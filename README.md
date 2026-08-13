# HYOYOUL ML Research

HYOYOUL BLOG의 공개 `Research` 카테고리에 매주 3~5편의 머신러닝
논문을 묶은 한·영 다이제스트를 발행하는 자동화 저장소입니다.

## 발행 흐름

```text
ml-research GitHub Actions
  -> context job: 블로그의 공개 read-only API에서 다이제스트 목록만 격리
  -> research job: ML Intern 조사와 단일 JSON 생성
  -> publish job: 새 runner에서 스키마·출처·주차를 재검증
  -> 주차별 공개 GitHub Release에 변경 불가능한 JSON 발행
  -> 블로그 importer가 자체 권한으로 날짜·append-only·URL·전체 build 재검증
  -> 검사한 main SHA에만 원자적으로 fast-forward
  -> main 연동 Vercel 배포
```

연구 에이전트는 블로그를 checkout하거나 직접 편집하지 않으며
`BLOG_REPO_TOKEN`도 받지 않습니다. 공개된 과거 다이제스트 목록과 `HF_TOKEN`만
있는 독립 runner에서 동작합니다. 출력은 `generated/weekly-digest.json` 하나로
제한되고, 별도의 신뢰된 publish job이 다시 검증한 데이터만 블로그의
공개 release로 내보냅니다. ML 저장소와 ML Intern은 비공개 블로그 읽기·쓰기
권한을 전혀 받지 않습니다. 블로그가 공개 API와 release 사이의 데이터만 교환하고,
자체 일회성 `GITHUB_TOKEN`으로 `content/public/research-digests.generated.json`에
원자적으로 병합합니다.

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

## 필요한 GitHub Actions secrets

`ml-research` 저장소의 Actions secrets에 다음 값을 등록해야 합니다.

- `HF_TOKEN`: **Make calls to Inference Providers** 권한이 있는 Hugging Face token
- `S2_API_KEY`: 선택 사항이지만 Semantic Scholar rate limit 안정성을 위해 권장

토큰 값은 프롬프트나 생성 JSON에 넣지 않습니다. 로컬 `.env`에는 HF 토큰만
둡니다. 블로그 PAT는 필요하지 않으며, 저장소에 남아 있는 과거
`BLOG_REPO_TOKEN` secret은 새 경로 검증 후 삭제합니다.

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

## 예약 실행

GitHub Actions cron은 **매주 일요일 오전 9시(Asia/Seoul, 일요일 00:00 UTC)** 에
실행됩니다. 필요할 때는 `workflow_dispatch`로 수동 실행할 수도 있습니다.
블로그 importer는 같은 날 12시·14시·16시에 공개 release를 확인합니다.

수동 실행의 `week_of` 입력은 `YYYY-MM-DD`이며 비우면 서울 기준 실행 날짜를
사용합니다.

## 자동 발행 경계

ML 저장소는 공개 예정인 검증 JSON을 주차별 GitHub Release로만 발행합니다.
블로그 importer는 서울 현재일 기준 미래 또는 14일보다 오래된 주차, 기존 글
변경, 중복 주차, 허용되지 않은 URL·문자·필드를 거부하고 전체 블로그 테스트와
프로덕션 빌드를 실행합니다. 검증을 시작한 `main` SHA가 그대로일 때만 단일
커밋을 non-force fast-forward합니다. 중간에 `main`이 바뀌면 Git이 push를
거부하고 다음 실행에서 새 상태를 다시 검증합니다.
