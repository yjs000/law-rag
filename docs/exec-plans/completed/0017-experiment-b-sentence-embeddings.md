# 실행 계획 0017: 실험 B — NVIDIA NIM 두 문장 임베딩과 코사인 유사도

상태: 구현 및 실제 2회 반복 실행 완료
작성일: 2026-07-23
소유자: Codex

## 목적과 사용자 결과

현재 질문 처리 흐름의 `embed(texts) -> list[list[float]]` 계약, 512차원 검색 벡터와 응답 순서
보존 방식을 그대로 사용하되, 임베딩 provider를 OpenAI에서 NVIDIA hosted NIM으로 교체한다.
추천 문장 두 개의 512차원 임베딩 전체와 코사인 유사도를 로컬 터미널에 출력한다.

예상 조건과 실제 실행값을 구분한다. 성공한 터미널 JSON 문자열은 그대로 생성 문서에 기록하고,
반복 실행마다 전체 512차원 벡터의 정확 일치 여부와 수치 차이를 계산한다. 2026-07-23에 같은 입력으로
live API를 두 번 호출한 결과와 비교표를 `docs/generated/experiment-b-embedding-results.md`에 남겼다.

## 추천 문장

문장 A:

> 전기사업을 하려는 자는 산업통상자원부장관의 허가를 받아야 한다.

문장 B:

> 산업통상자원부장관의 허가를 받지 않으면 전기사업을 시작할 수 없다.

행위자, 전기사업 시작과 사전 허가라는 의미는 같고 긍정형 의무와 부정형 금지로 문장 구조가
다르다. 동일 문자열 복사가 아닌 한국어 의미 유사성을 관찰하기 위한 쌍이며 법률 해석이나 답변
근거로 사용하지 않는다.

## 현재 구현과 변경 경계

현재 구현은 `NvidiaNimEmbedder.embed(texts)`가 텍스트 배열을 한 번에 전송하고 응답 `index` 순서로
벡터를 반환한다. 질문 처리 코드는 이 메서드의 첫 벡터와 NVIDIA model ID를 검색에 넘긴다.

유지할 계약:

- `async embed(texts: list[str]) -> list[list[float]]`
- 빈 배열은 빈 배열 반환
- 입력 순서와 응답 `index` 순서 일치
- 검색·DB에 전달하는 최종 벡터는 512차원 float
- 임베딩 실패 시 키워드 검색을 유지하는 기존 폴백
- DB, 검색 함수와 `vector(512)` 스키마

교체할 경계:

- `OpenAIEmbedder` 대신 같은 메서드 계약의 `NvidiaNimEmbedder`
- `OPENAI_API_KEY` 대신 기존 `NVIDIA_API_KEY`
- `api.openai.com` 대신 기존 NVIDIA base URL `https://integrate.api.nvidia.com/v1`
- `text-embedding-3-large` 대신 `nvidia/nemotron-3-embed-1b`

## 선택 모델

모델: `nvidia/nemotron-3-embed-1b`

선택 이유:

- NVIDIA 모델 카탈로그에서 현재 `Free Endpoint`로 제공된다.
- 한국어를 포함한 34개 언어에서 평가된 multilingual/cross-lingual 모델이다.
- 의미 유사도, dense retrieval, semantic search와 RAG가 명시적 용도다.
- 약 1.14B parameters로 hosted 실험에 적합하고 상업적 사용 준비 모델로 표시된다.
- 네이티브 2048차원 중 첫 1024 또는 512차원을 유지할 수 있는 표현 공간으로 학습됐으며,
  잘라낸 벡터는 L2 재정규화하라는 모델 카드 계약이 있다.
- 기존 NVIDIA 생성 adapter가 이미 쓰는 API key, base URL과 OpenAI-compatible SDK 패턴을 재사용한다.

`Free Endpoint`는 NVIDIA API Trial Terms가 적용되는 prototype endpoint를 뜻하며 무제한·영구 무료,
production SLA나 고정 quota를 보장한다는 뜻은 아니다. 실제 실행 시 현재 계정의 endpoint 제공 여부와
rate limit을 확인한다.

