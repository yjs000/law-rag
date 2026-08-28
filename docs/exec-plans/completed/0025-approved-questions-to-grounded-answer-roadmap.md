# 실행 계획 0025: 승인 질문에서 근거 기반 AI 답변까지

상태: 완료(2026-08-18) — 사용자 판단으로 이 로드맵의 남은 범위(M6 실험 E-10 결과 반영,
M7 0008/0012/0015 합류, M8 설계 확정)가 더 이상 필요하지 않다고 결정해 종료한다. M0~M5는
완료했고, M7이 참조하던 0008·0015는 각각 필요 없음/scheduler 미도입으로 종료됐으며 0012는
설계 현행화 대기로 todo로 되돌아갔다. 0032(실험 E-10)는 이 로드맵과 무관하게 별도 active
계획으로 독립 유지한다.

원래 상태(진행 중, 2026-08-08 마지막 갱신): M0~M4 완료(2026-08-07, 승자 R1+A), M4.5(0028) tier
1/2 배선·fixture 라이브 평가 완료(2026-08-08, tier 2 자체 calibration은 후속 과제), M5 항목
1·2·3·4·5·6 실행 완료(2026-08-08, NVIDIA API key 실배선 + bounded hosted smoke 통과,
`answer_timeout_seconds` 30→60초 수정), M6(실험 E-10) 전 상태
작성일: 2026-08-04
소유자: 주 에이전트

## 목적과 사용자 결과

사용자 확인이 끝난 D-10 10문항을 동결한 소표본 calibration으로 검색과 AI 입력 문맥을 확정하고 NVIDIA
답변을 소규모 실험 E로 평가한다. 승인된 1,000문항은 보존하되 전체 Gold는 실제 일반화·운영 회귀가
필요할 때만 다시 원문 검토해 작성한다. 검증된 설계만 운영 경로에 반영하고,
남아 있는 활성 계획을 최소 비용 순서로 마친 뒤 전체 테스트와 공개 종단 검증을 수행한다.

이 문서는 여러 활성 계획의 순서와 합류 지점을 정하는 상위 로드맵이다. 세부 데이터 계약과 구현
체크리스트는 기존 실행 계획과 설계 문서가 계속 권위 원본이다.

## 범위와 비범위

범위:

- corpus 게시 준비 증명과 D 기준 snapshot 동결
- 사용자 확정 D-10 10문항 계약·artifact preflight
- 저장된 동일 top 10의 raw dense와 R1, production dense-path 문맥 조립 calibration
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
5. 현재 10문항은 calibration으로만 사용하고 held-out 성능으로 일반화하지 않는다. 한 번에 한 변수만
   바꾸며 정식 release gate가 필요해질 때만 별도 Gold를 만든다.
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
| D-10 동결 라벨 | 10문항 사용자 확인 완료 | 원래 raw top 10 한정 직접 근거·무관 top 5·문맥 판정, 정식 Gold 아님 |
| D-full Gold | 0/1,000 | 보존·보류, 필요 시 현재 corpus를 다시 검사해 작성 |
| D-10 calibration Gold | 10문항×3,066 전수 qrel draft 생성, 10/10 사용자 review 대기 | 승인·seal 전에는 Gold 완료나 지표를 주장하지 않음 |
| 실험 D | D-10 실제 run·R1·M3 calibration 완료, Gold sealed | M4 AI 입력 문맥 확정 전 |
| AI 입력 문맥 | 조문별 최고 leaf 1개, 최대 5개 조문·60,000자 | 계층 복원과 facet 충족을 평가하지 않은 임시값 |
| NVIDIA 생성 | adapter와 API 연결 코드는 존재 | hosted 답변 smoke·반복성·법률 품질·비용 미측정 |
| 실험 E | 계획·runner·산출물 없음 | D 문맥 동결 뒤 별도 설계 필요 |
| corpus publisher | draft PR CI에서 PostgreSQL 통합 5건 실행, 운영 DB 읽기 전용 preflight 통과 | 실제 변경 bundle 게시·점검 모드·검색 smoke는 미실행 |
| Git 상태 | `codex/corpus-publisher-preflight`, draft PR #2 | Production `main`에는 병합·push하지 않음 |

질문은행 파일의 `draft_for_human_question_review`와 문항의 `not_annotated`는 승인 실패가 아니다. 질문
승인은 별도 manifest에 있고, `not_annotated`는 정답 근거 주석이 아직 없다는 뜻이다.

## 튜닝 데이터와 측정 데이터

