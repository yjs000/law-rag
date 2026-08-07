# 0028: 검색 전 질문 라우팅과 조건부 query 보강

상태: `제안됨 · 미착수`

제안 출처: 2026-08-05 사용자 후속 작업 요청. 실험 D-10과 D-10-R1에서 법령 corpus로 직접 답할 질문,
추가 사실이 필요한 질문, 실시간 정보와 사용자 문서가 필요한 질문을 같은 검색 경로에 넣을 때 무관
법령이 상위 문맥에 포함되는 문제가 확인됐다.

관련 계획: [0025 승인 질문에서 근거 기반 AI 답변까지](../active/0025-approved-questions-to-grounded-answer-roadmap.md)
M4.5

## 목적과 사용자 결과

질문 embedding과 법령 검색 전에 질문의 필요한 근거 유형을 판정한다. 법령 corpus가 답할 수 없는 질문을
억지로 검색하지 않고, 추가 정보·최신 정보·사용자 문서가 필요한 상태를 사용자에게 정확히 돌려준다.

## 범위

- `clarification_required`: 위치·설비용량·자가소비·판매 방식 등 빠진 사용자 사실을 먼저 요청한다.
- `realtime_required`: 올해 예산·현재 가격·고장 상태처럼 시점에 따라 변하는 질문을 법령 검색으로
  대신하지 않는다.
- `external_document_required`: 계약서·정산서·공사비 산출서 등 사용자 또는 운영기관 문서를 요청한다.
- 그 밖의 법령 질문만 동결된 D1/D2 검색·문맥 경로로 보낸다.
- route, 이유 코드, 필요한 추가 사실·자료와 embedding/search 실행 여부를 기록한다.
- 라우팅 뒤 법령 검색 결과가 여전히 부족할 때만 query 보강을 별도 단계로 평가한다.

## 조건부 후속 단계

query 보강은 라우팅 구현과 평가를 통과한 뒤에도 직접 근거 순위가 부족한 법령 질문에만 적용한다.
원 질문과 보강 문구를 별도 version·SHA로 고정하고 D-10의 같은 10문항 query embedding을 한 batch로
최대 한 번 다시 만든다. 기존 3,066개 passage vector와 같은 corpus snapshot·embedding profile을
재사용하며 기존 D-10/D-10-R1 산출물을 덮어쓰지 않는다.

## 비범위

- 새 corpus 수집 또는 passage 재임베딩
- 실시간 정보원이나 사용자 문서 저장소 자체의 구현
- realtime·external-document 질문을 법령 검색으로 강제하는 동작
- AI 답변 생성과 실험 E
- 질문 ID나 D-10 수동 정답을 런타임 라우팅 규칙에 하드코딩

## 의존성과 미결정

- D-10 M3/M4의 동결 검색·문맥 계약과 연결해야 한다. 10문항 밖 오분류율 일반화가 필요하면 예정 작업
  0029의 독립 Gold를 먼저 활성화한다.
- realtime 정보에 사용할 승인된 공식 source와 external document의 보안·보존 계약은 이 항목의
  라우팅 구현 범위 밖이며 별도 사용자 결정이 필요할 수 있다.
- 라우터 구현 방식과 threshold는 미결정이다. 동결 10문항의 partial·clarification·corpus 밖 사례를
  보기 전에 평가 방법과 비용 gate를 고정하며 일반 threshold는 D-full 전 확정하지 않는다.

## active 승격 조건

- 사용자가 이 항목의 착수를 명시한다.
- route schema, 실패·보류 동작, 평가 fixture와 불필요 검색률 지표를 실행 계획에 고정한다.
- 외부 source·사용자 문서가 없는 경우의 차단 동작을 구현 전에 확정한다.
- 현재 Git 변경과 파일 범위 충돌이 없음을 확인한다.

## 완료 조건

- 라우팅이 query embedding보다 먼저 실행되고 네 경로의 정상·실패·경계 테스트가 통과한다.
- clarification·realtime·external-document 경로에서 허용 조건 전 embedding/search가 실행되지 않는다.
- route와 검색 생략 사유가 개인정보·질문 전문 없이 관측 가능하다.
- 고정 평가 fixture에서 오분류와 불필요 검색률을 기록하고 사전 확정 gate를 통과한다.
- 조건부 query 보강을 실행한다면 별도 비교 run에서 직접 근거 순위와 무관 top 5 변화를 기록한다.