대안 제외 이유:

- `nvidia/llama-nemotron-embed-1b-v2`는 한국어·동적 512차원을 지원하지만 현재 카탈로그 표시는
  hosted `Free Endpoint`가 아니라 `Downloadable`이다.
- `baai/bge-m3`도 한국어를 포함한 multilingual 모델이지만 현재 NVIDIA 카탈로그에서는
  `Downloadable`이므로 로컬 GPU/NIM 인프라 없이 무료 hosted 실험을 바로 실행하는 조건에 맞지 않는다.
- `nv-embedqa-e5-v5`는 영어용으로 표시되어 한국어 법률 문장 실험에 맞지 않는다.

공식 근거와 확인 날짜는
`docs/references/nvidia-nemotron-3-embed-1b-2026-07-23.md`에 고정한다.

## 2048차원 NIM과 기존 512차원 계약 연결

현재 NVIDIA NIM API는 `nvidia/nemotron-3-embed-1b`에 2048차원 native float만 허용하고
`dimensions=512` 요청은 HTTP 400이 된다. 따라서 OpenAI 어댑터처럼 API에 512를 직접 요청하지 않는다.

512를 선택하는 이유는 모델이 일반적인 임의 절단을 허용해서가 아니라 다음 두 계약이 맞물리기 때문이다.

- 저장소의 검색·DB 계약이 이미 `vector(512)`이고, 이를 유지해야 현재 검색 호출부와 스키마를 재사용할 수 있다.
- NVIDIA 모델 카드는 이 모델에 한해서 2048개 좌표 중 **첫 1024개 또는 첫 512개**를 남기는
  prefix slicing을 명시적으로 지원한다. 따라서 마지막 512개, 임의 512개 또는 균등 간격 512개를
  선택하지 않는다. 그런 절단은 모델이 보장한 축약 표현이 아니며 좌표 의미와 검색 품질을 보장할 수 없다.

즉, `vector[:512]`는 단순한 편의가 아니라 이 모델이 공개한 차원 축약 계약을 기존 512차원 시스템에
적용한 것이다. 다만 모델 카드는 축약을 지원한다고만 명시하며, 구체적인 학습 기법을 공개 근거 없이
Matryoshka라고 단정하지 않는다.

1. NIM에 `dimensions`를 보내지 않고 2048차원 float를 받는다.
2. 각 벡터가 유한한 float 2048개인지 검증한다.
3. 모델 카드가 허용한 첫 512개 원소만 유지한다.
4. 잘라낸 벡터를 L2 norm 1이 되도록 재정규화한다.
5. 기존 `embed()` 반환 타입으로 512차원 벡터를 돌려준다.

L2 재정규화가 필요한 이유:

- 2048차원 벡터가 길이 1이어도 뒤의 1536개 좌표를 버리면 남은 벡터의 길이는 보통 1보다 작아진다.
- `v512 / ||v512||₂`로 모든 남은 좌표를 같은 비율로 확대하면 512차원 부분공간 안의 방향은 유지되고
  길이만 1로 복원된다.
- 그 결과 정규화된 벡터끼리는 내적과 코사인 유사도가 같아지고, 저장·검색 시 벡터 크기 차이가 점수에
  끼어드는 것을 막는다. 순수 코사인 공식은 자체적으로 norm을 나누므로 재정규화 전후 값이 수학적으로
  같지만, 모델 카드의 계약과 내적 기반 검색 호환성을 위해 저장 전 재정규화한다.
- 재정규화는 버린 1536차원의 정보를 복구하지 않는다. 512차원은 저장 공간과 연산량을 native 대비
  4분의 1로 줄이는 대신 검색 품질이 달라질 수 있으므로 실제 법률 평가셋에서 2048차원과 비교 검증한다.

질문과 문서 벡터는 반드시 같은 모델, 같은 512 slicing과 같은 재정규화를 사용해야 한다. 기존 OpenAI
벡터와 NVIDIA 벡터는 같은 공간이 아니므로 production corpus를 혼합하지 않으며 provider 교체 시
전체 문서 임베딩을 같은 pipeline으로 다시 생성해야 한다. 실험 B는 DB backfill을 하지 않는다.

