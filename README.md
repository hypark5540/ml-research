# HYOYOUL ML Research

HYOYOUL BLOG의 공개 `Research` 카테고리에 매주 3~5편의 머신러닝
논문을 묶은 한·영 다이제스트를 발행하는 자동화 저장소입니다.

## 발행 흐름

```text
ml-research GitHub Actions
  -> ML Intern 논문 검색·본문 조사
  -> 단일 주간 다이제스트 JSON 생성
  -> Pydantic 스키마·중복·출처 검증
  -> HYOYOUL BLOG 생성 데이터 갱신
  -> 양쪽 테스트와 블로그 프로덕션 빌드
  -> automation/ml-research-* 브랜치와 공개 PR
  -> 블로그 CI 성공 시 제한된 자동 머지
  -> main 연동 Vercel 배포
```

연구 에이전트는 블로그를 직접 편집하지 않습니다. 출력은
`generated/weekly-digest.json` 하나로 제한되고, 검증된 데이터만 블로그의
`content/public/research-digests.generated.json`에 원자적으로 병합됩니다.

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

- `HF_TOKEN`: Hugging Face Inference Providers 호출 권한
- `BLOG_REPO_TOKEN`: `hypark5540/hyoyoul-blog-v1`에 대해 Contents와 Pull
  requests 읽기/쓰기 권한이 있는 fine-grained token
- `S2_API_KEY`: 선택 사항이지만 Semantic Scholar rate limit 안정성을 위해 권장

토큰 값은 프롬프트나 생성 JSON에 넣지 않습니다. `BLOG_REPO_TOKEN`은 블로그
체크아웃, 자동화 브랜치 push, PR 생성에만 사용합니다.

## 로컬 검증

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
python3 -m ruff check .
python3 -m ruff format --check .
python3 -m pytest
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

수동 실행의 `week_of` 입력은 `YYYY-MM-DD`이며 비우면 서울 기준 실행 날짜를
사용합니다.

## 자동 머지 경계

블로그의 별도 `workflow_run` 작업은 다음 조건을 모두 만족할 때만 PR을
squash merge합니다.

- 블로그 CI가 성공함
- base가 `main`임
- head가 같은 블로그 저장소임
- 브랜치가 `automation/ml-research-`로 시작함
- PR 본문에 `ml-research-automation:v1` 마커가 있음

조건을 만족하지 않거나 merge API가 거부하면 PR은 열린 상태로 남습니다.
