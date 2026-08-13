from __future__ import annotations

import asyncio

from ml_research.agent_runner import build_restricted_tools, run_agent
from ml_research.io import read_json
from tests.test_models import sample_digest


def test_restricted_agent_has_only_read_tools_and_trusted_submission(tmp_path) -> None:
    output = tmp_path / "weekly-digest.json"
    tools = build_restricted_tools(output)

    assert {tool.name for tool in tools} == {
        "hf_papers",
        "web_search",
        "submit_weekly_digest",
    }


def test_trusted_submission_writes_only_valid_canonical_digest(tmp_path) -> None:
    output = tmp_path / "weekly-digest.json"
    submit = next(
        tool
        for tool in build_restricted_tools(output)
        if tool.name == "submit_weekly_digest"
    )

    message, success = asyncio.run(submit.handler({"digest": sample_digest()}))

    assert success, message
    assert read_json(output)["id"] == "research-2026-08-06"
    assert output.read_bytes().endswith(b"\n")


def test_trusted_submission_rejects_exact_runtime_secret(tmp_path, monkeypatch) -> None:
    output = tmp_path / "weekly-digest.json"
    secret = "opaque-value-not-matching-a-known-prefix"
    monkeypatch.setenv("HF_TOKEN", secret)
    payload = sample_digest()
    payload["papers"][0]["summaryEn"] += f" Protected value: {secret}."
    submit = next(
        tool
        for tool in build_restricted_tools(output)
        if tool.name == "submit_weekly_digest"
    )

    message, success = asyncio.run(submit.handler({"digest": payload}))

    assert not success
    assert "exact protected secret" in message
    assert not output.exists()


def test_run_agent_blocks_configured_mcp_and_restores_library(
    tmp_path, monkeypatch
) -> None:
    from agent import main as agent_main
    from agent.core import tools as agent_tools

    output = tmp_path / "weekly-digest.json"
    original_factory = agent_tools.create_builtin_tools
    original_router_init = agent_tools.ToolRouter.__init__
    original_openapi = agent_tools.ToolRouter.register_openapi_tool

    async def fake_headless_main(*args, **kwargs) -> None:
        del args, kwargs
        router = agent_tools.ToolRouter(
            {"untrusted-default-mcp": object()},
            hf_token="must-not-reach-tools",
            local_mode=True,
        )
        assert router.mcp_client is None
        assert set(router.tools) == {
            "hf_papers",
            "web_search",
            "submit_weekly_digest",
        }
        message, success = await router.tools["submit_weekly_digest"].handler(
            {"digest": sample_digest()}
        )
        assert success, message

    monkeypatch.setattr(agent_main, "headless_main", fake_headless_main)

    asyncio.run(run_agent("trusted prompt", output, 3))

    assert read_json(output)["id"] == "research-2026-08-06"
    assert agent_tools.create_builtin_tools is original_factory
    assert agent_tools.ToolRouter.__init__ is original_router_init
    assert agent_tools.ToolRouter.register_openapi_tool is original_openapi
