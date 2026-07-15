# 12. 웹의 빈 검색 결과 상태

## 배운 문제

HTTP 요청이 성공하고 `mode=search_only`여도 `sections`와 `citations`가 모두 비면 사용자가 확인할 실질 응답은 없다. 이 상태를 일반 검색 전용 응답처럼 렌더링하면 범위·한계 문장만 남아 시스템이 질문을 이해했는지, 검색이 실패했는지 구분하기 어렵다.

## 구현 선택

API의 `result_status=no_results`를 우선 사용하고 `no_results_reason`의 내부 코드를 한국어 원인으로 변환한다. `requested_path_not_found`는 요청한 조·항 경로가 기준일 유효 원문에 없음을, `no_matching_evidence`는 허용 코퍼스에서 일치 근거를 찾지 못했음을 뜻한다. 새 필드가 없는 이전 API 응답은 `sections`와 `citations`가 모두 빈 경우로 판별한다.

`1조2항은?`처럼 법령명 없이 조문 경로만 입력해도 API는 MVP 법령 전체에서 같은 경로를 검색한다. 결과가 없으면 법령명 누락을 실패 원인으로 단정하지 않고, 기준일 유효 대상 법령에서 해당 경로를 찾지 못했다고 설명한다. 다만 결과를 한 법령으로 좁히려면 `전기사업법 제1조 제2항은?`처럼 법령명과 경로를 함께 쓰도록 안내한다. 빈 결과 직후의 하단 행동은 로그인보다 질문 수정과 입력창 포커스를 우선한다.

## 검증

```powershell
pnpm.cmd --filter @law-rag/web test
pnpm.cmd --filter @law-rag/web typecheck
pnpm.cmd --filter @law-rag/web lint
```

테스트는 명시적 결과 상태, 두 원인 코드의 사용자 문구 변환, 구버전 응답 호환, 인용이 있는 응답의 오탐 방지를 확인한다.
