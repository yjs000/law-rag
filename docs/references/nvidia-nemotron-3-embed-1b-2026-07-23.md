# NVIDIA Nemotron 3 Embed 1B 조사

확인일: 2026-07-23
적용 대상: 실험 B NVIDIA hosted NIM 임베딩 provider 선정

## 결론

`nvidia/nemotron-3-embed-1b`를 실험 B의 hosted embedding 모델로 선택한다. NVIDIA catalog가
`Free Endpoint`로 표시하고, 한국어를 포함한 34개 언어에서 평가됐으며 semantic similarity,
dense retrieval과 RAG가 명시적 용도다. 이 무료 endpoint는 NVIDIA API trial 조건이며 무제한·
영구 무료나 production SLA를 뜻하지 않는다.

## 확인된 계약

- 모델 ID: `nvidia/nemotron-3-embed-1b`
- hosted 상태: NVIDIA Build catalog의 `Free Endpoint`
- 용도: multilingual/cross-lingual semantic similarity, dense retrieval, semantic search, RAG
- 평가 언어: Korean을 포함한 34개 언어
- native output: float 2048차원
- hosted NIM API: `POST /v1/embeddings`, `input_type=query|passage`, text modality
- current NIM API에서 `dimensions=512`는 지원하지 않으며 native 2048만 허용
- 모델 카드는 첫 1024 또는 512차원 유지가 가능하되 sliced vector를 L2 재정규화하도록 요구
- NIM support matrix에서 hosted/runtime 검증 최대 입력은 4096 tokens로 본다.

## 적용 판단

기존 DB와 검색은 `vector(512)`이므로 NIM에 512를 요청하지 않는다. 2048 float를 받은 후 첫 512개를
취하고 L2 재정규화한다. 질문과 문서에 같은 변환을 적용해야 하며 OpenAI embedding과 혼합하지 않는다.

### 왜 첫 512개인가

NVIDIA 모델 카드가 지원한다고 명시한 축약 방식이 첫 1024개 또는 첫 512개를 유지하는 prefix
slicing이기 때문이다. 현재 저장소가 요구하는 차원은 512이므로 두 공식 선택지 중 첫 512개를 택한다.
마지막 좌표나 임의 좌표 512개를 고르는 것은 모델 카드가 보장한 방법이 아니다. 이 판단은 모델의
구체적인 학습 알고리즘을 추정한 것이 아니라 공개된 출력 계약을 그대로 따른 것이다.

### 왜 L2 재정규화하는가

전체 벡터 `v`가 `||v||₂ = 1`이어도 `v[:512]`의 norm은 뒤 좌표의 에너지가 제거되어 일반적으로
1보다 작다. `u = v[:512] / ||v[:512]||₂`로 바꾸면 남은 512개 좌표 사이의 비율과 방향은 유지하면서
norm만 1로 복원한다. NVIDIA 모델 카드도 similarity scoring 전에 이 재정규화를 요구한다.

정규화 후에는 두 단위 벡터의 내적이 코사인 유사도와 같아져 cosine·inner-product 구현의 일관성이
좋아진다. 반면 잘라낸 1536개 좌표의 정보는 돌아오지 않는다. 저장 크기와 벡터 연산량은 2048차원
대비 4분의 1이 되지만 검색 품질은 변할 수 있으므로 대표 법률 질의·문서 평가셋으로 검증해야 한다.
순수 코사인 공식만 사용하면 정규화 전후 cosine 값 자체는 같지만, 모델의 출력 계약과 단위 벡터 저장
불변조건을 지키기 위해 재정규화한다.

`llama-nemotron-embed-1b-v2`는 한국어와 동적 512차원을 지원하지만 현재 catalog에서 Downloadable로
표시된다. `bge-m3`도 multilingual이지만 Downloadable이다. 로컬 GPU/NIM을 새로 운영하지 않고 hosted
free endpoint로 실험한다는 조건에서는 `nemotron-3-embed-1b`가 가장 직접적이다.

## 공식 출처

- [NVIDIA 모델 카드: Nemotron 3 Embed 1B](https://build.nvidia.com/nvidia/nemotron-3-embed-1b/modelcard)
- [NVIDIA embedding 모델 catalog](https://build.nvidia.com/models?q=embed)
- [NVIDIA NeMo Retriever Embedding NIM API reference](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/reference.html)
- [NVIDIA NeMo Retriever Embedding NIM support matrix](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/support-matrix.html)
- [NVIDIA 모델 카드: Llama Nemotron Embed 1B v2](https://build.nvidia.com/nvidia/llama-nemotron-embed-1b-v2/modelcard)
- [NVIDIA 모델 카드: BGE-M3](https://build.nvidia.com/baai/bge-m3/modelcard)
