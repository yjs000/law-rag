# 19 AI 없는 자연어 검색과 단계별 진단

## 문제

PGroonga에 사용자 문장을 그대로 전달하면 공백으로 나뉜 단어가 모두 필요한 검색이 된다. `확인할`, `알려주세요`, `절차` 같은 질문 표현이 원문에 없으면 핵심 법률 용어가 있어도 0건이 될 수 있다. 임베딩이 0건인 현재 운영 환경에서는 이를 의미 검색이 보완하지 못한다.

## 선택

- 서버가 질문을 정규화하고 안전한 토큰만 검색 구문으로 만든다.
- 제목, 조문 표제, 본문을 함께 검색한다.
- 엄격 검색이 0건일 때만 OR 완화 검색을 한다.
- `/v1/search`는 AI와 완전히 분리한다.
- NFTC처럼 한 문자열로 온 기술기준은 `1.1`, `1.2` 절 단위로 분리한다.
- 질문 이력에 각 단계의 상태와 후보 수를 JSONB로 남긴다.

## 데이터 흐름

`자연어 질문 → 조문 경로 파싱/토큰 정규화 → 엄격 키워드 검색 → 0건 시 완화 검색 → 허용 출처 필터 → 검색 전용 답변 → 단계별 진단 저장`

## 확인 명령

```text
cmd /d /c ..\..\.venv\Scripts\python.exe -m pytest tests\test_search_queries.py tests\test_parsers.py tests\test_migration_contract.py -q
cmd /d /c ..\..\.venv\Scripts\python.exe -m scripts.analyze_question_history --email user@example.com
```

두 번째 명령은 `apps/api`에서 실행하며 `DATABASE_URL`이 필요하다. 출력은 UTF-8 JSON이다.

## 남은 학습

완화 검색의 정밀도와 NFTC 재수집 후 청크별 Recall@10을 운영 평가셋으로 측정해야 한다.
