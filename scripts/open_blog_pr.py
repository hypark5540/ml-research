#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request


API_ROOT = "https://api.github.com"


def github_request(
    method: str,
    path: str,
    token: str,
    payload: dict | None = None,
) -> dict | list:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hyoyoul-ml-research",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Open the generated blog PR")
    parser.add_argument("--repo", default="hypark5540/hyoyoul-blog-v1")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--week-of", required=True)
    args = parser.parse_args()

    token = os.environ.get("BLOG_REPO_TOKEN")
    if not token:
        raise SystemExit("BLOG_REPO_TOKEN is required")

    owner = args.repo.split("/", 1)[0]
    query = urllib.parse.urlencode(
        {"state": "open", "head": f"{owner}:{args.branch}", "base": "main"}
    )
    existing = github_request("GET", f"/repos/{args.repo}/pulls?{query}", token)
    if existing:
        print(json.dumps(existing[0], ensure_ascii=False))
        return 0

    marker = "<!-- ml-research-automation:v1 -->"
    body = f"""{marker}
## 변경 내용

- {args.week_of} 주간 ML 연구 다이제스트 1편을 공개 Research 카테고리에 추가합니다.
- 3~5편의 논문을 한국어와 영어로 요약하고 원문 출처를 연결합니다.
- 생성 데이터는 스키마 검증과 블로그 전체 CI를 통과해야 합니다.

## 자동화 안전장치

- 에이전트 출력은 단일 JSON 파일로 제한됩니다.
- 기존 다이제스트와 arXiv ID 중복을 거부합니다.
- 동일 저장소의 `automation/ml-research-*` 브랜치와 이 마커가 있는 PR만 CI 성공 후 자동 머지됩니다.

## 배포

머지 후 `main` 배포 파이프라인을 통해 HYOYOUL BLOG에 반영됩니다.
"""
    pull = github_request(
        "POST",
        f"/repos/{args.repo}/pulls",
        token,
        {
            "title": f"research: publish weekly ML digest {args.week_of}",
            "head": args.branch,
            "base": "main",
            "body": body,
            "draft": False,
        },
    )

    try:
        github_request(
            "POST",
            f"/repos/{args.repo}/issues/{pull['number']}/labels",
            token,
            {"labels": ["automated-research"]},
        )
    except urllib.error.HTTPError as error:
        if error.code != 422:
            raise

    print(json.dumps(pull, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