## 계획된 핵심 호출 형태

기존 NVIDIA SDK 초기화 패턴과 현재 embed 메서드 계약을 합치면 구현 형태는 다음과 같다.

```python
self.client = AsyncOpenAI(
    api_key=api_key,
    base_url="https://integrate.api.nvidia.com/v1",
    max_retries=0,
)

response = await self.client.embeddings.create(
    model="nvidia/nemotron-3-embed-1b",
    input=texts,
    extra_body={
        "input_type": "query",
        "modality": "text",
        "embedding_type": "float",
        "encoding_format": "float",
        "truncate": "NONE",
    },
)
vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
return [normalize_l2(vector[:512]) for vector in vectors]
```

실험 B의 두 문장은 문장 대 문장 비교이므로 둘 다 같은 `input_type="query"`로 보낸다. 실험 C에서
질문과 문서 검색을 연결할 때는 질문은 `query`, 문서 조각은 `passage`로 분리한다.

## 범위와 비범위

범위:

- 현재 embed 메서드와 512차원 downstream 계약을 유지한 NVIDIA provider 교체 계획
- 추천 문장 기본값과 명령행 재정의 옵션 계획
- 512차원 벡터 두 개와 코사인 유사도 터미널 출력
- mock 정상·실패·경계 테스트와 수동 실행 확인 항목
- NVIDIA 모델 선정 근거와 코사인 유사도 학습 문서

비범위:

- 자동화 테스트에서의 live API 호출
- 실제 출력과 구분되지 않는 예상 벡터·예상 유사도 작성
- 실험 C 문서 저장과 Top 3 검색
- production corpus backfill
- 모델 비교 점수, 임계값 튜닝, 법률적 동일성 판단
- FastAPI·Next.js UI와 공개 API 변경

## 실행과 출력 방식

저장소 루트에서 실행할 명령:

```powershell
uv run --directory apps/api python -m scripts.experiment_embeddings
```

기본 출력:

```text
provider: nvidia_nim
model: nvidia/nemotron-3-embed-1b
native_dimensions: 2048
output_dimensions: 512
sentence_a: <문장 A>
embedding_a: [<512개 실수 전체>]
sentence_b: <문장 B>
embedding_b: [<512개 실수 전체>]
norm_a: <값>
norm_b: <값>
cosine_similarity: <값>
```

기본 실행은 터미널에 위 JSON을 출력한 뒤 같은 문자열과 반복 비교를 다음 생성 파일에 기록한다.

- `docs/generated/experiment-b-embedding-results.md`: 사람이 읽는 예상/실제 비교와 stdout 전체
- `docs/generated/experiment-b-embedding-runs.json`: 문서 재생성과 정확 비교를 위한 원시 stdout 이력

`--no-record`를 사용하면 기존처럼 터미널에만 출력한다. 성공한 API 호출 결과와 문서에 삽입되는 JSON은
한 번 직렬화한 동일 문자열을 사용하므로, 문서가 값을 다시 계산하거나 반올림해 바꾸지 않는다.

## 사용자가 결과에서 확인할 항목

1. provider와 model이 각각 `nvidia_nim`, `nvidia/nemotron-3-embed-1b`인지 확인한다.
2. native 응답은 각 2048개, 최종 `embedding_a`, `embedding_b`는 각각 정확히 512개인지 확인한다.
3. 두 벡터의 모든 값이 유한한 숫자이고 서로 완전히 같지 않은지 확인한다.
4. slicing 후 `norm_a`, `norm_b`가 부동소수점 오차 범위에서 1에 가까운지 확인한다.
5. `cosine_similarity`가 유한하고 `-1 <= 값 <= 1`인지 확인한다.
6. 두 문장은 의미가 가까우므로 양의 높은 값이 자연스럽지만, 이 한 쌍만으로 합격 임계값을 정하지 않는다.
7. 예상보다 낮거나 음수이면 문장 순서보다 먼저 model ID, `input_type`, 2048→512 slicing과
   L2 재정규화가 둘 다 동일하게 적용됐는지 확인한다.
