# HYOYOUL ML Research

HYOYOUL BLOG의 공개 `Research` 카테고리에 매주 3~5편의 머신러닝
논문을 묶은 한·영 다이제스트를 발행하는 자동화 저장소입니다.

## Codex 전환 (2026-09-07)

새 경로는 **비공개 GitHub Actions의 Python 자료 수집 → 구독 로그인 Codex의
한·영 작성 → 이 공개 저장소의 독립 검증·immutable release → 기존 블로그 importer**입니다.
Mac이 켜져 있을 필요가 없습니다. 이 공개 저장소에는 Codex OAuth 세션을 두지 않습니다.
공개 `publish-codex-digest.yml`은 네 가지 데이터 입력(날짜, canonical base64 JSON,
SHA-256, 예상 public main SHA)만 받으며, 원본 바이트를 다시 검증한 뒤 기존과 같은
release·attestation 조건으로 게시합니다. 실패하면 소유자에게 일반적인 GitHub issue를
생성하며 비밀값·후보 본문은 넣지 않습니다.

초기 인증 및 비공개 canary 성공 전에는 새 자동 실행을 활성화하지 않습니다.
HF 추론으로 자동 대체하지 않으며, 아래 HF 기반 구현은 이전 구조의 참고 자료입니다.
전환 시 기존 `weekly-digest.yml`의 예약 실행은 비활성화합니다. 되살리는 것은 별도
운영 결정이며 HF 유료 추론을 다시 사용할 수 있습니다.

[Writing 아키텍처 문서·draw.io·Mermaid](https://www.hyoyoul.com/posts/research-automation-hf-to-codex)
에서 전후 구조, 인증 갱신 경계, 비용 및 도입 순서를 확인할 수 있습니다.

## 이전 HF 경로: 발행 흐름

```text
ml-research GitHub Actions
  -> context job: 블로그 공개 API에서 주차와 기존 arXiv ID만 격리
  -> research job: 제한된 ML Intern 조사 도구와 단일 JSON 제출
  -> validate job: 새 runner와 블로그 production 스키마로 재검증
  -> publish job: 검증 SHA와 실행 SHA에 결박된 immutable GitHub Release 발행
  -> 블로그 importer가 release metadata·digest·attestation과 전체 build 재검증
  -> 검사한 main SHA에만 원자적으로 fast-forward
  -> main 연동 Vercel 배포
```

연구 에이전트는 블로그를 checkout하거나 직접 편집하지 않으며
`BLOG_REPO_TOKEN`도 받지 않습니다. 공개된 주차·arXiv ID 목록과 `HF_TOKEN`만
있는 독립 runner에서 동작합니다. ML Intern에 노출되는 기능은 `hf_papers`,
`web_search`, 검증된 `submit_weekly_digest`뿐입니다. 셸·파일 읽기·임의 파일 쓰기·
동적 OpenAPI/MCP 도구는 등록하지 않습니다. 출력은
`generated/weekly-digest.json` 하나로 제한되고, 별도의 read-only validate job이
같은 바이트를 블로그의 production validator에도 확인시킨 뒤에만 최소 권한
publish job으로 넘깁니다. ML 저장소와 ML Intern은 비공개 블로그 읽기·쓰기 권한을
전혀 받지 않습니다. 블로그는 공개 API와 immutable release 사이의 데이터만
교환하고, 자체 일회성 `GITHUB_TOKEN`으로 공개 아카이브에 원자적으로 병합합니다.

## 편집 정책

- 매주 정확히 3~5편을 추천합니다.
- 최근 7일의 논문과 큰 수정본을 우선합니다.
- 데이터·ML 시스템, LLM/에이전트 엔지니어링, 효율적인 학습·추론,
  신뢰성과 안전성을 균형 있게 다룹니다.
- 초록만 요약하지 않고 방법론, 실험, 결과, 한계를 확인합니다.
- 논문이 증명한 내용과 추천 이유를 분리합니다.
- 한국어와 영어에 동일한 핵심 사실·한계·원문 링크를 제공합니다.
- 과거 다이제스트에 등장한 arXiv ID는 다시 발행하지 않습니다.

주제와 선별 기준은 `config/topics.json`, 에이전트의 CI 설정은
`config/ml-intern.ci.json`에 있습니다. 자동화 세션의 HF trace 업로드는
비활성화되어 있습니다.

## 이전 HF 경로: 필요한 GitHub Actions secrets

`ml-research` 저장소의 Actions secrets에는 다음 값 하나만 등록합니다.

- `HF_TOKEN`: **Make calls to Inference Providers** 권한이 있는 Hugging Face token

토큰 값은 프롬프트나 생성 JSON에 넣지 않습니다. 로컬 `.env`에는 HF 토큰만
둡니다. 블로그 PAT와 Semantic Scholar API key는 자동화에 필요하지 않습니다.

## 로컬 검증

```bash
uv sync --frozen --extra dev
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv export --frozen --extra dev --no-hashes \
  --no-emit-project --no-emit-package ml-intern \
  | uv run --frozen pip-audit --strict --disable-pip --no-deps -r /dev/stdin
```

다이제스트 또는 전체 공개 아카이브는 다음처럼 검사합니다.

```bash
python3 scripts/validate_digest.py generated/weekly-digest.json
python3 scripts/validate_digest.py \
  --archive ../hyoyoul-blog-v1/content/public/research-digests.generated.json
```

## 이전 HF 경로: 예약 실행

GitHub Actions cron은 **매주 일요일 오전 9시(Asia/Seoul, 일요일 00:00 UTC)** 에
실행됩니다. 필요할 때는 `workflow_dispatch`로 수동 실행할 수도 있습니다.
블로그 importer는 같은 날 12시·14시·16시에 공개 release를 확인합니다.

수동 실행의 `week_of` 입력은 `YYYY-MM-DD`이며 비우면 서울 기준 실행 날짜를
사용합니다. 따라서 단순 점검 목적으로 빈 입력을 실행해도 no-op이 아니며, HF
추론 비용과 실행일 이름의 주중 release가 생길 수 있습니다. 기존 주차를 지정해도
조사는 먼저 다시 실행되고, 결과가 기존 immutable asset과 바이트 단위로 같을 때만
publish 단계가 no-op으로 끝납니다. 수동 실행은 실제 추가 발행 또는 의도적인 재현
검증에만 사용합니다.

## 자동 발행 경계

ML 저장소는 공개 예정인 canonical JSON을 256 KiB로 제한하고, 중복 JSON key와
credential 형태의 문자열을 거부한 뒤 주차별 GitHub Release로만 발행합니다.
발행 전 블로그 production validator가 같은 SHA-256을 승인해야 합니다. Release는
정확한 workflow `GITHUB_SHA`, 단일 `weekly-digest.json`, 서버가 기록한 SHA-256,
GitHub release attestation을 모두 만족해야 하며 immutability가 꺼져 있으면
게시 직후 검증에서 실패하고 블로그도 해당 release를 거부합니다. 블로그 importer는
서울 현재일 기준 미래 또는 14일보다 오래된 주차,
기존 글 변경, 중복 주차, 허용되지 않은 URL·문자·필드를 거부하고 전체 블로그
테스트와 프로덕션 빌드를 실행합니다. 검증을 시작한 `main` SHA가 그대로일 때만
단일 커밋을 non-force fast-forward합니다.
