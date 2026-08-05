# 실험 D-10 수동 검색·문맥 진단

상태: 구현 기준
최종 갱신: 2026-08-05

## 목적

승인된 일반 사용자 질문 1,000개 중 정답을 미리 붙이지 않은 10개를 현재 PostgreSQL의 확정 corpus에
한 번 검색한다. 같은 raw top 10 결과를 사람이 읽어 D1의 직접 근거 순위와 D2의 조문 문맥 충분성을
함께 판정한다. 이는 정식 gold·Recall 평가를 대체하지 않는 비용 최소 진단 pilot이다.

## 실험 C·D-10·D-full 경계

| 구분 | 실험 C | D-10 | D-full |
|---|---|---|---|
| 목적 | 후보 순위와 기록 방식 관찰 | 후보가 직접 근거인지, 복원 문맥이 충분한지 수동 진단 | 독립 gold 기반 검색 성능 평가 |
| corpus | 과거 로컬 3개 법률 일부, 205청크 | 실행 시점 현재 DB의 검색 준비 완료 provision과 활성 벡터 | 승인 gold의 문항 기준일별 DB population |
| 정답 | 고정 기대 조문 | 실행 전 없음 | 독립 qrels·reference·adjudication |
| 결과 | raw 청크·조 후보와 과거 고정 지표 | raw provision·조문 문맥·사용자 확인 진단값 | Recall·MRR·nDCG·facet 등 정식 지표 |

실험 C의 코드·corpus·결과는 역사적 기록으로 보존한다. 저작권법과 과거 전기사업법을 포함한 로컬
205청크 결과를 현재 검색 품질 기준으로 재실행하거나 D-10/D-full 수치와 비교하지 않는다. 실험 A·B는
corpus 검색 실험이 아니므로 기존 기록을 그대로 둔다.

## 고정 입력

입력은 `experiments/d_manual/experiment-d-10-questions.json`이다. 문항마다 승인된 질문 ID,
`question_sha256`, `question_scope_sha256`만 고정한다. 질문 문구는 권위 질문은행에서 읽고 승인 manifest와
다시 대조한다. 답변, qrel, 기대 법률·조문, 기대 판정은 입력에 넣지 않는다.

10문항은 법률이 직접 답할 가능성이 있는 질문, 사용자 사실·계약·현장 자료가 더 필요한 질문,
실시간 상태·예산·민원처럼 현재 법령 corpus만으로 끝까지 답하기 어려운 질문을 섞는다. 이 층화는 다양한
실패를 보기 위한 선택 기준이지 문항별 정답 라벨이 아니다. 기존 질문은행과 승인 manifest, D-full gold
계약은 수정하지 않는다.

## 실행 계약

실행기는 `scripts.experiment_d_manual_review`이며 다음 순서를 지킨다.

1. 질문 입력과 승인 manifest를 검증한다.
2. `REPEATABLE READ, READ ONLY`에서 corpus ready, 오늘 content snapshot, 활성 NVIDIA 512차원 profile,
   provision/vector 전수 coverage와 L2 norm을 검사한다.
3. 같은 질문 SHA·profile·snapshot의 query vector가 로컬 cache에 있으면 재사용한다. 누락된 질문은 최대
   10개를 NVIDIA query embedding 한 batch로만 요청하고 cache를 원자 교체한다.
4. corpus mutation shared lock을 얻은 `READ COMMITTED, READ ONLY` transaction에서 snapshot과 profile을
   다시 검사한다. 초기 상태와 다르면 검색하지 않고 실패한다.
5. 질문마다 현재 기준일 유효 raw provision을 exhaustive exact cosine으로 11개 조회한다. 10위와 11위
   점수가 같으면 `unresolved_cutoff_tie`로 전체 실행을 실패시킨다.
6. top 10 raw 후보를 조 단위로 중복 제거하고, 같은 문서·버전의 부모 조문과 모든 하위 항·호·목을 DB
   snapshot에서 원문 순서로 복원한다.
7. 완성된 JSON과 Markdown, 실제 CLI stdout의 SHA-256을 하나의 새 run 디렉터리로 원자 게시한다.

실행기는 `experiment_search prepare`, Open API 수집, 로컬 corpus 생성, passage embedding, answer 생성,
keyword fallback, hybrid, RRF, reranker와 HNSW를 호출하지 않는다. 출력은
`.data/experiments/d-manual/runs/<run-id>/`에 두고 기존 성공 run을 덮어쓰지 않는다.

## 수동 검토와 진단값

각 문항의 자동 출력에는 질문, raw top 10과 점수, 조문별 최고 raw 순위, 복원된 조·항·호·목 문맥을
포함한다. 그 뒤 Codex가 다음 1차 판정을 작성하고 사용자가 승인·수정·보류한다.

- 직접 근거 provision과 raw 순위
- `directly_answerable | partially_answerable | clarification_required | not_answerable_from_current_corpus`
- 근거가 있는 답변 요소와 없는 요소
- `sufficient | insufficient | blocked` 문맥 판정
- top 5 무관 raw 후보

10문항 모두 사용자가 승인 또는 수정한 검토 artifact만 진단 집계 입력으로 허용한다. 하나라도 보류·누락이면
집계를 게시하지 않는다. 확인 후 계산하는 값은 직접 근거 hit@1/3/5/10, 첫 직접 근거 순위, top 5 무관
후보 수, 문맥 충분·부족·차단 건수, Codex가 추가 질문과 corpus 근거 부족을 최종 판정과 같게 구분한 건수다.
이 값은 `D-10 manual diagnostic`이며 Evidence Recall, 정식 Gold 지표 또는 일반화된 검색 성능이 아니다.

사용자 확인 전에는 `docs/generated/`에 결과 요약을 만들지 않는다. 확인이 끝난 뒤에도 원본 run과 검토
artifact는 `.data`에 두고, 간단한 확정 요약과 snapshot·profile·입력·출력 해시만 생성 문서에 남긴다.

## 완료와 다음 단계

D-10은 실행기 구현만으로 완료되지 않는다. 실제 run, Codex 1차 검토, 사용자 최종 확인, 확인된 진단
집계와 필요한 문맥 구성 수정 여부 결정까지 끝나야 완료다. 그 뒤에만 D-full 또는 AI 답변 생성 실험 E/운영
연결의 다음 범위를 별도 계약으로 시작한다.

## 결정 기록

- 2026-08-05: 실험 C를 D로 이름만 바꾸거나 과거 로컬 결과를 현재 DB 결과로 재평가하지 않는다.
- 2026-08-05: 1,000문항 D-full과 gold 계약을 보존하고, 정답 없는 10문항을 별도 수동 진단으로 먼저 실행한다.
- 2026-08-05: 비용 상한은 새 수집 0회, passage embedding 0회, cache miss query embedding 최대 10개 한 batch다.
- 2026-08-05: 사용자 확인 전에는 Recall을 계산하거나 운영 답변 생성을 시작하지 않는다.
