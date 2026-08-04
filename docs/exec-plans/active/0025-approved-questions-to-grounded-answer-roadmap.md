# 실행 계획 0025: 승인 질문에서 근거 기반 AI 답변까지

상태: 진행 중 — M0·M1 완료, M2 독립 gold 제작 방법 확정·미착수
작성일: 2026-08-04
소유자: 주 에이전트

## 목적과 사용자 결과

승인된 일반 사용자 질문 1,000개를 독립적인 정답 근거가 있는 gold로 승격한 뒤, 실험 D로 검색과
AI 입력 문맥을 확정하고 NVIDIA 답변을 실험 E로 평가한다. E가 통과한 설계만 운영 경로에 반영하고,
남아 있는 활성 계획을 최소 비용 순서로 마친 뒤 전체 테스트와 공개 종단 검증을 수행한다.

이 문서는 여러 활성 계획의 순서와 합류 지점을 정하는 상위 로드맵이다. 세부 데이터 계약과 구현
체크리스트는 기존 실행 계획과 설계 문서가 계속 권위 원본이다.

## 범위와 비범위

범위:

- corpus 게시 준비 증명과 D 기준 snapshot 동결
- approved gold 제작·독립 검토·adjudication
- 실험 D의 raw dense 검색과 production dense-path 문맥 조립 평가
- NVIDIA 답변 연결과 실험 E
- 활성 계획 0002·0008·0012·0015의 합류 순서와 완료 gate
- 설계 동결, 전체 회귀·운영·공개 URL 검증

비범위:

- HNSW, hybrid, RRF, BM25 기본 채택, reranker와 similarity cutoff
- 새 영구 database, Redis·queue, 별도 유료 scheduler와 자동 유료 retry
- 운영 DB를 대상으로 한 고의 failure injection
- E 통과 전 Production AI 기본 활성화
- 검증하지 않은 역사 corpus 범위 공개

## 비용·범위 원칙

1. 사용자 핵심 흐름에 필요한 기능만 만든다. 새 유료 서비스, Redis, queue, 별도 영구 staging DB는
   추가하지 않는다.
2. 검색 정확성은 corpus 정확성, 직접 근거 충분성, 검색 순위 순으로 검증한다. 성능 최적화와 운영
   확장은 그 뒤에 한다.
3. 현재 검색은 NVIDIA 512차원 `dense-only`와 exhaustive exact cosine을 유지한다. HNSW, hybrid,
   RRF, reranker와 고정 similarity cutoff를 도입하지 않는다.
4. 로컬 vector와 bundle은 준비·운반 자료다. 웹과 API는 PostgreSQL에 검증·commit된 활성 vector와
   corpus만 읽는다.
5. calibration에서만 설정을 조정하고 held-out test는 동결한 설정으로 한 번 실행한다. 한 번에 한
   변수만 바꾼다.
6. AI 기능이 검증되기 전에는 검색 전용 모드를 유지한다. 모델 실패·인용 검증 실패·근거 부족은
   검색 전용 또는 명시적 근거 부족으로 종료한다.
7. 운영 DB를 통합 테스트 DB로 사용하지 않는다. 고의 실패와 rollback 검증은 CI의 일회성
   PostgreSQL에서만 수행한다.

## 현재 확인된 사실

| 항목 | 확인 상태 | 판단 |
| --- | --- | --- |
| 질문은행 | 1,000문항, 문구 SHA-256 `523325a6d86d2503492ff4dd8479f0a7e6045950dcef9288f970da0ae44d5a1a` | 입력 문구 고정 |
| 질문 범위 | 범위 SHA-256 `a8340555919ceac96616984d5f39b59ee9f0019c092a60918f772ffec4796845` | scenario family·의도·기술·표현 범위 고정 |
| 질문 승인 | `yjs000`, 2026-08-04, 1,000/1,000 `approved` | `question_text_and_scope_only` 승인 완료 |
| 고위험 35문항 | 유지 의도 2, clarification 의도 12, unanswerable 의도 21 | 최종 answerability가 아닌 gold 검토 힌트 |
| gold | 0문항 | qrels·기준 문맥·기준 응답·독립 검토·adjudication 미완료 |
| 실험 D | 계약과 합성 fixture runner만 준비됨 | 실제 1,000문항 embedding·검색·지표 미실행 |
| AI 입력 문맥 | 조문별 최고 leaf 1개, 최대 5개 조문·60,000자 | 계층 복원과 facet 충족을 평가하지 않은 임시값 |
| NVIDIA 생성 | adapter와 API 연결 코드는 존재 | hosted 답변 smoke·반복성·법률 품질·비용 미측정 |
| 실험 E | 계획·runner·산출물 없음 | D 문맥 동결 뒤 별도 설계 필요 |
| corpus publisher | draft PR CI에서 PostgreSQL 통합 5건 실행, 운영 DB 읽기 전용 preflight 통과 | 실제 변경 bundle 게시·점검 모드·검색 smoke는 미실행 |
| Git 상태 | `codex/corpus-publisher-preflight`, draft PR #2 | Production `main`에는 병합·push하지 않음 |

