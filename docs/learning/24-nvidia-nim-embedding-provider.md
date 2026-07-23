# NVIDIA NIM 임베딩 provider 교체

## 변경 결과

질문 임베딩과 실험 B가 `nvidia/nemotron-3-embed-1b`를 사용한다. 기존
`embed(texts: list[str]) -> list[list[float]]` 계약, 입력 순서, 빈 배열 처리와 최종 512차원은
유지했다. 실제 NVIDIA API 호출이나 실험 점수 생성은 수행하지 않았다.

## 변환 경계

NVIDIA hosted NIM은 이 모델에서 native 2048차원만 반환한다. adapter는 응답 개수·index·차원·
유한값을 검증한 뒤 모델 카드가 허용한 첫 512개를 선택하고 L2 norm 1로 재정규화한다. 질문에는
`input_type=query`를 사용한다. 이후 문서 색인을 만들 때는 같은 adapter의 `passage` 설정과 동일한
slicing·정규화를 사용해야 한다.

```text
NIM 2048 float
-> 응답 index와 유한값 검증
-> vector[:512]
-> vector / L2 norm
-> 기존 512차원 검색 경계
```

## 벡터 공간 격리

차원이 같아도 서로 다른 모델의 좌표는 직접 비교할 수 없다. 기존 SQL은 `provision_embeddings.model`을
필터링하지 않았으므로 query embedding과 model ID를 함께 repository에 전달하도록 바꿨다. 새
`hybrid_search` overload는 model, dimensions 512, embedding version 1이 모두 맞는 의미 후보만
선택한다. NVIDIA 문서 벡터가 없으면 의미 후보는 비지만 키워드 후보와 검색 전용 폴백은 유지된다.

## 실패 계약

- NVIDIA key가 없으면 embedding 단계는 provider unavailable로 건너뛴다.
- 인증, rate limit, timeout, 응답 검증 실패는 provider 원문을 사용자에게 반환하지 않는다.
- embedding 실패가 키워드 검색을 중단하지 않는다.
- 다른 임베딩 provider나 영벡터로 자동 대체하지 않는다.
- 테스트 환경은 로컬 `.env.local`의 실제 NVIDIA key를 상속하지 않는다.

## 검증

mock 응답으로 batch 순서, 2048→512 slicing, L2 norm, 잘못된 index·차원·NaN·영벡터,
설정과 검색 model 전달을 검증한다. 실험 B 실행기는 두 문장과 두 512차원 벡터, norm과 cosine을
표준 출력에만 표시하고 저장소 결과 파일을 만들지 않는다.

## 관련 문서

- [실험 B 실행 계획](../exec-plans/completed/0017-experiment-b-sentence-embeddings.md)
- [코사인 유사도](23-cosine-similarity.md)
- [NVIDIA 모델 참고](../references/nvidia-nemotron-3-embed-1b-2026-07-23.md)
