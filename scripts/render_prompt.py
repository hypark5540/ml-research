#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from ml_research.io import read_json
from ml_research.models import WeeklyDigest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the autonomous research prompt"
    )
    parser.add_argument("--topics", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--week-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()

    topics = read_json(args.topics)
    archive = read_json(args.archive)
    start_date = args.week_of - timedelta(days=7)
    schema = WeeklyDigest.model_json_schema()
    existing_ids = sorted(
        {
            paper["arxivId"]
            for digest in archive.get("digests", [])
            for paper in digest.get("papers", [])
        }
    )

    prompt = f"""\
Create one public bilingual weekly ML research digest for HYOYOUL BLOG.

You are running inside the ml-research automation repository. Your only permitted
write target is this exact file:
{args.output.resolve()}

Do not edit, commit, push, or delete any other file. Do not create a PR. The outer
automation will validate and publish your JSON.

Editorial window: {start_date.isoformat()} through {args.week_of.isoformat()}.
Audience and topic policy:
{json.dumps(topics, ensure_ascii=False, indent=2)}

Already published arXiv IDs, which must not be selected again:
{json.dumps(existing_ids, ensure_ascii=False)}

Research procedure:
1. Use hf_papers trending and searches across the configured tracks to build a
   diverse candidate pool. Prefer papers published or materially revised in the
   editorial window, but allow an older paper only when it is newly relevant and
   explicitly explain why.
2. Select exactly 3 to 5 papers using evidence quality, practical relevance to a
   data/ML engineer, novelty, and diversity. Do not select by hype alone.
3. For every selected paper, read its table of contents and the actual methodology,
   experiment, and limitation sections. Use primary paper/project sources. Search
   GitHub or HF resources only to verify released code or artifacts.
4. Attribute claims and numerical results to the paper. If a claim cannot be
   verified from a primary source, omit it. Never invent a venue, metric, code URL,
   citation count, author, or date.
5. Write complete Korean and English editorial summaries. They must communicate
   the same facts, findings, and limitations; they do not need to be literal
   translations.
6. Clearly separate what the paper demonstrates from why you recommend it. Mention
   material limitations, evaluation gaps, or threats to generalization.
7. Output raw JSON only at the required path, matching the schema below. Set:
   id = research-{args.week_of.isoformat()}
   slug = weekly-ml-research-digest-{args.week_of.isoformat()}
   weekOf = {args.week_of.isoformat()}
   version = 1
8. Run this validator and fix every error before finishing:
   python scripts/validate_digest.py {args.output.resolve()}

JSON Schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}
"""
    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