질문은행 파일의 `draft_for_human_question_review`와 문항의 `not_annotated`는 승인 실패가 아니다. 질문
승인은 별도 manifest에 있고, `not_annotated`는 정답 근거 주석이 아직 없다는 뜻이다.

## 선행 관계와 마일스톤

| 순서 | 마일스톤 | 결과물 | 다음 단계 진입 조건 |
| ---: | --- | --- | --- |
| M0 | 입력과 상태 감사 | 승인 manifest·active 계획 상태 확인 | 완료 |
| M1 (완료) | corpus 게시 준비 증명 | CI PostgreSQL 결과와 운영 비파괴 preflight | D·gold 기준 corpus가 DB에 확정됨 |
| M2 (방법 확정·미착수) | 독립 gold 제작 | 1,000문항 approved gold와 adjudication manifest | gold preflight 전체 통과 |
| M3 | 실험 D1 | calibration raw exact dense 검색 기준선 | test를 열지 않고 오류 분석 완료 |
| M4 | 실험 D2 | AI 입력용 검색 문맥 계약 v1과 D1·D2 held-out 결과 | 문맥 설정 동결 뒤 test 1회 통과 |
| M5 | NVIDIA 답변 연결 | 동결 문맥 입력, 답변 동작·인용 gate | bounded hosted smoke 통과 |
| M6 | 실험 E | 답변 품질·안전·비용·반복성 결과 | 사전 등록 release gate 통과 |
| M7 | 운영 잔여 계획 해결 | 0008·0012·0015와 0002 출시 항목 | 각 계획의 운영 증거 완료 |
| M8 | 설계 확정과 전체 검증 | 버전 고정·go/no-go 보고 | 중대 오류 0, 전체 gate 통과 |

핵심 경로는 `승인 질문 → corpus 확정 → gold → D1 검색 → D2 문맥 → NVIDIA → E → 설계 확정`이다. 0008 검색
성능, 0012 분산 취소와 0015 scheduler는 D의 선행 조건이 아니다.

## 담당과 검증 책임

| 마일스톤 | 담당 | 독립 검증 |
| --- | --- | --- |
| M1 | 주 에이전트·CI | publisher PostgreSQL 통합 결과와 운영 preflight diff 검토 |
| M2 | 분리된 주석자·검토자·판정 담당자 | 주 에이전트 계약 통합, gold preflight |
| M3~M4 | 검색 평가 담당 에이전트 | held-out 개봉 전 설정·threshold 봉인 감사 |
| M5~M6 | NVIDIA 연결·답변 평가 담당 에이전트 | 결정적 validator와 독립 표본 검토 |
| M7 | 각 active 계획의 DB/API/Web/운영 담당 | 계획별 focused test와 운영 증거 |
| M8 | 주 에이전트 | 전체 immutable diff, CI, 공개 E2E와 go/no-go |

각 구현 마일스톤은 관련 설계·운영 문서와 `docs/learning/` 기술 브리핑을 같은 기능 commit에서
갱신한다. 통합, staging과 commit은 주 에이전트가 담당한다.

## 사용자 승인 gate와 현재 차단 요소

- 현재 로드맵 작성과 읽기 감사에는 외부 차단 요소가 없다.
- 운영 `apply-prepared` 직전에는 update ID, bundle SHA, 기준 snapshot, 변경 문서·조문·vector 수와 예상
  점검 시간을 보고하고 별도 승인을 받는다.
- M2 후보 pool의 외부 provider 호출, D 질문 embedding과 E1·E2·E3 전에 예상 호출 수·token·quota와
  최대 비용을 계산해 승인된 상한 안에서만 실행한다. 한 단계가 gate를 통과하지 못하면 뒤의 유료
  호출을 시작하지 않는다.
- 운영 migration, 분산 취소, retention schedule과 공개 AI 활성화는 각각 별도 운영 승인 뒤 수행한다.
- final gold adjudication 직전부터 D held-out 완료까지의 짧은 corpus publisher schedule 중지 창도 운영
  승인 대상으로 보고한다.
- NVIDIA 데이터 처리·Trial/Production 조건과 법률 전문가 표본은 공개 AI 전 외부 확인 항목이다.

## M0 — 질문 승인과 상태 감사

- [x] 질문 승인 manifest가 1,000개 고유 ID와 개별 문구·범위 해시를 모두 승인했는지 확인한다.
- [x] 질문 승인과 gold 승인을 구분한다.
- [x] active index에서 빠진 `0022`를 복구한다.
- [x] Discord 전용 `docs/ROADMAP.md`는 이 작업의 운영 보드로 수정하지 않고, 관련 미완료 항목만
  이 로드맵에 반영한다.
- [x] 원격 작업을 재개하기 전에 현재 main의 미푸시 커밋과 CI 상태를 다시 확인한다.

## M1 — 운영 DB 반영 전 corpus 게시 검증

gold는 corpus ID·본문·기준일 population에 결박되므로 이 단계를 먼저 마친다. 현재 DB의 확정 corpus에
변경이 없다면 실제 게시 없이 비파괴 preflight만 통과하고 M2로 간다.