데이터·평가는 두 가지 다른 일을 한다: **튜닝**(시스템을 고치려고 반복해서 보는 것)과 **측정**(다 고친
뒤 실제로 좋아졌는지 정직하게 재는 것). 같은 문항으로 둘 다 하면 측정값이 항상 좋게 나오지만, 그건 그
문항에 맞춘 결과이지 일반적으로 좋아졌다는 증거가 아니다([Dwork 외 2015,
*Science*](https://www.science.org/doi/10.1126/science.aaa9375) — 같은 holdout을 반복 재사용하면 통계적
타당성이 매 라운드 저하됨을 formalize; [Google ML Crash
Course](https://developers.google.com/machine-learning/crash-course/overfitting) — "Don't train on test
data"). 이 로드맵은 모든 문항을 아래 두 계층 중 하나로 명확히 분류하고, 어느 마일스톤이 어느 계층에서
동작하는지 표시한다.

| 계층 | 현재 범위 | 반복 튜닝 | "일반적으로 좋다" 측정 주장 |
| --- | --- | --- | --- |
| **튜닝(calibration)** | D-10 10문항(확정) → D-full 재개 시 pilot 50 + calibration 200 | 허용 — 계속 보고 고친다 | 불가 |
| **측정(test)** | D-full 재개 시에만 존재하는 held-out 800문항 | 금지 — 한 번 확정하면 다시 안 본다 | 봉인 뒤 단 한 번만 |

**영구 규칙**: 어떤 문항이든 튜닝에 한 번 쓰이면 다시는 측정용으로 승격하지 않는다. D-10은 이미
D-10-R1 재정렬 설계에 쓰였으므로([M1.5](#m15--d-10-수동-진단) 참고) 영구히 calibration이며, 이후
20→50→...→1,000으로 늘려도 D-10을 포함하는 한 그 결과는 튜닝 신호일 뿐 측정값이 아니다. **이
로드맵(M0~M8)은 전부 튜닝 계층에서만 동작한다.** 측정 계층은 [예정 작업
0029](../todo/0029-d-full-gold-on-demand.md)가 active로 승격돼 test 800문항이 봉인된 뒤에만 존재하고,
그때도 E3 결과를 보고 같은 version을 재튜닝하지 않는다 — 필요하면 새 version으로 calibration부터
다시 시작한다(M6 "보존된 D-full E3" 참고).

## 선행 관계와 마일스톤

| 순서 | 마일스톤 | 결과물 | 다음 단계 진입 조건 | 데이터 계층 |
| ---: | --- | --- | --- | --- |
| M0 | 입력과 상태 감사 | 승인 manifest·active 계획 상태 확인 | 완료 | 인프라 |
| M1 (완료) | corpus 게시 준비 증명 | CI PostgreSQL 결과와 운영 비파괴 preflight | D·gold 기준 corpus가 DB에 확정됨 | 인프라 |
| M2 (완료) | D-10 계약 동결 | 10문항 판정·근거·run artifact manifest | 무호출 frozen preflight 통과 | 튜닝 |
| M3 (완료) | D-10 raw/R1 calibration | 저장 순위의 직접 근거·잡음 진단과 새 top 5 확인 | 완료(v3 Gold) — MRR@10 raw 0.525 → R1 0.60 | 튜닝 |
| M4 (완료) | D-10 AI 입력 문맥 확정 | 10문항 문맥 계약 v1 | 완료 — 승자 R1+A, hit 7/10 | 튜닝 |
| M4.5 (진행 중) | 검색 전 질문 라우팅 | clarification·realtime·external-document 경로와 검색 금지/재개 계약 | 라우팅 fixture와 비용 gate 통과 | 튜닝 |
| M5 | NVIDIA 답변 연결 | 동결 문맥 입력, 답변 동작·인용 gate | bounded hosted smoke 통과 | 인프라 |
| M6 | 실험 E-10 | 답변 품질·안전·비용·반복성 소표본 결과 | 사용자 확인, 일반 release gate로 사용 금지 | 튜닝(E-10) · 측정(D-full E3, 0029 활성화 시만) |
| M7 | 운영 잔여 계획 해결 | 0008·0012·0015와 0002 출시 항목 | 각 계획의 운영 증거 완료 | 인프라 |
| M8 | 설계 확정과 전체 검증 | 버전 고정·go/no-go 보고 | 중대 오류 0, 전체 gate 통과 | 인프라 + 튜닝 결과 종합 |

`인프라` 계층은 corpus·배포·연결 등 어느 문항 계층과도 무관한 운영 작업이다. M6의 실험 E-10 자체는
D-10 10문항을 쓰므로 튜닝이고, "보존된 D-full E1/E2/E3"만 0029 활성화 후 pilot 50·calibration
200(튜닝)·test 800(측정)으로 나뉜다.

핵심 경로는 `승인 질문 → corpus 확정 → D-10 수동 진단 → 10문항 계약 동결 → M3 raw/R1 → M4 문맥
→ 검색 전 라우팅 → NVIDIA → E-10 → 설계 확정`이다. D-full 자산은 삭제하지 않고 예정 작업 0029로
보류한다. 10문항 결과를 정식 Gold·held-out·release 지표로 부르지 않는다. 0008 검색
성능, 0012 분산 취소와 0015 scheduler는 D의 선행 조건이 아니다.

### M1.5 — D-10 수동 진단

완료된 [실행 계획 0026](../completed/0026-experiment-d-10-manual-review.md)과
[설계](../../design-docs/experiment-d-10-manual-review.md)를 따른다. 승인 질문 10개를 현재 DB의 오늘
population에서 exact dense로 한 번 검색하고, 같은 top 10으로 raw 직접 근거 순위와 복원 조문 문맥을
사람이 함께 판정한다. 정답·qrels를 미리 넣지 않으므로 D-full gold와 Recall 평가가 아니며, 사용자 확인이
끝날 때까지 진단 집계와 `docs/generated/` 결과 요약을 만들지 않는다. 2026-08-05 사용자 10/10 확인을
마쳤고, 후속 [D-10-R1 로컬 재정렬](../../design-docs/experiment-d-10-local-rerank.md)은 `0346` 직접 근거를
8위에서 2위로 이동시켰다. 같은 표본으로 R1을 설계했으므로 M3에서도 calibration으로만 사용한다.

## 담당과 검증 책임

| 마일스톤 | 담당 | 독립 검증 |
| --- | --- | --- |
| M1 | 주 에이전트·CI | publisher PostgreSQL 통합 결과와 운영 preflight diff 검토 |
| M2 | 주 에이전트 | 사용자 확정 판정·artifact SHA·범위의 무호출 preflight |
| M3~M4.5 | 검색 평가 담당 에이전트·사용자 | 새 top 5 원문 판정, 소표본 한계와 라우팅 비용 gate 감사 |
| M5~M6 | NVIDIA 연결·답변 평가 담당 에이전트 | 결정적 validator와 독립 표본 검토 |
| M7 | 각 active 계획의 DB/API/Web/운영 담당 | 계획별 focused test와 운영 증거 |
| M8 | 주 에이전트 | 전체 immutable diff, CI, 공개 E2E와 go/no-go |

각 구현 마일스톤은 관련 설계·운영 문서와 `docs/learning/` 기술 브리핑을 같은 기능 commit에서
갱신한다. 통합, staging과 commit은 주 에이전트가 담당한다.

## 사용자 승인 gate와 현재 차단 요소

- 현재 로드맵 작성과 읽기 감사에는 외부 차단 요소가 없다.
- 운영 `apply-prepared` 직전에는 update ID, bundle SHA, 기준 snapshot, 변경 문서·조문·vector 수와 예상
  점검 시간을 보고하고 별도 승인을 받는다.
- M2와 M3는 저장 artifact만 읽으며 외부 호출이 없다. M4 이후 새 embedding 또는 E 호출 전에는 예상
  호출 수·token·quota와 최대 비용을 계산해 승인된 상한 안에서만 실행한다.
- 운영 migration, 분산 취소, retention schedule과 공개 AI 활성화는 각각 별도 운영 승인 뒤 수행한다.
- D-full을 다시 활성화할 때만 final adjudication부터 held-out 완료까지 corpus publisher 중지 창을 별도
  운영 승인 대상으로 보고한다.
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

## M2 — D-10 10문항 평가 계약 동결 — 완료

2026-08-07 사용자 결정으로 1,000문항 Gold 제작을 필수 선행조건에서 제거했다. D-full 질문은행·승인
manifest·Gold schema와 runner는 [예정 작업 0029](../todo/0029-d-full-gold-on-demand.md)로 보존하며,
일반화·운영 회귀가 실제로 필요할 때만 질문을 현재 corpus에서 다시 검사해 정답 근거를 붙인다.

현재 M2는 `experiments/d_manual/experiment-d-10-m3-frozen-contract.json`에 질문 identity, 사용자 확정
판정, 원래 raw top 10 안의 직접 근거와 알려진 무관 top 5, D-10 run·corpus·profile과 원본 artifact
SHA-256을 동결한다. 다음 preflight는 파일을 쓰거나 DB·NVIDIA를 호출하지 않는다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_frozen_contract preflight
```

contract payload SHA-256은
`d25bcd2ab00428515797d34a301b13dd73acb5809833de89289093056ae1af2e`다. question count 10, corpus
provision 3,066, 외부 호출 0회로 실제 로컬 artifact preflight를 통과했다. 이 계약은 raw top 10 한정
사용자 확인셋이며 독립 주석·전체 qrels·reference answer가 없어 정식 Gold가 아니다.

### 보존된 D-full 설계 — 현재 보류

gold는 질문 승인 manifest의 canonical payload SHA-256
`d41f6a206fec705a2e99b2b9543a6472cd5c5c067fc3a2a530e31a9a08fde869`에 결박한다. 실제 JSON 파일 byte
SHA-256 `19b1e40704d38a56751cf7a539a39075af18d1e5bbed8e47b1a3b00dabf82f31`과 역할을 섞지 않는다.

#### D-full 50문항 pilot

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

#### D-full 전체 1,000문항

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

#### D-full 재활성화 시 실행 순서

1. 승인된 1,000문항에서 scenario family 10개 × 5문항의 pilot 작업표를 만든다.
2. 주석자·독립 검토자·불일치 판정 담당자의 역할과 annotation schema를 고정한다.
3. 외부 호출이 필요한 후보 pool을 만들기 전에 예상 NIM 호출 수와 비용 상한을 보고한다.
4. pilot 50문항을 독립 주석·검토·adjudication하고 answerability와 qrel 경계를 고정한다.
5. calibration을 200문항까지 확장하고 gold preflight를 통과한 뒤 test 800문항을 봉인해 제작한다.
6. 이 절차는 예정 작업 0029가 active로 승격된 경우에만 실행하며 현재 M3의 선행조건이 아니다.

## M3 — D-10 raw/R1 소표본 calibration — 완료(2026-08-07, v3 Gold 기준 재계산)

1. [x] M2 frozen preflight를 통과한다. (0026/0027 완료 당시 통과, 2026-08-05)
2. [x] 원본 D-10 raw top 10과 cosine 순서를 baseline으로 읽는다. 새 query embedding·DB 검색은 하지 않는다.
   ([0026](../completed/0026-experiment-d-10-manual-review.md) `result.json` 재사용, 새 호출 0회)
3. [x] 사용자 확정 라벨로 manual hit@1/3/5/10, 첫 직접 근거 순위, manual reciprocal rank@10, 알려진 무관
   top 5와 문맥 판정 수만 계산한다. **v3 Gold**(`d10-gold-20260807t065254073895z`, [0030 v3 추가
   기록](../completed/0030-d-10-full-corpus-qrels-adjudication.md#v3-추가-기록--2026-08-07-완료-이후-정정)
   참고) 기준 raw hit@1/3/5/10 `5/5/5/7`(/10), MRR@10 `0.5250`, known irrelevant@5 `37`.
4. [x] 같은 후보 집합의 R1 순서를 비교해 `0346`의 8위→2위, hit@3/5 변화와 순위가 나빠진 사례를 함께
   본다. R1 hit@1/3/5/10 `5/7/7/7`(/10), MRR@10 `0.6000`, known irrelevant@5 `34`. **나빠진 문항 0건.**
5. [x] R1 새 top 5에 들어온 원래 6~10위 미판정 후보를 Codex가 원문 검토하고 사용자가 승인·수정·보류한다.
   9개 후보(6문항)를 개별 원문·facet 대조로 재검토했다 — 7건은 v1/v2 relevance 0이 맞았고, 2건
   (`0601`의 `9c93a34b`·`7cd6894f`)은 오채점이라 v3로 정정했다.
6. [x] 질문별로 baseline 유지, R1 사용 후보, 라우팅 우선, 추가 문맥 필요 중 하나를 기록한다. `0201`·
   `0251`·`0521`·`0601`·`0111` 5문항은 baseline=R1 동일(모두 1위), `0346`·`0561` 2문항은 R1 사용
   (8위→2위), `0605`/`0836`/`0943`은 순위 문제가 아니라 corpus에 positive qrel 자체가 없어 M4.5
   라우팅 대상.
7. [x] `docs/generated/` 요약을 만들되 기존 D-10/R1 artifact는 덮어쓰지 않는다.
   [experiment-d-10-m3-calibration-summary.md](../../generated/experiment-d-10-m3-calibration-summary.md)
   — 별도 원자 JSON(SHA 결박 스크립트)은 만들지 않고 기존 0026/0027 artifact와 0030 v3 sealed
   judgments.jsonl을 재계산 없이 읽어 조합했다. D-full 재개 등으로 이 패턴을 반복해야 하면 그때
   전용 스크립트로 formalize한다.

**최초 발행 수치(0026 기준, raw `6/6/6/7`·MRR `0.6125`)는 부정확했다** — 0026의 "직접 근거" 판정이
project relevance-2 정의보다 느슨해서(배경 맥락도 포함) `0561`을 실제로는 8위인데 1위로 과대평가했다.
반대로 `0601`은 v1/v2 Gold 초안이 raw·R1 top 1위 후보(`9c93a34b`)를 일괄 무관 처리로 놓쳐서 과소평가돼
있었다. 두 오차가 부분 상쇄돼 최종 수치(raw MRR `0.525`)가 최초 발행값(`0.6125`)보다 낮다. 왜 놓쳤고
다음 평가에서 뭘 볼지는 [design doc 회고
절](../../design-docs/experiment-d-10-gold-adjudication.md#회고--v1에서-놓친-것과-다음-평가에서-고려할-점)에
정리했다.

`lay-energy-0346`의 0030 Gold 정정(`approved_use_terms` relevance 1→2)은 raw/R1 top 10 후보 집합
어디에도 없는 provision이라 이 calibration의 입력이 아니다 — 계약 정합성 정정일 뿐 위 수치에 영향이
없다.

M3는 같은 10문항을 보며 R1을 만든 calibration이다. `known irrelevant@5` 감소는 새 후보 판정 전 실제
Precision 개선으로 해석하지 않으며 Evidence Recall·nDCG·facet·held-out·population 성능을 계산하지 않는다.
결과만으로 운영 검색 순서를 바꾸거나 Production AI release를 승인하지 않는다.

## M4 — 실험 D2: AI 입력 검색 문맥 확정 — 완료(2026-08-07)

M3 raw 순위만으로 AI 문맥을 확정하지 않는다. M4는 frozen D-10 result의 raw top 10과 이미 복원된 부모
조문을 읽고 baseline 또는 R1 순서에서 문맥을 조립한다. 새 query embedding·DB read 없이 같은 10문항의
AI 입력 후보를 비교한다.

### 검증 무게 원칙 — 튜닝과 확정 산출물을 구분한다

D-10 Gold를 v1→v2→v3로 고칠 때마다 매번 새 draft·seal·SHA·design doc 회고·M3 재계산을 전부 다시
했다. 이건 [플랜의 튜닝/측정 원칙](#튜닝-데이터와-측정-데이터)("튜닝은 반복해서 봐도 된다")을
문서로만 선언하고 실제 실행에서는 release-gate급 무게를 튜닝 단계에도 그대로 쓴 것이다. 앞으로는
다음처럼 구분한다.

- **튜닝(calibration) 라운드**: 판정 기준(relevance 2 정의 등)이 이미 확정된 뒤 나오는 개별 라벨
  수정은 seal·새 draft-id·전체 재문서화를 매번 반복하지 않는다. 가벼운 수정 기록(표 형태 changelog
  한 줄)만 남기고, 그 수정이 이미 발행한 결론(M3 승자, M4 승자 등)을 실제로 뒤집을 때만 해당 결론
  절만 갱신한다.
- **확정 산출물(release-gate급 무게 유지)**: (1) M4의 `search-context-contract-v1`처럼 이후
  단계(M5~)가 그대로 가져다 쓰는 동결 계약, (2) [예정 작업 0029](../todo/0029-d-full-gold-on-demand.md)의
  D-full held-out(test) 단계. 이 두 곳만 seal·SHA 결박·decision log 수준을 유지한다.
- D-10 Gold 자체(v3)는 계속 calibration 데이터이므로, 앞으로 추가 오류를 발견해도 v4 seal
  라운드를 새로 만들지 않는다 — draft judgments를 가볍게 고치고 changelog만 남긴다.
- **rubric 버전과 판정(calibration) 버전을 구분한다.** `0601`처럼 "relevance 2의 정의는 안 바뀌었는데
  개별 판정이 틀렸던" 정정은 같은 rubric(`relevance-v1`) 안의 calibration 수정이지 새 rubric
  version이 아니다. 반대로 "배경 맥락도 2로 친다" → "facet을 직접 서술해야 2"처럼 **relevance 2의
  정의 자체**가 바뀌는 경우만 `relevance-v2`로 승격한다. v1→v2→v3 draft-id는 전부 `relevance-v1`
  아래의 calibration 수정이었다 — 이 구분을 몰라서 매번 "새 rubric이 나온 것처럼" 전체를
  재문서화했다.

### raw/R1과 A/B는 서로 다른 축이다

- **raw/R1(순위)** — 후보 10개를 어떤 순서로 줄 세우나. raw는 NVIDIA dense cosine 유사도 실제 검색
  1회(M2), R1은 같은 후보를 법령명·복원된 부모 조문 표제·직접성 규칙으로 재정렬한 결과(외부 호출
  0회). M3에서 이미 비교·확정했다: 5문항은 raw==R1(1위 동일), `0346`·`0561` 2문항은 R1이 8위→2위로
  개선했고 나빠진 문항은 없다.
- **A/B(조립)** — 그 순위에서 고른 조문을 AI에게 어떤 형태로 넣어주나.
  - A(현재 방식): raw top 10을 조문별로 중복 제거하고 **조문당 최고 leaf 1개만** 사용, 최대 5개
    조문·60,000자 고정.
    A는 "정답 leaf 한 조각만" 주므로 짧고 싸지만, 그 조각이 `제1항에 따른`처럼 상위 조문 맥락이 있어야
    이해되는 경우 맥락을 놓칠 수 있다.
  - B(계층 복원): 같은 top 10에서 고른 leaf의 **조·항·호·목 계층 전체**를 복원해 함께 넣는다. 최대
    조문 수(3·5개) × 문자 예산(30,000·60,000자) 조합으로 4개 변형이 있다.
    B는 맥락 손실을 줄이지만 문자 수·비용이 늘어난다.
  - A/B는 M3와 달리 아직 코드도 비교 결과도 없다 — 이번 M4에서 처음 만든다.

calibration에서 비교한 변형(전부 실행 완료, [요약](../../generated/experiment-d-10-m4-context-assembly-summary.md)):

- [x] A: 현재 방식 — raw top 10을 조문별로 중복 제거하고 최고 leaf 하나씩 최대 5개 조문·60,000자
- [x] B: 같은 조문 top 10에서 선택 leaf의 조·항·호·목 계층 문맥을 복원, 최대 조문 수(3·5개) × 문자
  예산(30,000·60,000자) 4개 변형
- [x] raw × R1 × {A, B×4} = 10개 조합을 전부 계산했다. **결과: B는 어떤 설정으로도 A보다 hit이 늘지
  않고 토큰만 2~3배 더 썼다** — hit 여부는 "어떤 조문을 고르나"(순위)에 달려 있지 "얼마나 상세히
  주나"(조립)에 달려 있지 않았다. budget_exceeded 0건.
- [x] 승자: **R1 + A(최대 5개 조문·60,000자)** — hit 7/10(raw는 5/10), 평균 371 근사 토큰으로 비교
  조합 중 가장 적다. "품질 gate 통과 + 토큰 최소" 규칙 그대로 적용한 결과다.

다음 값을 확인했다: 직접 근거 포함 여부와 첫 포함 순위, 같은 조문 중복(0건), 문맥 문자 수·예상
토큰, `sufficient|insufficient|blocked`와의 일치(참고용, 승자 선택 기준 아님). 범위 밖 날짜·빈 후보
사례는 이 10문항에 해당 사례가 없어 관찰하지 못했다 — 실제 운영 코드 구현 시 별도로 확인한다.

10문항 결과로 문맥 제한을 고정하되 held-out 검증이나 일반 성능으로 부르지 않는다. 과거 6문항 실험의
`required_evidence_terms`와 D-10 직접 근거 ID는 평가 라벨일 뿐 런타임 판정기로 재사용하지 않는다.

### `search-context-contract-v1` — 문서 동결(코드 동결 아님)

위 "검증 무게 원칙"에 따라 이번엔 Pydantic 스키마·SHA 결박 스크립트를 새로 만들지 않고, 계약
파라미터를 이 문서에 확정하는 것으로 동결을 대신한다. 실제 운영 context builder 구현은 M5(NVIDIA
연결) 착수 시점으로 미룬다.

| 항목 | 확정값 |
| --- | --- |
| 순위 입력 | R1(`d10-parent-heading-directness-v1`) |
| 조립 방식 | A — 조문별 최고 leaf 1개 |
| 최대 조문 수 | 5개 |
| 최대 문자 수 | 60,000자 |
| 조립 순서 | raw 후보 → 조문 단위 중복 제거(우선순위: R1 순위) → 문자 예산 적용 → citation ID 부여 |
| 잘림 규칙 | 조·항·호·목 단위 중간 절단 금지 — 예산 초과 시 그 조문은 건너뛰고 `context_budget_exceeded`로 표시(생성 금지 아님, 다음 조문으로 진행) |
| 관찰 상태 | `context_available` \| `no_candidate` \| `blocked_corpus_or_date` \| `context_budget_exceeded` |
| citation ID 매핑 | citation ID는 실제 provision_id·source에 1:1 매핑한다. qrel은 런타임 입력으로 사용하지 않는다(오프라인 평가 전용) |
| 입력 결박(M5 구현 시 SHA로 기록) | D-10 frozen contract, 0026 run, 0030 v3 sealed corpus, NVIDIA embedding profile |

D-10 answerability와 직접 근거 ID는 오프라인 평가에만 사용한다. Production context builder는 질문,
DB 후보와 구조 메타데이터만 입력받는다. 10문항 문맥 계약은 다음 NVIDIA E-10 입력을 고정하지만 일반
release gate가 아니다.

동결한 context assembler의 순수 계층·중복·인용·예산 계약은 dense·직접 조문 경로·keyword fallback
fixture에 공통 검증할 수 있다. 다만 10문항 calibration만으로 운영 후보 순서 변경을 자동 승인하지 않는다.

M4가 끝나면 프런트 날짜 범위 TODO를 `0002` 공개 Web 범위로 명시적으로 이관한다. `0022`의 D-full
Gold·정식 runner 범위는 예정 작업 0029로 보류한다.

## M4.5 — 검색 전 질문 라우팅 — 진행 중([0028](0028-pre-retrieval-question-routing.md), 착수 2026-08-07)

D-10에서 법령 corpus로 직접 답할 질문, 사용자 사실이 필요한 질문, 실시간 정보와 사용자 문서가 필요한
질문이 섞이면 무관 법령을 AI 문맥으로 보낼 수 있음이 확인됐다. 질문 embedding과 법령 검색 전에 다음
경로를 판정하는 라우터를 별도 구현·평가한다. 세부 계약·8단계 구현 계획·fixture는
[0028](0028-pre-retrieval-question-routing.md)이 갖고 있다.

- `clarification_required`: 위치·설비용량·자가소비·판매 방식 등 빠진 사용자 사실을 먼저 묻고, 필요한
  답을 받기 전에는 query embedding과 법령 검색을 시작하지 않는다.
- `realtime_required`·`external_document_required`: 시스템은 질문 text와 법령 corpus만 입력받는다
  (2026-08-07 사용자 결정) — 실시간 source 연동이나 문서 업로드를 만들지 않고, 결정적 차단 메시지로
  끝낸다(embedding·검색·LLM 호출 0회).
- 그 밖의 법령 질문만 D1/D2의 동결 검색·문맥 경로(M4 승자: R1+A)로 보낸다.

라우터 자체는 결정적 규칙 → D-10 근접 예시 embedding 비교 → 소형 LLM classifier(tier 2 힌트 포함)
3단계로, LLM 호출을 corpus 크기가 아니라 모호함의 크기에 비례시킨다. clarification의 최소비용
기본안은 서버가 이전 질문과 추가 사실을 자동 병합하는 것이 아니라, 원 질문과 누락 필드가 들어간
복사용 완성 질문 템플릿을 결정적으로 반환하고 사용자가 다음 메시지에 새 독립 질문으로 다시 보내게
하는 것이다.

라우팅은 질문 ID나 D-10 정답을 런타임 규칙으로 넣지 않는다. route, 이유 코드, 필요한 추가 사실·자료,
embedding/search 실행 여부를 기록하고 동결 10문항의 partial·clarification·corpus 밖 사례에서 오분류와
불필요 검색을 진단한다. 일반 오분류율은 D-full을 다시 활성화하기 전에는 주장하지 않는다.

query 보강은 라우팅보다 뒤의 조건부 TODO다. 라우팅 결과가 법령 검색이고 동결 dense·문맥 경로가 여전히
직접 근거를 충분히 앞에 놓지 못할 때만 원 질문과 보강 문구를 별도 version·SHA로 고정한다. D-10의 같은
10문항 query embedding을 한 batch로 최대 한 번 다시 만들고, 기존 3,066개 passage vector와 동일
snapshot/profile을 재사용한다. passage embedding, 새 corpus, realtime/external-document 질문의 억지 법령
검색은 수행하지 않는다. 기존 D-10/D-10-R1 artifact를 덮어쓰지 않고 별도 비교 run으로 기록한다.

## M5 — NVIDIA 답변 연결 — 완료(2026-08-08)

NVIDIA adapter는 이미 있으므로 새 provider 계층을 만들지 않는다. 다음 최소 변경만 한다.

1. 생성 입력을 M4의 동결 문맥 package로 교체한다.
2. 답변 schema에 네 동작을 구분하는 안정 필드를 추가한다. 런타임에는 D-10 판정을 전달하지 않고 모델
   출력과 결정적 gate의 동작을 E-10에서 사용자 확정 기대 동작과 비교한다.
3. 생성 provider를 `nvidia_nim`으로 고정하고 OpenAI는 운영 비교·fallback으로 사용하지 않는다.
4. 모델·prompt·schema·context·sampling 설정과 SHA를 기록한다.
5. 현재 one-shot 생성 후 검증 실패 시 검색 전용 fallback을 유지한다. E에서 이득이 증명되기 전에는
   유료 재시도를 추가하지 않는다.
6. 동결 10문항 중 최소 표본의 bounded hosted smoke로 schema, timeout, provider error와 검색 전용
   fallback만 먼저 확인한다.

실험 E 통과 전에는 Production AI를 기본 활성화하지 않는다.

## M6 — 실험 E-10: AI 답변 소표본 평가 — 계획 확정(2026-08-08, [0032](../active/0032-experiment-e-10-ai-answer-evaluation.md))

실제 호출 전에 별도 active 실행 계획을 만들고 10문항의 호출 수·비용·판정표를 사전 등록한다. E-10은
사용자 확인 진단이며 일반 release gate가 아니다. 10문항 밖 품질 일반화가 필요하면 예정 작업 0029를
먼저 활성화한다.

**2026-08-08**: 위 요구사항에 따라 [0032](../active/0032-experiment-e-10-ai-answer-evaluation.md)를 만들어
E0 + D-10 기반 E-10 base(최대 12회 NVIDIA 호출, 무료 티어)로 범위를 확정하고 안전 gate를
사전 등록했다. E1/E2/E3(D-full 50/200/800)는 0029 미착수라 범위 밖. 실제 실행은 사용자 승인
대기 중이다.

### E0 — 외부 호출 없는 결정적 검사

- schema와 네 답변 동작
- citation ID·source URL·문서·버전·기준일·본문 SHA
- 인용 없는 claim·checklist 형식과 인용하지 않은 숫자·규범어 차단
- no evidence, corpus unready, unsupported date, provider 실패 fallback

unsupported facet, 의미상 claim support와 facet coverage는 gold가 있는 실험 E 지표다. 새 사용자 질문의
runtime 결정적 gate가 정답 facet을 안다고 가정하지 않는다.

### 보존된 D-full E1 — pilot 50문항

- 보존된 D-full 50문항 pilot의 10 family × 5문항을 한 번 호출한다.
- pilot에 존재하는 answerability, 넓은 facet 질문과 경계 사례를 모두 포함한다. 네 상태 중 빠진 상태가
  있으면 calibration에서 해당 문항을 사전 봉인해 보충하고, 모집단 자체가 0이면 `not_applicable`로 기록한다.
- 문맥·prompt·sampling·gate 중 한 번에 하나만 고치고 원인을 기록한다.
- 50문항 전체를 독립 검토한다.
- E1 hard gate가 통과하지 않으면 E2·E3 호출을 시작하지 않는다.

### 보존된 D-full E2 — calibration 200문항

- calibration 전체를 한 번 실행한다.
- E1 뒤 model·prompt·schema·context·sampling이 바뀌지 않았다면 pilot 50개 출력은 재사용하고 나머지
  150개만 호출한다. 하나라도 바뀌면 같은 version 비교를 위해 200개를 다시 실행한다.
- expected action, claim support, citation correctness·coverage, supported facet coverage, 근거 없는 주장,
  fallback 정확도, provider 오류, p50/p95, token·비용을 기록한다.
- model·prompt·schema·context·sampling과 품질 임계값을 동결한다.
- E2의 사전 등록 gate가 통과하지 않으면 E3를 열지 않는다.

### 보존된 D-full E3 — held-out test 800문항

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

E-10 필수 안전 gate:

- 존재하지 않거나 기준일·source·본문이 틀린 citation 0건
- 검토 표본의 근거 없는 중대 규범 주장 0건
- `corpus_unready`·unsupported date에서 생성 0건
- provider·schema·grounding 실패 시 검색 전용 fallback 100%

나머지 answer action, facet coverage와 답변 정확성 임계값은 D-full을 활성화한 경우에만 E2 결과를 본 뒤
E3 전에 고정한다. E-10에서는 문항별 사용자 판정만 기록한다.

## M7 — 기존 활성 계획 합류와 해결

| 계획·Discord 항목 | 현재 실제 상태 | 처리 시점과 최소 비용 해결책 |
| --- | --- | --- |
| `0022` | 검색 인프라·질문 승인 완료, D-full Gold 보류 | 10문항 M3/M4와 분리하고 Gold는 예정 작업 0029에서 필요 시 재개 |
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

- D-10 frozen contract와 사용자 확인 version
- D raw retrieval profile과 `search-context-contract-v1`
- NVIDIA model·prompt·schema·sampling과 answer gate
- E release threshold와 search-only fallback
- 운영 corpus 게시·취소·retention 계약

전체 검증:

1. Python API/core/collector unit·integration, Ruff와 migration 계약
2. Web lint·typecheck·unit·Production build
3. CI PostgreSQL publisher 5건과 retention 2건
4. D-10 M3 검색 진단과 M4 context 회귀
5. E-10 저장 출력의 결정적 회귀와 공개 전 bounded hosted smoke
6. 인용 원문·버전·기준일, 부분 답변·추가 질문·근거 부족, quota·provider·grounding fallback E2E
7. 인증·RLS·개인정보·질문 이력 삭제·Storage·백업 복구
8. 공개 AI를 활성화한다면 분산 취소의 서로 다른 두 API 인스턴스 검증
9. retention scheduler 첫 실행 감사와 실패 경보
10. Preview 동일 출처와 공개 URL 질문→답변/검색 전용→인용→이력→내보내기 종단 검증
11. 문서 검사와 clean diff, 기능별 commit·원격 CI

go/no-go 조건:

- D-10과 E-10의 사전 등록 안전 gate가 통과한다. 이는 일반 검색·답변 성능의 통계적 release 증거가 아니다.
- 10문항만으로 공개 AI의 일반 품질을 승인하지 않는다. 공개 범위를 결정할 때는 제한 beta 범위를 별도
  승인하거나 예정 작업 0029의 Gold·회귀 gate를 먼저 활성화한다.
- 중대 인용·규범·기준일 오류가 0건이다.
- 운영 DB 통합 테스트 대체 실행이나 고의 장애 주입이 없다.
- 공개 AI 이전에 NVIDIA 데이터 처리·Trial/Production 조건, 개인정보 정책과 법률 전문가 표본을
  확인한다.
- 미완료 항목은 기능을 숨기거나 명시적으로 범위를 줄인 뒤에만 공개한다.

## 미결정 사항과 차단 요소

- M4의 최종 조문 수·문자 예산은 10문항 사용자 확인으로 정하며 일반 품질 threshold는 D-full 전 미결정이다.
- E-10은 문항별 사용자 판정을 기록하고 일반 action·facet·정확성 수치 gate는 D-full 전 미결정이다.
- NVIDIA Production 사용 조건, 개인정보 정책과 법률 전문가 표본은 공개 AI의 외부 차단 요소다.
- 운영 corpus 게시, 분산 취소 migration과 retention schedule은 각각 별도 사용자 승인이 필요하다.
- 235개 연혁 이관 전에는 현재 저장 corpus가 실제로 검증한 날짜만 지원하며, 과거 범위 확대는 미결정이다.

## 검증과 롤백

- frozen contract·Gold 또는 질문을 바꾸면 기존 파일을 덮어쓰지 않고 새 version과 manifest를 만든다.
- D2가 실패하면 현재 검색 전용 결과를 유지하고 AI 연결을 진행하지 않는다.
- E가 실패하면 `AI_MODE=off`를 유지하며 D의 검색 결과만 제공한다.
- corpus 게시가 실패하면 Tx B는 rollback되고 gate를 닫은 채 원인을 수정한다. 운영에서 rollback을
  시험하려고 고의 실패시키지 않는다.
- 0008·0012·0015·0002 변경은 서로 다른 기능 commit으로 분리해 각각 되돌릴 수 있게 한다.

## 결정 로그

- 2026-08-07: D-10 Gold를 v1→v2→v3로 고칠 때마다 매번 seal·새 draft-id·전체 재문서화를 반복한 게
  튜닝 단계에 release-gate급 무게를 잘못 적용한 것이라는 사용자 지적에 따라, 검증 무게를 계층별로
  차등화했다. calibration 라벨 수정은 가벼운 changelog로, seal·SHA·decision log 수준은 확정
  산출물(M4 계약, 0029 D-full held-out)에만 쓴다.
- 2026-08-04: [대체됨] 질문 문구와 범위 1,000개 승인은 완료됐지만 gold 승인은 아니므로 실험 D 전에
  독립 qrels·기준 문맥·기준 응답과 adjudication을 필수로 뒀다. 2026-08-07 소표본 계약으로 대체했다.
- 2026-08-04: 실험 D를 raw retrieval D1과 production dense-path context D2로 나눈다. 현재 D runner만으로
  AI 입력 문맥을 확정할 수 없기 때문이다.
- 2026-08-04: CI의 일회성 PostgreSQL에서 publisher·retention rollback을 검증하고 운영에서는 성공 게시와
  자연 실패 복구만 확인한다.
- 2026-08-04: 0008·0012·0015는 D/E 선행 조건으로 만들지 않는다. 정확성과 AI 가치가 확인된 뒤 공개
  운영에 필요한 최소 범위만 구현한다.
- 2026-08-04: [보류] D-full E는 50 pilot, 200 calibration, 동결, 800 held-out 1회 순서로 설계했다.
  2026-08-07 현재 범위는 E-10 사용자 확인 진단이다.
- 2026-08-05: D-10 후속 개선으로 검색 전 clarification·realtime·external-document 라우팅을 M4.5 TODO로
  둔다. query 보강과 D-10 질문 embedding 10개 재실행은 라우팅 뒤 법령 검색 질문이 여전히 부족할 때만
  한 batch로 허용하며 passage embedding과 원본 artifact 변경은 하지 않는다.
- 2026-08-07: 1,000문항 Gold를 필수 선행조건에서 제거하고 필요 시 예정 작업 0029에서 재개한다. 사용자
  요청에 따라 D-10 10문항만 [활성 계획 0030](../completed/0030-d-10-full-corpus-qrels-adjudication.md)에서 전수 qrel과
  사용자 adjudication 대상으로 만들며, 승인 전에는 기존 top-10 한정 M2 계약을 유지한다.
- 2026-08-07: 사용자가 "10문항 결과가 좋아지면 검색기가 실제로 좋아진 것 아니냐"고 질의해 튜닝
  (calibration)과 측정(test)의 차이를 명시적으로 문서화하도록 요청했다. 기존 D-full E1/E2/E3(50 pilot·
  200 calibration·800 held-out) 설계가 이미 이 구분을 담고 있었으므로 새로 설계하지 않고, `## 튜닝
  데이터와 측정 데이터` 절과 마일스톤 표의 `데이터 계층` 열로 표면화했다. D-10은 이미 D-10-R1 튜닝에
  쓰였으므로 영구히 calibration이며, 문항 수를 늘려도(20→50→...) 별도 봉인된 held-out 없이는 측정
  주장으로 승격되지 않는다는 규칙을 명문화했다. 근거: Dwork 외(2015, *Science*) "The Reusable
  Holdout"과 Google ML Crash Course의 train/test 분리 원칙.
- 2026-08-07: clarification은 자동 turn 병합·slot 저장 대신 원 질문과 추가 정보를 한 메시지로
  복사·보완해 재제출하도록 안내하는 최소비용 방식을 기본안으로 정했다. 구현은 예정 작업 0028로
  계속 보류하며 현재 API·Web·검색 동작은 변경하지 않았다.

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
- 2026-08-05: D-10과 D-10-R1 결과를 근거로 검색 전 질문 라우팅과 조건부 query 보강을 후속 TODO로
  등록했다. 코드, embedding, DB·외부 source 호출은 실행하지 않았다.
- 2026-08-07: D-10 frozen manifest와 무호출 preflight를 추가해 question count 10, 3,066 provision
  snapshot, NVIDIA profile, 사용자 판정과 다섯 artifact SHA를 검증했다. M3 검색·외부 호출은 실행하지 않았다.
- 2026-08-07: D-10 10문항을 현재 3,066 provision 전체와 대조한 30,660개 qrel draft를 만들었다.
  0251·0521의 근거 있음과 추가 사실·corpus 부족 경계를 문서화했으며, 현재 10문항 모두 사용자
  adjudication 대기라 M3와 Gold seal은 실행하지 않았다.
- 2026-08-07: [0030](../completed/0030-d-10-full-corpus-qrels-adjudication.md)에서 `0346`의 `approved_use_terms`
  relevance 오채점(1→2)을 사용자 지적으로 정정한 v2 proposal·draft를 만들고 10문항 모두 confirm한 뒤
  seal했다(`preflight-sealed` → `valid_approved_calibration_gold`). 이어서 M3를 실행했다 — 기존
  0026/0027 raw/R1 artifact를 새 DB·embedding 호출 없이 재사용해 raw hit@1/3/5/10 `6/6/6/7`, MRR@10
  `0.6125`, R1 hit@1/3/5/10 `6/7/7/7`, MRR@10 `0.65`, known irrelevant@5 `28→18`을 계산했다. R1이
  새로 끌어올린 미판정 후보 9개는 0030 sealed Gold에서 전부 relevance 0으로 이미 확정돼 있어 추가
  검토 없이 M3 step 5를 닫았다. `0346` 정정 대상 provision은 raw/R1 후보 집합 밖이라 이 수치에 영향이
  없음을 확인했다. 결과를
  [experiment-d-10-m3-calibration-summary.md](../../generated/experiment-d-10-m3-calibration-summary.md)에
  기록하고 M3를 완료로 표시했다. M4(AI 입력 문맥 확정)는 아직 실행하지 않았다.
- 2026-08-07: M4 착수 중 raw/R1의 "직접 근거" 판정을 0030 sealed Gold(v2) relevance-2 기준으로 다시
  계산하니 0026 기준 M3 결과와 어긋남을 발견했다. 사용자가 0026의 `direct_evidence_provision_ids`와
  v2를 10문항 전수 대조해 6문항(9건)의 불일치를 찾았고, 각각 원문·facet 대조로 재검토했다 — 7건은
  v1/v2 relevance 0이 맞았고 `0601`의 `9c93a34b`·`7cd6894f` 2건만 오채점이었다. v3 proposal로 정정해
  `d10-gold-20260807t065254073895z`를 새로 만들고(30,660개 중 정확히 2줄 변경) confirm·seal·
  preflight-sealed를 통과했다. M3를 v3 기준으로 재계산해 raw hit@1/3/5/10 `5/5/5/7`, MRR@10 `0.525`,
  R1 hit@1/3/5/10 `5/7/7/7`, MRR@10 `0.60`으로 갱신했다(`0561`이 0026 기준 1위→실제 8위로 하향,
  `0601`이 없음→1위로 상향). 놓친 이유는 [design doc
  회고](../../design-docs/experiment-d-10-gold-adjudication.md#회고--v1에서-놓친-것과-다음-평가에서-고려할-점)에
  정리했다. M4는 아직 시작하지 않았고, M4용으로 미리 만든
  `apps/api/scripts/experiment_d_10_context_assembly.py`는 v2 sealed 경로를 참조하므로 재개 전
  v3 경로로 갱신해야 한다.
- 2026-08-07: 스크립트를 v3 경로로 갱신하고 raw×R1×{A,B×4} 10개 조합을 계산했다. R1 조합의
  `first_direct_evidence_rank`가 raw rank를 그대로 보고하는 버그(공유 `Candidate` 객체의 stale
  `.rank`)를 발견해 R1 재정렬 시 position 기반 rank로 새 객체를 만들도록 고쳤다. 결과: B(계층 복원)는
  4개 변형 전부 A와 hit count가 동일하고 토큰만 2~3배 더 썼다 — hit 여부는 순위(어떤 조문을 고르나)가
  결정하지 조립 방식(얼마나 상세히 주나)은 결정하지 않았다. 승자 `R1+A-5-60000`(hit 7/10, 평균 371
  토큰)을
  [experiment-d-10-m4-context-assembly-summary.md](../../generated/experiment-d-10-m4-context-assembly-summary.md)에
  기록했다. 사용자 지적에 따라 "검증 무게 원칙"을 추가했다 — 앞으로 D-10 calibration 라벨 수정은
  seal 라운드를 새로 만들지 않고, seal·SHA·decision log 수준은 M4의 `search-context-contract-v1`과
  0029 D-full held-out 단계에만 쓴다. `search-context-contract-v1`은 이 원칙에 따라 Pydantic
  스키마·SHA 결박 스크립트 대신 이 문서 표로 파라미터를 확정했고, 실제 운영 코드는 M5로 미뤘다. M4를
  완료로 표시했다.
- 2026-08-08: M5 항목 중 API 호출·비용이 없는 부분만 먼저 구현했다 — 항목 1(M4 문맥 재사용)과
  5(검증 실패 시 검색 전용 fallback)는 `app/main.py`에 이미 구현돼 있어 확인만 했다. 항목 4는
  `app/domain/generation_profiles.py`(model/prompt/schema/context/sampling을 묶고 SHA로 참조하는
  `GenerationProfile`)를 추가해 `diagnostics["generation"]`에 `generation_profile_key`/
  `_sha256`으로 기록했다. 항목 2는 `app/domain/answer_actions.py`의 `derive_answer_action()`으로
  D-10 gold의 answerability 네 값(`fully_answerable`·`partially_answerable`·
  `clarification_required`·`unanswerable`)과 이름을 맞춘 `QuestionResponse.action`(optional,
  하위 호환)을 추가했다 — **MOCK/미확정**: checklist status→action 매핑 규칙은 D-10으로 검증한 적이
  없는 첫 추정치다. 항목 3(provider를 `nvidia_nim`으로 고정)과 항목 6(hosted smoke)은 실행하지
  않았다 — 전자는 기본값 변경이라 사용자 확인이 먼저 필요하고, 후자는 실제 유료 API 호출이 필요하다.
  NVIDIA 답변 모델(`nvidia/nemotron-3-ultra-550b-a55b`)의 `temperature=1.0`이 결정론적 법률 답변에
  흔히 쓰는 값보다 높아 의도된 값인지 확인이 필요하다는 것도 이때 발견해 `generation_profiles.py`
  주석에 MOCK으로 표시했다. M4.5(0028)는 자체 완료 gate("라우팅 fixture와 비용 gate 통과")를 아직
  통과하지 못했지만, M5는 M4의 동결 검색·문맥 경로를 그대로 쓰는 독립 트랙이라 병행 진행했다.
- 2026-08-08: 사용자가 `.env.local`에 NVIDIA_API_KEY를 등록해 M5 항목 3(provider
  `nvidia_nim` 고정)과 항목 6(bounded hosted smoke)을 실행했다. 항목 3은
  `settings.answer_provider` 기본값을 `nvidia_nim`으로 바꿨다(0028 결정 기록에도 동일 항목
  기록). 항목 6은 `scripts/hosted_answer_smoke_test.py`로 D-10 legal_search 질문 2개 +
  의도적 무관 질문 1개를 실제 파이프라인(Postgres 검색 + NVIDIA 생성)에 통과시켰다.

  **발견 — `answer_timeout_seconds` 기본값 30초가 실제로 너무 짧았다**: 첫 실행에서
  legal_search 질문 2개가 모두 `generation_error`로 fallback됐다. 직접 재현해보니
  `nemotron-3-ultra-550b-a55b`의 정상 생성 자체가 29.2~36.0초 걸려 30초 timeout에
  자주 걸렸다 — 답이 틀려서가 아니라 순수 latency 문제였다. 60초로 올리고(`app/settings.py`,
  `.env.example`, 로컬 `.env.local`) 재현했더니 36.0초로 정상 통과했다. 이 60초도 실측
  몇 건 기준 추정치라 M6 E1/E2의 p50/p95 latency 기록에서 다시 검증해야 한다. 세 번째
  질문("냉장고에서 이상한 소리")은 검색은 히트가 나왔지만(코퍼스가 무관 조문을 그나마 가장
  가까운 것으로 반환) 생성이 grounding gate에서 정상적으로 걸러져 `grounding_failed`
  fallback으로 끝났다 — 의도한 안전장치가 실제로 작동하는 걸 확인했다.
  provider-error/timeout 자체의 코드 경로는 이미 mock 기반 단위 테스트
  (`tests/test_ai_fallback.py`)로 커버돼 있어 실제 장애를 인위로 유발하지는 않았다.

  **부수 발견 — `QuestionResponse.route`가 성공/fallback 경로에서 비어 있었다**: 라우팅
  결정은 차단된 세 route(`route_blocked_answer`)에만 기록되고 있었고, `legal_search`로
  통과한 성공/fallback 응답에는 `route` 필드가 안 채워졌다. `route_decision`을 함수
  스코프로 끌어올려 두 경로 모두에 채우도록 고쳤다.

## 초기 로드맵 작성에서 하지 않은 일

- gold·pilot·Experiment D/E artifact 생성 또는 실행
- NVIDIA/Open API/Storage 호출
- 운영 DB 쓰기, migration, corpus 게시·점검 모드·검색 smoke
- M2 이후의 기능 코드·workflow·환경변수 변경
- Production `main` 병합·push·배포
