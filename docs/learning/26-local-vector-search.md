# 기존 전체 청크를 이용한 로컬 벡터 검색의 경계

## 결론

실험 C는 새 청커나 검색 모델을 만든 것이 아니라 기존 경계를 다음과 같이 연결한다.

```text
국가법령정보 Open API
-> 기존 JSON 우선/XML 폴백 parser
-> parser가 반환한 청크 전체
-> 기존 NVIDIA passage embedding, 512차원
-> 로컬 JSON
-> 질문의 기존 NVIDIA query embedding
-> 모든 청크의 cosine 전수 계산
-> 상위 3개
```

“기존 청킹을 그대로 쓴다”는 특정 조문을 골라 쓰는 것도, 제목 전용 청크를 합치는 것도 아니다. 기존
파서가 반환한 순서와 경계를 그대로 저장하는 것이다. 이 실험의 첫 구현은 요구를 10개 표본 선택으로
잘못 좁혔고, 전체 파서 출력 사용으로 교정했다.

## 데이터 저장과 계보

로컬 corpus는 `.data/experiments/search/corpus.json`에 저장한다. Git에는 넣지 않지만 각 청크는 법령명,
source ID, MST, 시행일, OC가 제거된 Open API URL, 원문 SHA-256, parser version과 조문 path를 가진다.
따라서 어느 Open API 원문 버전을 어떤 parser가 어떤 경계로 나눴는지 추적할 수 있다.

사용자가 준 URL은 저작권법 현행, 전기사업법 과거 `MST=180380`, 신재생에너지법 현행을 식별하는
단서다. 법령 화면 HTML은 corpus 본문으로 쓰지 않는다.

## 전체 청크와 배치 임베딩은 다른 개념이다

청킹은 문서를 검색 단위로 나누는 일이고, 임베딩 배치는 그 청크들을 API 한 번에 몇 개씩 보내는지에
관한 실행 방식이다. 32개씩 여러 번 호출해도 각 청크의 텍스트, 순서, 임베딩 모델과 최종 512차원
계약은 동일하다. 배치를 쓰는 이유는 전체 법령 청크를 하나의 큰 요청에 넣어 provider 요청 제한이나
타임아웃 위험을 높이지 않기 위해서다.

모든 배치가 성공하고 벡터 개수·차원 검증까지 끝난 뒤에만 corpus를 원자 교체한다. 뒤쪽 배치가
실패해도 부분 corpus가 완성본처럼 남지 않고, 이전에 성공한 corpus가 있다면 그대로 유지된다.

## passage와 query를 분리하는 이유

같은 `nvidia/nemotron-3-embed-1b`라도 저장할 문서는 `input_type=passage`, 사용자 질문은
`input_type=query`로 보낸다. 기존 adapter는 native 2048차원을 검증한 뒤 앞 512개를 선택하고 L2
재정규화한다. 모델 ID, 최종 차원, input type과 slicing 방식이 모두 같아야 저장 벡터와 질문 벡터를
동일한 검색 공간 계약으로 비교할 수 있다.

## exhaustive cosine top 3

질문 벡터 `q`와 각 청크 벡터 `dᵢ`에 다음 계산을 적용한다.

```text
scoreᵢ = (q · dᵢ) / (||q||₂ * ||dᵢ||₂)
```

점수가 큰 순서로 정렬하고 처음 3개만 출력한다. 동점은 안정적인 `chunk_id` 순으로 정렬한다. 이
점수는 확률이나 법률적 동일성 판정이 아니다. 현재 실험 규모에서는 모든 청크를 직접 비교하면 계산
과정을 가장 쉽게 관찰할 수 있다. corpus가 훨씬 커질 때만 HNSW 같은 근사 색인의 비용·효과를 따로
검토하면 된다.

## 관찰할 점과 한계

- 파서가 만든 제목·장·절 청크도 그대로 검색 후보가 된다.
- 상위 3개가 질문과 의미상 관련 있는 원문인지 `path`와 `content`로 직접 확인한다.
- score 차이가 작으면 순위가 강한 판정이 아니라는 점을 기억한다.
- 현행 법령은 prepare 시점 버전이므로 corpus metadata의 MST와 시행일을 함께 확인한다.
- 이 실험은 production DB, Supabase, 키워드 검색과 검색 품질 임계값을 변경하지 않는다.

## 실행

```powershell
uv run --directory apps/api python -m scripts.experiment_search prepare
uv run --directory apps/api python -m scripts.experiment_search ask
```

상세 저장 필드와 실패 동작은 [실험 C 실행 안내](../../experiments/search/README.md)를 참고한다.
