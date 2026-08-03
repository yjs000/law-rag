# 실험 B — NVIDIA NIM 문장 임베딩

두 한국어 문장을 한 번의 NVIDIA hosted NIM batch 요청으로 임베딩하고, 각 512차원 벡터와 norm,
코사인 유사도를 표준 출력에 JSON으로 표시한다. 성공한 표준출력과 동일한 JSON 문자열을 실행별로
보존하고, 예상 조건과 반복 실행 차이를 생성 문서에 자동 반영한다.

## 필요한 설정

`apps/api/.env.example`을 참고해 `apps/api/.env.local`에 다음 값을 설정한다. 실제 키를 저장소,
문서, CLI 인자나 채팅에 넣지 않는다.

```dotenv
NVIDIA_API_KEY=<NVIDIA Build에서 발급한 키>
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b
EMBEDDING_DIMENSIONS=512
EMBEDDING_TIMEOUT_SECONDS=30
```

- 실험 B에 반드시 필요한 비밀값은 `NVIDIA_API_KEY` 하나다.
- base URL, model과 dimensions는 adapter가 위 값만 허용한다.
- `OPENAI_API_KEY`는 임베딩에 사용하지 않으며 기존 `OPENAI_EMBEDDING_MODEL` 변수는 제거한다.
- API 질문 흐름에서도 NVIDIA 임베딩을 사용하려면 `AI_MODE=auto`가 필요하다.
- 생성 답변까지 NVIDIA로 실행하려면 별도로 `ANSWER_PROVIDER=nvidia_nim`과
  `NVIDIA_ANSWER_MODEL`을 설정한다. 실험 B 자체에는 생성 모델 설정이 필요 없다.

NVIDIA Build의 모델 화면에서 계정에 연결된 API key를 발급한다. `Free Endpoint`는 trial 서비스이며
영구 무료, 고정 quota 또는 production SLA를 보장하지 않는다.

Vercel API에서도 사용할 경우 Project Settings의 Preview와 Production 환경에 `NVIDIA_API_KEY`를
각각 secret으로 등록하고, 나머지 NVIDIA embedding 설정도 같은 환경에 등록한다. 브라우저용
`NEXT_PUBLIC_*` 변수로 만들지 않는다.

## 실행

저장소 루트에서 다음 명령을 실행한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_embeddings
```

다른 문장을 비교하려면 다음처럼 재정의한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_embeddings `
  --sentence-a "첫 번째 문장" `
  --sentence-b "두 번째 문장"
```

성공 출력에는 provider, model, native/output dimensions, 두 문장, 두 512차원 벡터, 두 norm과
`cosine_similarity`가 포함된다. 같은 실행에서 다음 두 파일도 갱신한다.

- `docs/generated/experiment-b-embedding-results.md`: 예상 조건, 실행별 비교표와 실제 터미널 JSON 전체
- `docs/generated/experiment-b-embedding-runs.json`: 문서 재생성과 정확 비교에 사용하는 stdout 원시 이력

여러 번 같은 명령을 실행하면 실행 1을 기준으로 두 512차원 배열의 정확 일치 여부, 최대 좌표 차이,
코사인 차이와 SHA-256 지문을 비교한다. 표시 자릿수만 같다고 같은 것으로 처리하지 않는다. 기록 없이
일회성으로 확인하려면 다음 옵션을 사용한다.

```powershell
uv run --directory apps/api python -m scripts.experiment_embeddings --no-record
```

현재 실제 실행 결과는
[실험 B 실제 출력과 반복 비교](../../docs/generated/experiment-b-embedding-results.md)에서 확인한다.

이 실험 CLI만 실행할 때 DB와 migration은 필요 없다. PostgreSQL 하이브리드 검색까지 사용할 경우에는
배포 전에 `DATABASE_URL`/`DIRECT_URL`을 설정하고 새 model-filtered 함수를 적용한다.

```powershell
uv run --directory apps/api python -m alembic -c alembic.ini upgrade head
```

## 확인할 항목

1. provider가 `nvidia_nim`, model이 `nvidia/nemotron-3-embed-1b`인지 본다.
2. `native_dimensions=2048`, `output_dimensions=512`인지 본다.
3. 두 embedding 배열 길이가 각각 512인지 본다.
4. `norm_a`, `norm_b`가 부동소수점 오차 범위에서 1에 가까운지 본다.
5. cosine 값이 유한하고 `-1`에서 `1` 사이인지 본다.
6. 반복 실행에서 두 벡터의 전체 일치 여부와 최대 좌표 차이를 본다.
7. 점수를 확률이나 법률적 동일성으로 해석하지 않는다.

## 실패 동작

키 없음, 인증·quota·network·timeout, 잘못된 응답 index·개수·차원·유한값 또는 영벡터는 종료 코드
`2`와 안전한 JSON 오류를 표준 오류에 출력한다. provider 오류 전문이나 API key는 출력하지 않는다.
실패 시 OpenAI, 다른 NVIDIA 모델, 영벡터로 자동 대체하지 않으며 새 실행 결과도 기록하지 않는다.
API 호출은 성공했지만 생성 문서를 기록하지 못한 경우에도 `result_recording_failed`로 종료한다.

API 질문 흐름에서는 임베딩 실패 시 의미 후보만 생략하고 기존 키워드 검색을 계속한다. 검색 SQL은
같은 NVIDIA model, 512차원, embedding version 1인 문서 벡터만 비교한다. 기존 OpenAI 문서 벡터는
자동 변환되지 않으므로 의미 검색을 사용하려면 문서도 NVIDIA pipeline으로 다시 임베딩해야 한다.