1. push 승인을 받은 뒤 현재 branch를 원격에 올려 GitHub CI의 일회성 PostgreSQL 17 service를
   실행한다.
2. `CORPUS_PUBLISH_TEST_DATABASE_URL`로 publisher 통합 5건을 통과시킨다. 같은 CI가
   `RETENTION_TEST_DATABASE_URL`의 retention 통합 2건도 실행하지만, 이 결과는 M7·M8의 0015 gate로
   기록하고 corpus·gold·D를 막지 않는다. 두 값에는 운영 URL을 넣지 않는다.
3. 운영에서는 기존 `DIRECT_URL`의 명시적 `READ ONLY` transaction과 짧은 statement timeout에서만
   migration head, gate, active profile, vector coverage, 기준 snapshot과 bundle checksum을 사전 점검한다.
   함수·trigger를 포함해 write를 유발하는 SQL은 호출하지 않는다.
4. 변경이 없으면 NIM·Storage·점검 모드·DB write 없이 종료한다.
5. 실제 변경 bundle이 있을 때만 점검 창에서 한 번 게시한다.
   - gate close와 65초 drain
   - 단일 Tx B commit
   - profile·coverage·snapshot 확인
   - gate reopen과 검색 smoke
6. 운영 DB에 고의 실패를 주입하지 않는다. 단계별 실패와 rollback은 CI에서 증명한다. 운영의 자연
   실패가 발생하면 Tx B 변경 없음과 `search_ready=false`를 확인하고, 원인을 고친 뒤 같은 계약으로
   복구한다.
7. M2가 사용할 확정 snapshot ID와 기준일별 population fingerprint를 기록한다.

`CORPUS_PUBLISH_TEST_DATABASE_URL`은 새 운영 database가 아니다. CI job 종료와 함께 사라지는 빈 테스트
database이고, 운영 게시에는 기존 `DIRECT_URL`만 사용한다.

### M1 완료 증거 — 2026-08-04

