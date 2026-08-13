from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ml_research.io import atomic_write_json, read_json
from ml_research.models import WeeklyDigest
from ml_research.public_scan import assert_public_text_has_no_secret


ALLOWED_RESEARCH_TOOLS = frozenset({"hf_papers", "web_search"})


def build_restricted_tools(output: Path) -> list[Any]:
    from agent.core import tools as agent_tools

    original = agent_tools.create_builtin_tools
    safe_tools = [
        tool
        for tool in original(local_mode=False)
        if tool.name in ALLOWED_RESEARCH_TOOLS
    ]

    async def submit_digest(arguments: dict[str, Any]) -> tuple[str, bool]:
        try:
            if not isinstance(arguments, dict):
                raise TypeError("submission arguments must be an object")
            candidate = WeeklyDigest.model_validate(arguments.get("digest"))
            serialized = (
                json.dumps(
                    candidate.model_dump(mode="json"), ensure_ascii=False, indent=2
                )
                + "\n"
            )
            if len(serialized.encode("utf-8")) > 262_144:
                raise ValueError("candidate exceeds the 256 KiB public boundary")
            assert_public_text_has_no_secret(serialized)
            atomic_write_json(output, candidate.model_dump(mode="json"))
        except ValidationError as error:
            details = error.errors(include_input=False, include_url=False)
            return f"Digest rejected by the trusted validator: {details}", False
        except (TypeError, ValueError) as error:
            return f"Digest rejected by the trusted validator: {error}", False
        return "Digest accepted and written to the only permitted output file.", True

    safe_tools.append(
        agent_tools.ToolSpec(
            name="submit_weekly_digest",
            description=(
                "Validate and submit the final weekly digest. This is the only write "
                "capability. Call it with the complete digest object; fix validation "
                "errors and retry until it succeeds."
            ),
            parameters={
                "type": "object",
                "additionalProperties": False,
                "properties": {"digest": WeeklyDigest.model_json_schema()},
                "required": ["digest"],
            },
            handler=submit_digest,
        )
    )
    return safe_tools


async def run_agent(prompt: str, output: Path, max_iterations: int) -> None:
    from agent import main as agent_main
    from agent.core import tools as agent_tools

    restricted_tools = build_restricted_tools(output)
    original_factory = agent_tools.create_builtin_tools
    original_router_init = agent_tools.ToolRouter.__init__
    original_openapi = agent_tools.ToolRouter.register_openapi_tool

    def create_restricted_tools(local_mode: bool = False) -> list[Any]:
        del local_mode
        return restricted_tools

    def initialize_restricted_router(
        self: Any,
        mcp_servers: Any,
        hf_token: str | None = None,
        local_mode: bool = False,
    ) -> None:
        # ml-intern's packaged default config contains an HF MCP server and its
        # deep-merge semantics cannot clear it with an empty user mapping. Keep
        # the inference token out of every tool transport by forcing no MCPs.
        del mcp_servers, hf_token, local_mode
        original_router_init(self, {}, hf_token=None, local_mode=False)

    async def disable_dynamic_openapi(self: Any) -> None:
        del self

    output.unlink(missing_ok=True)
    try:
        agent_tools.create_builtin_tools = create_restricted_tools
        agent_tools.ToolRouter.__init__ = initialize_restricted_router
        agent_tools.ToolRouter.register_openapi_tool = disable_dynamic_openapi
        await agent_main.headless_main(
            prompt,
            max_iterations=max_iterations,
            stream=False,
            sandbox_tools=False,
        )
    finally:
        agent_tools.create_builtin_tools = original_factory
        agent_tools.ToolRouter.__init__ = original_router_init
        agent_tools.ToolRouter.register_openapi_tool = original_openapi

    if not output.is_file():
        raise RuntimeError("the research agent did not submit a digest")
    candidate = WeeklyDigest.model_validate(read_json(output))
    assert_public_text_has_no_secret(output.read_text(encoding="utf-8"))
    atomic_write_json(output, candidate.model_dump(mode="json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ML Intern with read-only tools")
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-iterations", type=int, default=90)
    args = parser.parse_args()

    prompt = args.prompt_file.read_text(encoding="utf-8")
    asyncio.run(run_agent(prompt, args.output.resolve(), args.max_iterations))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
