# 03 하이브리드 RAG와 인용

## 개념과 선택 이유

RAG는 답변 전에 외부 근거를 검색해 모델 입력에 붙이는 방식이다. PGroonga는 한국어 용어 검색, pgvector는 의미 검색을 담당한다. RRF는 서로 다른 점수 대신 순위를 결합한다. Structured Outputs는 모델 출력을 Pydantic 스키마로 제한한다.

법률명·조문 번호는 키워드 검색이 강하고 생활 언어 질문은 의미 검색이 강하다. 두 검색을 결합하고 인용 ID 검증을 모델 밖에서 수행하면 일반 챗봇보다 추적 가능하다.

## 데이터 흐름

질문 → 512차원 임베딩 + PGroonga → 기준일 필터 → RRF → Responses API → 인용 ID 게이트 → 답변 또는 검색 전용 폴백.

## 직접 실행

```powershell
cd apps/api
uv run ruff check app scripts tests migrations
uv run pytest
cd ../..
pnpm.cmd typecheck
pnpm.cmd build
```

## 다음 학습 주제

Recall@10, 인용 정밀도, 프롬프트 주입 평가와 상하위법 그래프 확장을 학습한다.