- draft PR: [#2](https://github.com/yjs000/law-rag/pull/2), Production `main` 병합·push 없음
- CI: commit `8a71024`, [run 30898366884](https://github.com/yjs000/law-rag/actions/runs/30898366884)
  - API/core `531 passed`
  - collector `99 passed`; `test_prepared_publisher_postgres.py` 5건 모두 실행되고 skip 0건
  - Web lint·typecheck·test·build, Ruff와 문서 검사 통과
- 운영 `DIRECT_URL` 읽기 전용 preflight 기록 시각: `2026-08-04T18:56:50+09:00`
  - transaction: `REPEATABLE READ`, `READ ONLY`, statement timeout `15s`, lock timeout `2s`
  - migration head `0011`, `corpus.search_ready=true`, reason `embedding_profile_verified`
  - 활성 profile: `nvidia-nemotron-3-embed-1b-512-v1`, NVIDIA 2,048차원 응답의 앞 512차원 사용 후 L2 정규화
  - 검색 조문 `3,066`, 정상 vector `3,066`; 누락·잘못된 차원·본문 SHA 불일치·비단위 vector 모두 `0`
  - 게시 기준 snapshot `corpus-sha256:c836fe1cba95ac6a4896047d5bfd6e3a8f314652e33c3694633db124cb5bb85c`
  - runtime snapshot `corpus-sha256:605b1f53b4fbe3edff19000796e56d906415e7648e7e6ae6119a46f5fc8d9578`
  - 지원 범위 계산값 `2024-07-01~2026-08-04`, 해당일 eligible 조문 `3,066`
  - bundle 없음(`present=false`): bundle checksum·새 게시 결과는 검증 대상이 아니었음
- 이 preflight에서는 DB write, advisory lock, NIM·Open API·Storage 호출, 점검 모드와 검색 smoke를 실행하지
  않았다. 한 시점의 읽기 전용 검사이므로 완료 직후의 변경까지 막는 보장은 없다.
- CI publisher 5건은 실제 PostgreSQL에서 바깥 Tx B commit/rollback, gate와 writer lock 해제를 검증한다.
  내부 단계 적용 함수·Storage·65초 drain은 대체 구현을 사용하므로 실제 각 단계 SQL의 독립 장애 주입까지
  통과했다고 해석하지 않는다.

## M2 — 독립 gold 제작 — 방법 확정, 구현·주석 미착수

gold는 질문 승인 manifest의 canonical payload SHA-256
`d41f6a206fec705a2e99b2b9543a6472cd5c5c067fc3a2a530e31a9a08fde869`에 결박한다. 실제 JSON 파일 byte
SHA-256 `19b1e40704d38a56751cf7a539a39075af18d1e5bbed8e47b1a3b00dabf82f31`과 역할을 섞지 않는다.

### M2.1 50문항 pilot

1. 승인 manifest에 결박된 10개 scenario family × 5문항 작업표를 생성한다.
2. 주석자와 검토자를 분리해 각 문항의 기준일, answerability, 필수 답변 요소, qrels, 기준 문맥과
   기준 응답을 독립적으로 작성한다. `reviewer_id`는 `annotator_id`와 달라야 한다.
3. 후보 검색은 원문 검토를 돕는 pool로만 사용한다. dense와 keyword 결과를 결합해 새 운영 검색기로
   만들거나 현재 검색 점수를 정답 라벨로 복사하지 않는다.
4. 전체 corpus를 직접 검토하지 않는 문항은 최소 두 독립 후보 수집 방법을 사용한다. 방법별 exact
   top-k, 설정 SHA와 후보 ID 집합 SHA를 기록하고, 주석자와 검토자에게 retrieval system label을 숨긴다.
5. 수집한 후보 합집합을 빠짐없이 판정해 각 후보를 positive qrel 또는 distractor로 분류하고
   `pool_candidates_judged=true`와 alternative-positive 탐색 수행 여부를 기록한다. 이는 corpus 전체의
   모든 관련 근거를 찾았다는 보장이 아니라, 사용한 pool의 판정 완료를 뜻한다.
6. 직접 근거는 국가법령정보 공동활용 Open API에서 수집해 현재 parser가 구조화한 원문·버전·본문
   SHA로 확인한다. FAQ 답변이나 모델 기억을 qrels로 사용하지 않는다.
7. pilot 50문항의 불일치를 최초 주석자와 다른 판정 담당자가 adjudication하고 다음 경계를 고정한다.
   - `fully_answerable | partially_answerable | clarification_required | unanswerable`
   - 직접 근거 relevance 2와 보조 문맥 relevance 1
   - 넓은 질문의 필수 facet 크기
   - 추가 질문과 근거 부족 기준 문구
8. 질문 의미·corpus 범위·법률 판단이 실제로 바뀌는 미해결 쟁점만 사용자에게 요청한다. 주 에이전트는
   주석과 검토 결과의 통합을 담당하고, 최초 주석자로 참여한 문항의 독립 adjudicator를 겸하지 않는다.

### M2.2 전체 1,000문항

- pilot 뒤 남은 calibration 150문항을 먼저 주석하고, 200문항 계약·pool·preflight checkpoint가
  통과한 뒤에만 test 800문항을 시작한다.
- 확정한 calibration 계약을 test 800문항에 적용한다.
- 같은 scenario family의 다섯 표현을 같은 split에 둔다. calibration 40 family·200문항, test
  160 family·800문항을 고정한다.
- 문항마다 supported facet의 relevance 2 근거, 필요한 evidence closure, 기준 응답과 인용을 완성한다.
- 고위험 35문항의 기존 분류 의도는 참고만 하고 원문 검토로 최종 answerability를 다시 확정한다.
- test qrels는 검색 설정 조정에 사용하지 않고, 후보 pool의 방법·설정과 최종 판정까지 봉인한다.
- 모든 주석에 작성자·검토자·불일치 해결 기록을 남기고 전체·문항별 canonical SHA-256을 별도 gold
  adjudication manifest로 봉인한다.
- `non_current_parser_provision_ids`, 기준일 population, 본문 SHA, qrel·reference 무결성과 승인 시간
  순서를 초기 preflight에서 검사한다.
- 50·200·1,000문항 checkpoint마다 M1 snapshot을 다시 확인한다. drift가 있으면 날짜별 population diff로
  영향 문항만 재검토하고 새 dataset·manifest를 만든다.
- final adjudication 직전부터 M4의 held-out 완료까지는 corpus publisher schedule을 잠시 중지하고, 시작
  직전 변경 bundle 없음 또는 동일 snapshot을 확인한다. D runner의 기존 experiment lock은 실행 중 변경을
  추가로 막는다.

완료 조건:

- 정확히 1,000문항이 `approved_gold`다.
- `fully_answerable`의 모든 supported facet에 직접 qrel이 있다.
- `partially_answerable`은 supported·unsupported facet과 `partial_answer_with_limits`를 모두 가진다.
- `clarification_required`는 needs-clarification facet, 빠진 사용자 사실과 `ask_clarifying_question`을 가진다.
- `unanswerable`은 qrels가 비어 있고 근거 부족 사유와 `insufficient_evidence`를 가진다.
- reference response의 action과 citation은 같은 문항의 answerability·직접 qrel과 일치한다.
- test qrels는 calibration 조정에 사용하지 않는다.
- gold preflight가 검색·NIM 호출 전에 통과한다.

### 다음 실행 순서 — 아직 미착수

1. 승인된 1,000문항에서 scenario family 10개 × 5문항의 pilot 작업표를 만든다.
2. 주석자·독립 검토자·불일치 판정 담당자의 역할과 annotation schema를 고정한다.
3. 외부 호출이 필요한 후보 pool을 만들기 전에 예상 NIM 호출 수와 비용 상한을 보고한다.
4. pilot 50문항을 독립 주석·검토·adjudication하고 answerability와 qrel 경계를 고정한다.
5. calibration을 200문항까지 확장하고 gold preflight를 통과한 뒤 test 800문항을 봉인해 제작한다.
6. 1,000문항 gold가 승인된 뒤에만 M3 실험 D1을 시작한다.

## M3 — 실험 D1: raw dense 검색 기준선

1. D1 metric과 D2 비교 변형·선택 규칙·threshold 산정법을 test 실행 전에 등록한다.
2. clean code provenance, approved gold, adjudication manifest, corpus snapshot과 NVIDIA 512차원 profile의
   initial·locked preflight를 통과한다.
3. calibration 문항별 raw provision 11개를 exhaustive exact cosine으로 조회하고 10위와 11위 동점이면
   실행을 실패시킨다.
4. Recall·HitRate·Precision·Direct Precision·MRR@10·nDCG@1/3/5/10·facet coverage를 계산한다.
5. calibration 결과로 raw 검색 오류만 분석하되 held-out D1 결과와 test qrels는 열지 않는다.
6. partial·clarification·unanswerable은 core 평균과 분리해 후보 false-positive와 필요한 근거의 회수만
   진단한다.
7. dataset·corpus·embedding profile·query plan·code SHA, 실제 순위, 지연과 NIM batch를 원자적 run
   artifact에 기록한다. 실패한 부분 결과는 성공 run으로 게시하지 않는다.

M3 calibration 출력은 별도 diagnostic schema·경로에 기록하며 최종 D 성공 run으로 부르지 않는다.
전체 approved gold와 held-out primary를 요구하는 기존 final runner 계약은 완화하지 않는다. 최종 D 성공
artifact는 M4에서 동결한 D1·D2를 함께 평가하도록 runner version을 확장해 한 번 게시한다.

질문 embedding은 같은 질문 SHA·모델·입력 유형·차원·축약·정규화 profile일 때만 D2에서 재사용한다.
실험 E는 동결한 D2 문맥을 입력받아 generation만 평가하며 재검색·재임베딩하지 않는다.

## M4 — 실험 D2: AI 입력 검색 문맥 확정

D1은 raw dense 검색 능력만 측정하므로 그대로 AI 문맥을 확정하지 않는다. D2는 D1 query embedding을
재사용하고 같은 frozen snapshot·실험 lock에서 운영과 같은 `raw 50 → 조문 중복 제거 → top 10`을 별도
DB read로 재현해 추가 NIM 비용 없이 production dense-path 문맥을 비교한다.

calibration에서 비교할 최소 변형:

- A: 현재 방식 — raw 50을 조문별로 중복 제거한 top 10에서 최고 leaf 하나씩, 최대 5개 조문·60,000자
- B: 같은 조문 top 10에서 선택 leaf의 조·항·호·목 계층 문맥을 복원
- B의 최대 조문 수 3개·5개와 문자 예산 30,000자·60,000자만 비교한다. 품질 gate를 통과한 조합 중
  실제 입력 token이 가장 적은 계약을 선택하고 필요하지 않은 추가 조합은 만들지 않는다.

다음 값을 함께 본다.

- Context/Evidence Recall과 Precision
- supported facet recall과 모든 supported facet 충족률
- 같은 조문 중복, 잘린 계층, 무관 조문 수
- 문맥 문자 수와 예상 입력 token·비용
- 범위 밖 날짜, 빈 후보, 부분 답변·추가 질문·근거 부족 사례

calibration 결과로 품질 임계값과 문맥 제한을 test 공개 전에 사전 등록한다. held-out 800문항에는 선택한
한 계약만 한 번 적용한다. 과거 6문항 실험의 `required_evidence_terms`는 평가 fixture일 뿐이므로 런타임
직접 근거 판정기로 재사용하지 않는다.

동결 산출물 `search-context-contract-v1`에는 다음을 기록한다.

- 입력 D run·gold·corpus·embedding profile SHA
- raw 후보 → 조문 중복 제거 → 계층 복원 → 문자 예산 → citation ID 부여 순서
- 후보 K, 최대 조문 수, 최대 문자 수와 잘림 규칙
- source·기준일·본문 SHA·중복·예산, parent/path 무결성과 원문 순서 hard gate
- citation ID와 실제 provision·source의 정확한 매핑. 이 매핑은 qrel을 런타임 입력으로 사용하지 않는다.
- 조문·항·호·목의 문자 중간 절단 금지. 단일 필수 구조 단위가 예산을 넘으면 일부를 자르지 않고
  `context_budget_exceeded`로 생성하지 않는다.
- `context_available | no_candidate | blocked_corpus_or_date | context_budget_exceeded` 관찰 상태
- 빈 후보와 unsupported date/corpus unready의 생성 금지 동작

gold의 answerability·facet·qrels·reference response는 오프라인 평가에만 사용한다. Production context
builder는 질문, DB 후보와 구조 메타데이터만 입력받는다. calibration에서 계약을 동결한 뒤 held-out D1과
D2를 함께 한 번 실행하며, primary는 test `fully_answerable`의 family macro와 bootstrap 95% 구간이다.

동결한 context assembler는 dense·직접 조문 경로·keyword fallback 후보에 공통 적용한다. D의 1,000문항
지표는 dense-path에만 계산하고, 직접 경로와 keyword fallback은 기존 고정 fixture로 계층·중복·인용·예산
계약만 저비용 통합 검증한다.

D2가 끝나면 프런트 날짜 범위 TODO를 `0002` 공개 Web 범위로 명시적으로 이관한 뒤 `0022`를 실제 D1·D2
결과와 함께 완료 처리한다.

## M5 — NVIDIA 답변 연결

NVIDIA adapter는 이미 있으므로 새 provider 계층을 만들지 않는다. 다음 최소 변경만 한다.

1. 생성 입력을 M4의 동결 문맥 package로 교체한다.
2. 답변 schema에 네 동작을 구분하는 안정 필드를 추가한다. 런타임에는 gold answerability를 전달하지
   않고 모델 출력과 결정적 gate의 동작을 실험 E에서 gold 기대 동작과 비교한다.
3. 생성 provider를 `nvidia_nim`으로 고정하고 OpenAI는 운영 비교·fallback으로 사용하지 않는다.
4. 모델·prompt·schema·context·sampling 설정과 SHA를 기록한다.
5. 현재 one-shot 생성 후 검증 실패 시 검색 전용 fallback을 유지한다. E에서 이득이 증명되기 전에는
   유료 재시도를 추가하지 않는다.
6. held-out을 열지 않도록 calibration 문항 소수의 bounded hosted smoke로 schema, timeout, provider
   error와 검색 전용 fallback만 먼저 확인한다.

실험 E 통과 전에는 Production AI를 기본 활성화하지 않는다.

## M6 — 실험 E: AI 답변 평가

실제 호출 전에 별도 active 실행 계획을 만들고 다음 계약과 release gate를 사전 등록한다.

### E0 — 외부 호출 없는 결정적 검사

- schema와 네 답변 동작
- citation ID·source URL·문서·버전·기준일·본문 SHA
- 인용 없는 claim·checklist 형식과 인용하지 않은 숫자·규범어 차단
- no evidence, corpus unready, unsupported date, provider 실패 fallback

unsupported facet, 의미상 claim support와 facet coverage는 gold가 있는 실험 E 지표다. 새 사용자 질문의
runtime 결정적 gate가 정답 facet을 안다고 가정하지 않는다.

### E1 — pilot 50문항

- M2.1 pilot과 같은 10 family × 5문항을 한 번 호출한다.
- pilot에 존재하는 answerability, 넓은 facet 질문과 경계 사례를 모두 포함한다. 네 상태 중 빠진 상태가
  있으면 calibration에서 해당 문항을 사전 봉인해 보충하고, 모집단 자체가 0이면 `not_applicable`로 기록한다.
- 문맥·prompt·sampling·gate 중 한 번에 하나만 고치고 원인을 기록한다.
- 50문항 전체를 독립 검토한다.
- E1 hard gate가 통과하지 않으면 E2·E3 호출을 시작하지 않는다.

### E2 — calibration 200문항

- calibration 전체를 한 번 실행한다.
- E1 뒤 model·prompt·schema·context·sampling이 바뀌지 않았다면 pilot 50개 출력은 재사용하고 나머지
  150개만 호출한다. 하나라도 바뀌면 같은 version 비교를 위해 200개를 다시 실행한다.
- expected action, claim support, citation correctness·coverage, supported facet coverage, 근거 없는 주장,
  fallback 정확도, provider 오류, p50/p95, token·비용을 기록한다.
- model·prompt·schema·context·sampling과 품질 임계값을 동결한다.
- E2의 사전 등록 gate가 통과하지 않으면 E3를 열지 않는다.

### E3 — held-out test 800문항

- 동결한 설정으로 한 번만 실행한다.
- test 결과를 보고 같은 version을 재튜닝하지 않는다. 변경이 필요하면 새 version으로 calibration부터
  다시 시작하되, 이미 연 800문항은 이후 regression set으로만 부른다. 독립 새 test set이 없으면 새
  unbiased held-out 성능이라고 주장하지 않는다.
- 반복성은 1,000개 전체를 반복하지 않고 미리 봉인한 calibration 10~20문항만 3회 실행해 action,
  citation과 핵심 claim의 변동률을 측정한다.

모든 문항은 결정적 검사를 적용한다. pilot 50문항, 사전 봉인한 held-out 표본, 자동 실패와 경계 사례는
독립 검토한다. 별도 LLM judge는 초기 버전에 추가하지 않는다. 추가 비용과 순환 평가 없이 부족한 경우에만
후속 실험으로 검토한다.

성공한 E run만 새 JSON으로 원자 게시한다. dataset·gold·D context·model·prompt·schema·sampling·code SHA,
실제 입력 context, raw structured response, 출력 action·citation, validator 결과, token·지연·비용,
provider request ID의 비민감 부분, provider 오류, 반복 실행 차이와 stdout SHA-256을 기록한다. 터미널 값을
수기로 옮긴 문서를 결과 원본으로 사용하지 않으며 실패한 부분 결과나 기존 성공 run을 덮어쓰지 않는다.

hard release gate:

- 존재하지 않거나 기준일·source·본문이 틀린 citation 0건
- 검토 표본의 근거 없는 중대 규범 주장 0건
- `corpus_unready`·unsupported date에서 생성 0건
- provider·schema·grounding 실패 시 검색 전용 fallback 100%

나머지 answer action, facet coverage와 답변 정확성 임계값은 E2 결과를 본 뒤 E3를 열기 전에 고정한다.

## M7 — 기존 활성 계획 합류와 해결

| 계획·Discord 항목 | 현재 실제 상태 | 처리 시점과 최소 비용 해결책 |
| --- | --- | --- |
| `0022` | 질문 승인 완료, gold·D 미완료 | M2~M4에서 완료 |
| `0008` / D-002 — 7/10 | 정확성 구현 완료, Production EXPLAIN·region/pool·재측정 미완료 | D2 뒤 `EXPLAIN → Vercel region/Supavisor pool 확인 → warm 300·cold 10 재측정`으로 병목을 분리한다. 1초 초과 원인이 DB 왕복일 때만 단일 함수화를 검토하고 회귀한다. 표본 수를 줄이려면 실행 전에 근거와 새 목표를 문서화한다. credential 부재 blocker는 낡은 기록으로 정리한다. |
| `0012` / D-004 — 2/17 | process-local 취소만 운영, 계획 문서에 polling·Qwen 표현이 남음 | E 통과 뒤 공개 AI 전에 NVIDIA+Supabase private Realtime Broadcast로 통일하고 migration·RLS·TTL, API 202/200/404/503, Web 상태, owner 격리와 2인스턴스를 검증한다. PostgreSQL 권위 행과 기존 Broadcast만 사용한다. E 실패로 AI를 공개하지 않으면 계속 active로 두거나 제품 범위 제외 결정을 별도 기록한다. |
| `0015` / D-009 — 15/19 | migration·로컬 함수 완료, 일 1회 scheduler·최초 감사 미완료 | 기존 self-hosted GitHub Actions runner에 짧은 일 1회 job을 추가해 반환 `failed`를 job 실패로 바꾼다. 새 유료 scheduler와 `pg_cron` 설치를 피한다. 운영 승인 뒤 최초 감사·경보만 확인한다. |
| D-005 NVIDIA | passage embedding·3,066개 DB vector와 key 사용은 확인, 생성 hosted 평가·정책 미완료 | M5~M6에서 frozen context smoke와 E를 실행한다. 데이터 처리·Trial/Production 정책 승인 전 공개 AI를 켜지 않는다. |
| `0002` — 21/38 | 기본 Web/API/DB/Auth 연결 완료, 생성·수명주기·공개 E2E 미완료 | M5~M8에서 NVIDIA 생성·quota 영속 상태·인용 gate·동일 출처 Preview·Storage/삭제/백업·공개 URL E2E를 마친다. 235개 연혁은 D 문항 기준일 또는 공개 과거 검색 범위에 필요할 때 이관하고, 그 전에는 검증하지 않은 과거 범위를 노출하지 않는다. |

문서 정상화 TODO:

- `0002`의 주 1회 수집과 직전 generation 보존 설명을 현재 일 1회 점검 게시 계약에 맞춘다.
- `0008`의 hybrid/RRF와 삭제된 rollback 설명을 현재 dense-only·keyword fallback 경계에 맞춘다.
- `0012`와 분산 취소 설계의 polling·Qwen/Ollama 설명을 Realtime Broadcast·NVIDIA로 맞춘다.
- `0015`의 migration 미적용 blocker를 실제 DB revision과 대조하고 scheduler만 미완료로 남긴다.
- Discord 전용 보드는 해당 Discord 작업을 다시 시작할 때만 같은 사실로 갱신한다.

## M8 — 설계 확정과 전체 검증

설계 확정 대상:

- gold·adjudication version
- D raw retrieval profile과 `search-context-contract-v1`
- NVIDIA model·prompt·schema·sampling과 answer gate
- E release threshold와 search-only fallback
- 운영 corpus 게시·취소·retention 계약

전체 검증:

1. Python API/core/collector unit·integration, Ruff와 migration 계약
2. Web lint·typecheck·unit·Production build
3. CI PostgreSQL publisher 5건과 retention 2건
4. D1 검색 회귀와 D2 context 회귀
5. E 저장 출력의 결정적 회귀와 release 전 bounded hosted smoke
6. 인용 원문·버전·기준일, 부분 답변·추가 질문·근거 부족, quota·provider·grounding fallback E2E
7. 인증·RLS·개인정보·질문 이력 삭제·Storage·백업 복구
8. 공개 AI를 활성화한다면 분산 취소의 서로 다른 두 API 인스턴스 검증
9. retention scheduler 첫 실행 감사와 실패 경보
10. Preview 동일 출처와 공개 URL 질문→답변/검색 전용→인용→이력→내보내기 종단 검증
11. 문서 검사와 clean diff, 기능별 commit·원격 CI

go/no-go 조건:

- D와 E의 사전 등록 gate가 모두 통과한다.
- 중대 인용·규범·기준일 오류가 0건이다.
- 운영 DB 통합 테스트 대체 실행이나 고의 장애 주입이 없다.
- 공개 AI 이전에 NVIDIA 데이터 처리·Trial/Production 조건, 개인정보 정책과 법률 전문가 표본을
  확인한다.
- 미완료 항목은 기능을 숨기거나 명시적으로 범위를 줄인 뒤에만 공개한다.

## 미결정 사항과 차단 요소

- D2의 최종 조문 수·문자 예산과 품질 threshold는 calibration 결과로 정하되 held-out 실행 전에 봉인한다.
- E의 action·facet·정확성 수치 gate는 E2로 정하되 E3 실행 전에 봉인한다.
- NVIDIA Production 사용 조건, 개인정보 정책과 법률 전문가 표본은 공개 AI의 외부 차단 요소다.
- 운영 corpus 게시, 분산 취소 migration과 retention schedule은 각각 별도 사용자 승인이 필요하다.
- 235개 연혁 이관 전에는 현재 저장 corpus가 실제로 검증한 날짜만 지원하며, 과거 범위 확대는 미결정이다.

## 검증과 롤백

- gold 또는 질문을 바꾸면 기존 파일을 덮어쓰지 않고 새 version과 manifest를 만든다.
- D2가 실패하면 현재 검색 전용 결과를 유지하고 AI 연결을 진행하지 않는다.
- E가 실패하면 `AI_MODE=off`를 유지하며 D의 검색 결과만 제공한다.
- corpus 게시가 실패하면 Tx B는 rollback되고 gate를 닫은 채 원인을 수정한다. 운영에서 rollback을
  시험하려고 고의 실패시키지 않는다.
- 0008·0012·0015·0002 변경은 서로 다른 기능 commit으로 분리해 각각 되돌릴 수 있게 한다.

## 결정 로그

- 2026-08-04: 질문 문구와 범위 1,000개 승인은 완료됐지만 gold 승인은 아니므로 실험 D 전에 독립
  qrels·기준 문맥·기준 응답과 adjudication을 필수로 둔다.
- 2026-08-04: 실험 D를 raw retrieval D1과 production dense-path context D2로 나눈다. 현재 D runner만으로
  AI 입력 문맥을 확정할 수 없기 때문이다.
- 2026-08-04: CI의 일회성 PostgreSQL에서 publisher·retention rollback을 검증하고 운영에서는 성공 게시와
  자연 실패 복구만 확인한다.
- 2026-08-04: 0008·0012·0015는 D/E 선행 조건으로 만들지 않는다. 정확성과 AI 가치가 확인된 뒤 공개
  운영에 필요한 최소 범위만 구현한다.
- 2026-08-04: E는 50 pilot, 200 calibration, 동결, 800 held-out 1회 순서로 실행하고 별도 LLM judge와
  자동 유료 retry는 초기 범위에서 제외한다.

## 진행 기록

- 2026-08-04: 질문 승인 manifest의 1,000개 ID·문구·범위 해시와 승인 범위를 읽기 전용으로 확인했다.
- 2026-08-04: M0를 다시 감사했다. 일반 사용자 질문은 1,000개 고유 ID·문구이며 승인 manifest와
  일치하고, `lay-energy-0084`, `lay-energy-0111`, `lay-energy-0511`도 요청 문구와 `approved` 상태를
  유지한다. 질문 승인 관련 테스트는 `36 passed`였고 전체 문항은 아직 `not_annotated`라 gold는
  `0/1,000`이다. `git fetch origin main` 뒤 원격 전용 커밋은 0개, 로컬 main의 미푸시 커밋은 12개임을
  확인했다. 이 단계에서는 DB·NIM·검색 실험을 실행하지 않았다.
- 2026-08-04: gold·pilot·실제 D/E가 아직 없고 NVIDIA answer adapter만 준비된 상태임을 확인했다.
- 2026-08-04: active 0002·0008·0012·0015와 누락된 0022, Discord 항목 D-002·D-004·D-005·D-009의
  실제 잔여 작업과 낡은 blocker를 대조했다.
- 2026-08-04: corpus-first, gold, D1/D2, NVIDIA, E, 운영 마무리 순서의 이 로드맵과 active index를
  문서화했다. 기능 구현·실험·DB·외부 호출은 실행하지 않았다.
- 2026-08-04: M1을 완료했다. draft PR #2의 CI에서 publisher PostgreSQL 5건을 skip 없이 포함한 전체
  검증이 통과했고, 운영 `DIRECT_URL`에서는 명시적 읽기 전용 preflight만 실행해 migration·gate·profile·
  3,066개 vector coverage와 snapshot을 확인했다. 운영 write·게시·실험 D는 실행하지 않았다.
- 2026-08-04: M2는 독립 주석 방법과 50→200→1,000 checkpoint만 확정했다. 작업표·annotation artifact·
  qrels·gold 코드는 만들지 않았다.

## 이번 로드맵 작성에서 하지 않은 일

- gold·pilot·Experiment D/E artifact 생성 또는 실행
- NVIDIA/Open API/Storage 호출
- 운영 DB 쓰기, migration, corpus 게시·점검 모드·검색 smoke
- M2 이후의 기능 코드·workflow·환경변수 변경
- Production `main` 병합·push·배포