8. 출력과 오류에 `NVIDIA_API_KEY`, Authorization header나 provider 오류 전문이 없는지 확인한다.

실험 결과는 확률이 아니며 “법적으로 같은 문장”이라는 판정도 아니다. 모델·전처리·차원 계약이 제대로
연결됐는지 관찰하는 smoke test다.

## 입력, 비용과 비밀정보

- `NVIDIA_API_KEY`는 `apps/api/.env.local` 또는 프로세스 환경변수로만 주입한다.
- 키를 CLI 인자, 출력, JSON, 오류나 문서에 기록하지 않는다.
- 비개인 공개 실험 문장만 hosted endpoint에 전송한다.
- `Free Endpoint` 가용성과 quota는 계정·trial 조건에 의존한다. 유료 전환이나 production 사용은
  별도 사용자 결정 없이는 진행하지 않는다.

## 실패 동작

- 키 없음, 빈 문장, 응답 개수·index·native dimension 불일치, NaN/Infinity, 영벡터,
  인증·권한, rate limit, timeout·network를 안전한 오류 코드로 구분한다.
- 실패 시 종료 코드 `2`와 provider 원문을 제외한 JSON 오류 한 줄을 표준 오류에 출력한다.
- 한 벡터라도 검증에 실패하면 slicing, 유사도와 결과 저장을 중단한다.
- OpenAI나 다른 모델, 임의 벡터나 0 벡터로 자동 대체하지 않는다.
- 실패 시 새 실행 이력을 추가하지 않는다. API 호출 후 문서 기록이 실패해도 안전한
  `result_recording_failed`와 종료 코드 `2`를 반환한다.

## 측정 가능한 완료 조건

- 기존 `embed(list[str])` 호출부와 512차원 검색·DB 계약을 바꾸지 않는다.
- 실제 provider는 NVIDIA NIM 하나이며 OpenAI embedding API를 호출하지 않는다.
- native 2048차원을 검증한 뒤 첫 512차원을 L2 재정규화한다.
- 두 문장을 단일 batch, 동일한 `query` 설정으로 보내 입력 순서대로 두 벡터를 반환한다.
- 코사인 유사도는 유한하고 `[-1, 1]` 범위다.
- 터미널에 모델, native/final 차원, 문장, 전체 벡터, norm과 유사도를 출력한다.
- 실제 stdout을 예상 조건과 분리해 생성 문서에 그대로 추가한다.
- 반복 실행은 실행 1 대비 embedding A/B 전체 일치, 최대 좌표 차이와 cosine 차이를 계산한다.
- mock 테스트는 네트워크·quota 없이 정상·실패·경계와 비밀 비노출을 검증한다.
- API 테스트, Ruff, 타입 검사와 문서 검사가 통과한다.

## TODO와 에이전트 배정

### 주 에이전트

- [x] `M1 — provider 교체 계약`: `NvidiaNimEmbedder`를 현재 embed 인터페이스와 동일하게 구현하고
  2048 검증, 512 slicing, L2 재정규화와 순서 보존 mock 테스트를 추가한다.
- [x] `M2 — 기존 질문 흐름 연결`: settings와 `_embedder()`를 NVIDIA key/model로 연결하되 검색 폴백,
  512차원 DB 계약과 생성 provider 선택을 깨뜨리지 않는 회귀 테스트를 추가한다.
- [x] `M3 — 사용자 실행 CLI`: 두 기본 문장, 전체 벡터·norm·코사인 터미널 출력과 안전한 오류를
  구현하고 테스트한다.
- [x] `M4 — 검증과 문서`: 권위 설계·환경 예시를 실제 코드와 맞추고 전체 검증 후 계획을 완료한다.
- [x] `M5 — 실제값과 반복성`: 성공 stdout 원문 기록, 예상/실제 분리, 벡터 전체 비교를 구현하고
  같은 입력으로 live 실행을 두 번 수행한다.

