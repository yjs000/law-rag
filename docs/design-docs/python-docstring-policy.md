# Python docstring 정책

상태: 승인

## 목적

공개 Python API와 복잡한 내부 경계의 의도를 코드 가까이에 남기되, 자명한 구현을 반복하는
주석과 기존 코드 전체의 일괄 정리 비용은 피한다.

## 규칙

- 공개 함수와 FastAPI 엔드포인트는 목적과 외부 계약을 docstring으로 작성한다.
- 복잡한 내부 함수는 목적과 함께 중요한 불변조건, 부작용, 안전한 fallback 또는 예외 조건을
  필요한 범위에서 작성한다.
- 단순 변환과 자명한 private helper에는 docstring을 강제하지 않는다.
- `#` 주석은 코드의 동작을 번역하지 않는다. 설계 선택의 이유, 제약, 보안, 개인정보 또는
  호환성 조건만 설명한다.
- 한 줄 docstring은 명령형 요약과 마침표를 사용하며, 타입 힌트로 알 수 있는 인자 목록을
  반복하지 않는다.
- 여러 줄 docstring은 한 줄 요약 뒤에 빈 줄을 두고, 반환값, 부작용, 예외 또는 호출 제약 중
  독자가 알아야 하는 항목만 추가한다.

## 자동 검사와 적용 범위

별도 `pydocstyle` 의존성을 추가하지 않는다. 이미 사용하는 Ruff의 `D` 규칙과 `pep257` 규약을
사용한다. 최초 적용 대상은 다음 v2 질문 요청 경로와 그 초기화·검색 경계다.

- `apps/api/app/main.py`
- `apps/api/app/adapters/llamaindex_repository.py`
- `apps/law-rag-llamaindex/src/law_rag_llamaindex/config.py`
- `apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py`
- `apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py`
- `apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py`

CI는 위 파일에만 `D100,D101,D102,D103,D107,D200,D205,D209,D400,D401,D403`을 실행한다.
이는 공개 API 누락과 승인된 요약·여러 줄 형식만 검사하며, 인자 설명 강제처럼 현재 정책에 없는
규칙은 포함하지 않는다. 이후 새 파일 또는 수정하는 파일을 동일 검사 목록에 추가하며, 기존
저장소 전체에 `D`를 전역 활성화하지 않는다.

## 결정 기록

- 2026-08-20: 별도 pydocstyle 대신 Ruff `D` 규칙을 사용한다. 기존 CI가 Ruff를 이미 실행하고
  있어 의존성·명령을 늘리지 않으면서 같은 docstring 규약을 적용할 수 있기 때문이다.
- 2026-08-20: `D` 규칙은 v2 질문 경로부터 파일 단위로 도입한다. 기존 코드 전체에 문서화 부채를
  한 번에 부과하지 않고, 변경 지점부터 일관성을 확보하기 위함이다.
