# 실험 C — Dense 검색 후보 관찰

> 이 실험과 아래 수치는 과거 로컬 3개 법률 일부·205청크에 한정된 역사적 기록이다. 현재 PostgreSQL의
> 확정 에너지 법령 corpus를 쓰는 D-10/D-full 기준선으로 재실행하거나 비교하지 않는다. 코드는 실제 결과
> 자동 기록 방식의 참고로만 남긴다.

지정 장·조 범위의 기존 청크 205개와 NVIDIA query embedding의 코사인 유사도를 전수 계산한다. 검색
후보를 AI 답변 문맥으로 확정하지 않고, raw 청크 순위와 조 단위 그룹 순위를 함께 관찰·기록한다.

## corpus 범위

| 법령 | 버전 | 저장 범위 | 청크 수 |
| --- | --- | --- | ---: |
| 저작권법 | 현행 MST `283335`, 시행 2026-05-11 | 제1장, 제5장 | 74 |
| 전기사업법 | 과거 MST `180380`, 시행 2016-07-28 | 제1장, 제6장 | 94 |
| 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 | 현행 MST `268793`, 시행 2026-02-01 | 제1조부터 제5조 | 37 |

선택된 조의 항·호·목은 모두 보존한다. `제5장의2`는 제5장에 포함하지 않고, 제1조~제5조 범위의
`제2조의2` 같은 가지조문은 포함한다.

## 환경변수와 준비

비밀값은 루트 또는 앱별 `.env.local`에 둔다.

```dotenv
LAW_OPEN_API_OC=<국가법령정보 공동활용 Open API OC>
NVIDIA_API_KEY=<NVIDIA Build API key>
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b
EMBEDDING_DIMENSIONS=512
```

```powershell
uv run --directory apps/api python -m scripts.experiment_search prepare
```

성공하면 Git에서 제외되는 `.data/experiments/search/corpus.json`이 원자 교체된다. 모든 원문 수집,
범위 검증, passage embedding과 512차원 벡터 검증이 끝나기 전에는 기존 corpus를 덮어쓰지 않는다.

## 질문, 후보 10개와 자동 기록

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask `
  --question "태양광 발전에 사용하는 태양에너지는 신에너지와 재생에너지 중 어디에 해당하나요?"
```

기본 `candidate_k=10`이며 `--candidate-k 20`처럼 1~50 사이에서 바꿀 수 있다. 출력은 두 목록이다.

- `raw_chunk_candidates`: 개별 조·항·호·목 청크의 cosine 상위 K
- `article_candidates`: 같은 조의 모든 청크를 묶고 최고 하위청크 cosine을 조 점수로 사용한 상위 K

조 후보에는 조 전체 청크 수, 최고 청크와 점수가 높은 하위청크 3개가 들어간다. 이는 dense-only
관찰 후보이며 AI에 전달할 최종 근거가 아니다.

성공한 `ask`는 실험 A와 같은 성공 후 원자 기록 원칙으로 다음 파일을 자동 생성·갱신한다.

- `.data/experiments/search/search-runs.json`: 실행 번호, corpus/stdout SHA-256과 실제 stdout 전체
- `.data/experiments/search/search-results.md`: 실행 비교표와 실행별 실제 stdout 전체

두 파일은 질문 원문을 포함하므로 로컬 `.data`에만 두고 Git에 넣지 않는다. 기록을 원하지 않는 단일
실행만 `--no-record`를 사용한다. 검색 성공 후 기록이 실패하면 `result_recording_failed`와 종료 코드
`2`를 반환하고 이전 성공 이력을 보존한다.

## 고정 평가

```powershell
uv run --directory apps/api python -m scripts.experiment_search evaluate
```

[고정 질문셋](evaluation-questions.json)의 기대 법률·조문을 기준으로 다음을 계산한다.

- Law@1
- Article Recall@3, Recall@5, Recall@10
- Article MRR
- Evidence Recall@3, Recall@5, Recall@10
- 기대 조문의 raw 청크 rank와 조 단위 rank
- 기대 조문의 필수 근거 문구가 복원된 조·항·호·목에 실제로 있는지
- 범위 밖 기대 조문이 corpus에 실제로 없는지

기계 판독 결과는 `.data/experiments/search/evaluation.json`, 사람이 읽는 대표 결과는
[실제 dense 검색 평가](../../docs/generated/experiment-c-retrieval-evaluation.md)에 원자 생성된다.

2026-07-23 수정 전 실제 기준선은 Law@1 `1.0`, Recall@3 `0.8`, Recall@5 `0.8`, Recall@10
`1.0`, MRR `0.82`였다. 2026-08-03에는 구조 표지와 평탄화된 `목` 계층을 고치고 corpus validator를
통과시킨 뒤 재측정했다. 최종 Law@1, Article Recall@3/5/10, Article MRR, Evidence Recall@3/5/10은
모두 `1.0`이었다.

이는 고정된 범위 내 질문 5개에 대한 결과이며 일반 검색 성능이 완벽하다는 뜻은 아니다. 현재 평가셋에서는
hybrid 검색이 높일 지표 여지가 없으므로 dense-only를 유지하고 평가 질문을 확장한 뒤 다시 비교한다.

## 현재 하지 않는 것

- 키워드·BM25·PGroonga·RRF 결합: [보류 설계](../../docs/design-docs/experiment-c-keyword-retrieval-options.md)
- AI reranker를 사용한 일반 질문의 의미 기반 직접 근거 판정
- 생성 AI 답변, production DB·검색 변경

`score`는 코사인 유사도이며 정답 확률이 아니다. 후보 1위여도 실제 `content`가 질문을 뒷받침하는지
직접 확인해야 한다.

## 실패 동작

- corpus 없음: `corpus_missing`, 종료 코드 `2`
- Open API OC 또는 NVIDIA key 없음: 해당 설정 누락 코드, 종료 코드 `2`
- 지정 범위·모델·차원·평가셋 검증 실패: `experiment_c_failed`, 종료 코드 `2`
- 기록 실패: `result_recording_failed`, 종료 코드 `2`
- provider 오류 전문, API key와 Authorization header는 출력·저장하지 않음