### 하위 에이전트

- 사용하지 않는다. provider, settings, 질문 흐름과 테스트가 같은 핵심 계약을 공유하며 병렬 수정 시
  embedding provider 조건과 공용 설정이 충돌할 위험이 있다.

## 검증 및 롤백

예정 검증 명령:

```powershell
uv run --directory apps/api python -m pytest tests/test_nvidia_nim_embedder.py -q
uv run --directory apps/api python -m pytest tests/test_ai_fallback.py tests/test_settings.py -q
uv run --directory apps/api ruff check app scripts tests
uv run python scripts/check_docs.py
pnpm.cmd verify
```

live NVIDIA 호출은 자동 검증에 포함하지 않는다. provider 전환 후에는 OpenAI와 NVIDIA 벡터를 섞지
않고, 문제가 있으면 NVIDIA query embedding을 비활성화해 기존 키워드 검색 폴백을 유지한다.
production corpus 재색인은 별도 실행 계획과 사용자 승인 전에는 수행하지 않는다.

## 결정 로그

- 2026-07-23: 무료 hosted, 한국어 평가, semantic search/RAG 용도를 모두 만족하는
  `nvidia/nemotron-3-embed-1b`를 선택했다.
- 2026-07-23: API는 native 2048만 받으므로 512를 요청하지 않고 모델 카드 계약에 따라 첫 512개를
  잘라 L2 재정규화해 기존 downstream 차원을 유지한다.
- 2026-07-23: 어댑터 구현은 교체하지만 `embed()`와 검색·DB 512차원 계약은 유지한다.
- 2026-07-23: 사용자 요청에 따라 실제 stdout을 생성 문서에 그대로 보존하고, 반복 실행의 전체 벡터와
  cosine 차이를 계산한다. 예상값은 실제 결과 영역에 넣지 않는다.
- 2026-07-23: cosine score는 확률·법률적 동일성·고정 합격 임계값으로 해석하지 않는다.

## 진행 기록

- 2026-07-22: OpenAI 기반 초안을 작성했으나 구현하거나 API를 호출하지 않았다.
- 2026-07-23: 현재 코드, NVIDIA hosted embedding catalog/API/model card와 OpenAI embedding 공식 문서를
  확인하고 NVIDIA provider 재사용 계획으로 전면 수정했다.
- 2026-07-23: 코사인 유사도 학습 문서와 사용자가 결과에서 확인할 체크리스트를 작성했다.
- 2026-07-23: NVIDIA adapter, 실험 CLI와 model-filtered hybrid search를 구현하고 mock·API 전체
  회귀 테스트를 통과했다.
- 2026-07-23: `.env.example`, 실행 안내와 운영 실패 동작을 갱신하고 구현 계획을 완료했다.
- 2026-07-23: 동일 입력으로 live API를 두 번 호출했다. 두 실행의 512차원 벡터는 정확히 같지 않았지만
  최대 좌표 차이는 A 약 `8.99e-9`, B 약 `1.07e-8`이었고 cosine 차이는 약 `-1.85e-9`였다.
  전체 실제값과 SHA-256 지문은 생성 문서에 기록했다.

## 미결정과 차단 요소

- 실제 Free Endpoint 접근 가능 여부와 quota는 사용자의 NVIDIA 계정/API key에서만 확인할 수 있다.
- production 의미 검색에는 문서 전량 재임베딩이 필요하며 실험 B 범위가 아니다.
- 두 번의 관찰만으로 provider의 장기 결정성이나 허용 오차를 확정하지 않는다. 더 많은 시점·환경에서
  반복하려면 같은 명령을 실행해 이력을 추가한다.

## 완료 결과

NVIDIA provider, 2048→512 변환, model-filtered 검색, 결과 기록 실험 CLI, mock·회귀 테스트와
환경·실패 안내를 완료했다. 실제 두 번의 stdout을 예상 조건과 분리해 생성 문서에 보존했고, 전체
벡터와 cosine의 반복 차이를 기계적으로 비교할 수 있다.
