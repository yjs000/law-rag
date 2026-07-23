# 로컬 10청크 벡터 검색 실험에서 배운 경계

## 결론

실험 C는 새 검색 모델을 만든 것이 아니라 기존 네 경계를 작은 로컬 corpus에 연결했다.

```text
국가법령정보 Open API
-> 기존 JSON 우선/XML 폴백 parser
-> parser가 만든 기존 조·항·호 청크 중 10개 선택
-> 기존 NVIDIA passage embedding, 512차원
-> 로컬 JSON
-> 질문의 기존 NVIDIA query embedding
-> 10개 cosine 전수 계산
-> 상위 3개
```

10개뿐이므로 별도 벡터 DB나 근사 최근접 탐색이 필요하지 않다. 모든 벡터를 직접 비교하면 결과와
점수 계산을 가장 쉽게 관찰할 수 있다.

## 데이터 저장과 계보

로컬 corpus는 `.data/experiments/search/corpus.json`에 저장한다. Git에 넣지 않지만 각 청크는 법령명,
source ID, MST, 시행일, OC가 제거된 Open API URL, 원문 SHA-256, parser version과 조문 path를 가진다.
따라서 “어느 화면에서 복사한 텍스트인지”가 아니라 “어느 Open API 원문 버전을 어떤 parser가 어떤
경로로 나눴는지”를 추적할 수 있다.

사용자가 준 세 URL은 다음 입력을 뜻한다.

- 저작권법 현재 버전
- 전기사업법 과거 `lsiSeq/MST=180380`, 시행 2016-07-28 버전
- 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 현재 버전

법령 화면 HTML은 본문 데이터로 사용하지 않았다.

## 기존 청커를 재사용할 때 확인할 점

첫 준비에서는 최상위 `제7조`, `제9조`, `제10조`를 선택했다. live smoke 검색 결과 `제7조` content는
허가 본문이 아니라 `제2장 전기사업 제1절 허가 등`이라는 장·절 표제였고, 실제 허가 문장은 기존
parser의 `제7조/항①`에 있었다.

이 문제를 고치기 위해 parser나 chunk 내용을 합치지 않았다. 기존 파서 출력 목록을 확인하고 의미가
독립적인 하위 경로를 선택했다. “기존 청커 재사용”은 함수만 호출하는 것이 아니라 반환된 각 청크가
실제로 검색할 내용을 담는지 검사하는 것까지 포함한다.

최종 선택은 저작권법 3개, 전기사업법 4개, 신재생에너지법 3개다. 10개 제한 안에서 법령별 대표
정의·허가·의무 조문을 함께 관찰하기 위한 실험 선택이며 production corpus 선정 기준은 아니다.

## passage와 query를 분리하는 이유

같은 `nvidia/nemotron-3-embed-1b`를 사용하지만 저장할 문서는 `input_type=passage`, 사용자 질문은
`input_type=query`로 보낸다. 이는 검색 대상과 검색 요청의 역할을 모델에 알려 주는 기존 adapter
계약이다. 두 경우 모두 native 2048차원을 검증한 뒤 앞 512개를 선택하고 L2 재정규화한다.

모델 ID와 최종 차원이 같아도 query/passage 설정이나 slicing 방식이 다르면 같은 검색 공간 계약으로
간주할 수 없다. corpus metadata에 model, dimensions, embedding version과 두 input type을 함께 둔
이유다.

## exhaustive cosine top 3

질문 벡터 `q`와 각 청크 벡터 `dᵢ`에 다음 계산을 적용한다.

```text
scoreᵢ = (q · dᵢ) / (||q||₂ * ||dᵢ||₂)
```

점수가 큰 순서로 정렬하고 처음 3개만 출력한다. 같은 점수는 안정적인 `chunk_id` 순으로 정렬해 같은
입력에서 순서가 흔들리지 않게 한다. 이 점수는 확률이나 법률적 동일성 판정이 아니다.

10개에 대한 전수 계산은 정확히 10번의 cosine만 필요하다. 대규모 corpus에서 사용하는 HNSW 같은
근사 색인은 관찰을 복잡하게 만들 뿐 이 실험에는 이점이 없다.

## 실제 smoke 확인

교정된 corpus에 `전기사업을 하려면 누구의 허가를 받아야 하나?`를 질문했을 때 다음 순서가 나왔다.

1. 전기사업법 `제7조/항①` — 허가 의무
2. 전기사업법 `제10조/항①` — 양수·분할·합병 등의 인가
3. 전기사업법 `제8조` — 허가 결격사유

이 결과는 연결이 동작한다는 smoke 확인이다. 10개만 대상으로 한 한 질문의 순위이므로 검색 품질,
임계값 또는 production 성능을 입증하지 않는다.

## 실패와 개인정보 경계

- 준비가 모두 성공한 후에만 corpus를 원자 교체한다.
- 조문 경로가 없으면 비슷한 다른 경로를 임의 선택하지 않는다.
- provider 실패 시 다른 모델이나 영벡터로 바꾸지 않는다.
- API key, OC와 provider 오류 전문은 저장하지 않는다.
- 질문은 임베딩 API로 보내지만 로컬 결과 이력에는 저장하지 않는다.
- 이 실험은 production DB, Supabase와 MVP 허용 코퍼스를 변경하지 않는다.

## 실행

```powershell
uv run --directory apps/api python -m scripts.experiment_search prepare
uv run --directory apps/api python -m scripts.experiment_search ask
```

상세 경로와 출력 계약은 [실험 C 실행 안내](../../experiments/search/README.md)를 참고한다.
