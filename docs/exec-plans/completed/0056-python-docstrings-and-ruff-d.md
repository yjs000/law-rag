# Python Docstrings and Ruff D Implementation Plan

상태: 완료 (2026-08-20)

**Goal:** 공개 API와 v2 질문 경로에 승인된 docstring 정책을 적용하고, 대상 Ruff `D` 검사를 CI에 추가한다.

## 결과

- 별도 `pydocstyle` 의존성 없이 API·LlamaIndex 프로젝트 Ruff에 `pep257` 규약을 설정했다.
- CI가 `D100,D101,D102,D103,D107,D200,D205,D209,D400,D401,D403`만 아래 대상 파일에 실행한다.
  - `apps/api/app/main.py`
  - `apps/api/app/adapters/llamaindex_repository.py`
  - `apps/law-rag-llamaindex/src/law_rag_llamaindex/config.py`
  - `apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py`
  - `apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py`
  - `apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py`
- FastAPI 공개 엔드포인트와 v2 공개 인터페이스에는 목적·외부 계약을, 복잡한 질문 처리 함수에는
  예산·취소 정리·근거 우선 fallback 불변조건을 docstring으로 기록했다.
- [설계 기준](../../design-docs/python-docstring-policy.md)을 추가하고 색인에 연결했다.

## 검증 증거

- 변경 전 대상 `D` 검사: API 44건, LlamaIndex 9건 위반을 재현했다.
- 변경 후 대상 Ruff 검사: 두 프로젝트 모두 `All checks passed!`.
- v2 질문·저장소 회귀: 10 passed.
- v2 retriever·store 회귀: 7 passed.
- 대상 파일의 기존 일반 Ruff 검사: 모두 통과.
- `git diff --check`: 공백 오류 없음.
- 전체 문서 검사: 이번 작업과 무관한 기존 broken link 목록 때문에 실패했다. 새 정책 문서는 오류
  목록에 없으며, 해당 링크 정리는 별도 작업으로 남긴다.

## 알려진 환경 제약

- sandbox는 기본 Windows pytest 임시 폴더에 쓰지 못한다. 프로젝트 내부 `--basetemp`로 우회한
  전체 API·core 실행은 도구의 30초 출력 창이 종료 코드 전에 분리되어 최종 전체 결과를 확인하지
  못했다. 이 변경의 직접 대상인 17개 v2 회귀와 lint 검증은 통과했다.
- sandbox에서 `uv` 캐시·환경 잠금 파일 접근과 네트워크 기반 재빌드는 제한된다. 설치된
  가상환경의 `python -m pytest` 및 `ruff --no-cache`로 대상 검증을 수행했다.
