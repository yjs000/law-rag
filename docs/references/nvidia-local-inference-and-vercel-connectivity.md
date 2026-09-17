# NVIDIA 로컬 추론과 Vercel 연결 검토

기준 시점: 2026-07-18

조사 범위: NVIDIA 공식 문서·NVIDIA 개발자 블로그·NVIDIA Research만 사용

목적: Windows PC의 무료 로컬 모델과 Vercel API 연결 대안을 결정하기 위한 1차 자료 메모

## 결론

현재 PC(`GeForce GTX 1650 4GB`, compute capability 7.5, Windows 10, driver 512.15)는 NVIDIA가 문서화한 **NIM on WSL2 지원 조건을 충족하지 않는다**. NVIDIA 문서는 Windows 11 23H2 이상, 시스템 RAM 12GB 이상, GeForce RTX 40/50 시리즈를 전제로 한다. 따라서 이 PC에서 NIM 또는 최근 NVIDIA Nemotron 3 Nano 4B를 운영 경로로 바로 채택하면 안 된다.

우선순위는 다음과 같다.

1. 현 PC에서는 기존 `Qwen3:4b + Ollama` 후보를 로컬 개발용으로 실측한다. 이는 NVIDIA NIM 인증 경로가 아니며 4GB VRAM에서 GPU 전량 적재를 가정하지 않는다.
2. 공개 서비스는 Vercel이 집 PC에 직접 접속하지 않게 한다. Supabase의 인증된 작업 큐를 집 PC가 outbound polling하고 결과만 되돌리는 중계 구조를 우선 검토한다.
3. RTX 40/50 Windows 11 PC로 교체한 뒤에만 NIM on WSL2 또는 Nemotron 3 Nano 4B를 다시 평가한다.
4. 빠른 원격 검증은 NVIDIA-hosted NIM API를 사용하되 무료 범위는 프로토타이핑이며 production SLA·지원으로 해석하지 않는다.

## 2026-07-19 Hosted NIM 결정

사용자 결정에 따라 생성 기본 후보를 `nvidia/nemotron-3-ultra-550b-a55b`로 변경한다. NVIDIA 모델 카드는 550B total/55B active, 한국어 지원, 최대 1M context, frontier reasoning과 high-stakes RAG 용도를 명시하고 hosted free endpoint를 제공한다. 이는 모델 규모·NVIDIA 분류 기준의 최상위 후보이지 이 프로젝트의 법률 정확도 실측 결과는 아니다.

호출 계약:

- Base URL: `https://integrate.api.nvidia.com/v1`
- Model: `nvidia/nemotron-3-ultra-550b-a55b`
- 초기 출력 상한: 4,096 tokens
- 초기 thinking: off. 구조화 출력과 grounding 성공률을 먼저 측정한 뒤 별도 평가에서 medium/full reasoning을 비교
- JSON schema guided generation 후 Pydantic 검증과 기존 인용 gate를 모두 통과해야 노출
- timeout/429/잘못된 JSON/grounding 실패 시 검색 전용 결과 유지

Hosted free endpoint는 NVIDIA API Trial Terms가 적용되는 prototype 서비스다. NVIDIA 공식 Run NIM Anywhere 문서는 Developer Program hosted endpoint를 prototyping 용도로 설명하고 Production 전환에는 partner endpoint, self-hosted 또는 NVIDIA AI Enterprise를 안내한다. 따라서 24시간 공개 배포의 영구 무료 backend로 확정하지 않는다.

사용자 설정:

1. NVIDIA Developer 계정으로 모델 페이지에서 API key 생성
2. 키 원문을 채팅이나 저장소에 보내지 않고 Vercel의 Preview/Production `NVIDIA_API_KEY` secret에 각각 등록
3. 당시에는 `NVIDIA_ANSWER_MODEL=nvidia/nemotron-3-ultra-550b-a55b`를 등록했다. 현재 설정은 아래 2026-09-17 전환 결정을 따른다.
4. 실제 endpoint smoke와 법률 고정 평가셋을 실행할 때만 AI를 활성화
5. Trial rate limit·데이터 보존·Production 가격을 NVIDIA 계정의 실제 계약 화면에서 확인하고 승인

## 2026-09-17 Hosted generation model 전환

Ultra의 일반 호출과 production routing 호출이 같은 시간대에 hosted function `404`를 반환한 반면,
공식 Getting Started 형식의 `nvidia/nemotron-3.5-lightning-30b-a3b` 호출은 `200`으로 성공했다.
따라서 현재 generation 기본값을 3.5 Lightning으로 전환한다. 답변·질문 라우팅·초기 clarification은
단일 `NVIDIA_GENERATION_MODEL`을 composition root에서 주입받고, 임베딩은
`NVIDIA_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b`로 별도 유지한다. 모델 교체 시 역할별 설정을
각각 수정하지 않는다.

### 2026-09-17 로컬 실호출 비교 권한 계약

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 로컬 설정 | `apps/api/.env.local` | 폐기된 두 generation 설정을 단일 `NVIDIA_GENERATION_MODEL`로 교체 | 기존 secret은 읽거나 출력하지 않음 | gitignored 로컬 파일 수정 | 동일 모델 주입 검증 | Approved — 2026-09-17 사용자 요청 | 모델 관련 비밀 아닌 줄만 변경, 커밋 금지 |
| NVIDIA 직접 호출 | `https://integrate.api.nvidia.com/v1/chat/completions` | Nemotron 3.5 POST, 60초 이내 | 기존 `NVIDIA_API_KEY`, 일반 테스트 질문 | NVIDIA 측 요청 로그 가능, 원문 응답 미보존 | 공식 endpoint 기준선 확인 | Approved — 2026-09-17 사용자 요청 | 키·원문 응답 출력 금지, 상태·지연·안전 요약만 기록 |
| 프로젝트 API 호출 | `http://127.0.0.1`의 `/v1/questions` | 같은 일반 질문 POST | 로컬 설정, NVIDIA key, 원격 검색용 기존 자격 증명 가능 | 익명 호출, provider·DB 측 운영 로그 가능 | 실제 route/answer 경로 비교 | Approved — 2026-09-17 사용자 요청 | 개인정보 금지, 원격 데이터 쓰기·배포 금지 |
| Git release state | `origin/main` | 정책·문서 커밋과 push | repository content, secret 없음 | 원격 Git 이력 추가 | 지속 승인과 검증 결과 공유 | Approved — 2026-09-17 사용자 요청 | `.env.local` 제외와 diff 검증 후 push |
| 배포 환경 | Vercel project/env | 배포 또는 환경변수 변경 | 해당 없음 | 없음 | 이번 로컬 비교 범위 밖 | Not required — 2026-09-17 | 실행 금지 |

결정 기록: 사용자는 `.env.local`의 비밀이 아닌 generation model 설정 변경, 동일한 일반 질문을 이용한
NVIDIA 직접 호출과 로컬 프로젝트 API 호출 비교, 정책·문서의 commit과 `origin/main` push를 승인했다.
비밀값·개인 사건자료·원문 provider 응답은 출력하거나 저장하지 않는다.

### 2026-09-17 실호출 비교 결과

개인정보가 없는 동일 질문으로 비교했으며 provider 응답 원문은 보존하지 않았다.

| 경로 | 설정 | 결과 | 지연 | 판정 |
| --- | --- | --- | --- | --- |
| NVIDIA 공식 OpenAI 호환 endpoint | 3.5 Lightning, 단순 chat completion, 128 tokens | HTTP 200, 요청·응답 model 일치, content 존재 | 5.286초 | endpoint와 key 정상 |
| 로컬 `/v1/questions` | 프로젝트 기본 route timeout 8초 | HTTP 200 안전 응답, `routing_unavailable` | 13.067초, 재시도 17.922초 | end-to-end 실패 |
| 프로젝트 router adapter | 진단용 route timeout 20초 | provider HTTP 200, `legal_search`, confidence 0.95 | 6.186초 | 모델·구조화 라우팅 호환 |
| 로컬 `/v1/questions` | 진단용 route timeout 20초 | HTTP 503 | 47.517초 | end-to-end 실패 |

기본 라우터의 안전 로그는 두 시도 모두 `failure_kind=timeout`, `upstream_status=null`을 기록했다. 따라서
처음 두 로컬 실패는 모델 ID나 endpoint 404가 아니라 8초 route budget 초과다. 20초 router 단독 호출은
성공했으므로 3.5가 프로젝트의 라우팅 schema와 호환된다는 점도 확인했다. 마지막 503은 관측된 총 지연과
현재 request/answer budget을 함께 보면 이후 generation 단계의 시간 예산 소진으로 추정되지만, 응답 원문을
기록하지 않았으므로 확정 원인으로 쓰지 않는다. 결론적으로 직접 호출은 성공했지만 현재 프로젝트 기본
시간 예산에서는 전체 API가 안정적으로 성공하지 않는다.

## “NVIDIA가 최근 무료 배포했다”는 주장 확인

서로 다른 세 가지 사실이 섞이기 쉽다.

- NVIDIA는 2024-07-29 Developer Program 회원에게 다운로드 가능한 NIM을 개발·테스트·연구 용도로 무료 제공한다고 발표했다. 당시 범위는 최대 2 nodes/16 GPUs였고 production에는 NVIDIA AI Enterprise가 안내됐다. 이는 최근 새로 무료화된 Windows runtime이라는 뜻은 아니다.
- NVIDIA는 2026-03-17 Nemotron 3 Nano 4B를 GeForce RTX 사용자를 위한 최신 소형 open model로 발표했고, RTX PC에서 로컬 agent를 “private and free”로 실행하는 용도를 제시했다.
- NIM은 모델이 아니라 컨테이너형 추론 microservice/runtime이다. 최신 NIM LLM은 OpenAI-compatible `/v1/chat/completions`, `/v1/responses`, tokenization과 cancellation endpoint를 제공한다.

무료 조건은 production 권리와 동일하지 않다. Developer Program NIM은 개발·테스트·연구/실험 범위이고, NVIDIA는 production 보증·API 안정성·지원에는 NVIDIA AI Enterprise 또는 partner endpoint를 안내한다. 또한 모델 weight의 별도 라이선스는 해당 모델 카드에서 확인해야 한다. NIM의 `/v1/license`로 실행 중 라이선스 메타데이터와 전문을 확인할 수 있다.

## Qwen3:4b 대안 가능성

NVIDIA NeMo AutoModel은 Qwen3 계열 0.6B~32B와 `Qwen3ForCausalLM`을 지원하며, Qwen3-4B가 계열에 존재함을 문서화한다. 그러나 최신 Certified NIM 목록에서 확인되는 Qwen3 dense model은 Qwen3-32B이고, **Qwen3-4B용 인증 NIM/RTX profile은 확인되지 않았다**. NeMo의 학습·미세조정 지원을 4GB 소비자 GPU용 NIM 실행 지원으로 해석하면 안 된다.

최근 NVIDIA 대안인 Nemotron 3 Nano 4B는 RTX PC용으로 발표됐지만 현재 GTX 1650은 RTX AI PC가 아니고 NIM on WSL2 공식 조건 밖이다. 따라서 현재 장비에서는 다음처럼 판단한다.

| 후보 | 현재 PC | 용도 판단 |
|---|---|---|
| Qwen3:4b + Ollama/llama.cpp 계열 | 실측 필요 | 가장 현실적인 개발 후보. NVIDIA 인증 NIM은 아님 |
| Qwen3-4B + model-free NIM | 비권장 | architecture 지원과 현 GPU/Windows 지원은 별개이며 VRAM·OS 조건 미충족 |
| Nemotron 3 Nano 4B | 비권장 | 최신 open RTX 후보지만 GTX 1650은 공식 RTX PC 경로 밖 |
| NVIDIA-hosted NIM API | 가능 | PC GPU 불필요, 인터넷·외부 처리 필요, 무료는 prototype 범위 |

## 하드웨어와 runtime 체크

현재 PC에서 확인한 값:

```text
GPU: NVIDIA GeForce GTX 1650
VRAM: 4096 MiB
Compute capability: 7.5
Driver: 512.15
OS: Windows 10 Pro
```

NIM on WSL2 공식 최소선은 Windows 11 23H2+, RAM 12GB+, RTX 40/50 GeForce다. 일반 NIM의 generic profile 설명은 compute capability 7.0 이상과 충분한 GPU memory가 있으면 동작할 수 있다고 하지만 “보장하지 않음”을 명시한다. 이 generic 문구가 Windows/WSL2 지원표를 덮어쓰지 않는다.

향후 RTX 장비 평가 시 사용자가 먼저 확인할 항목:

1. `nvidia-smi`의 GPU명, VRAM, driver와 free memory 95% 확보 가능 여부
2. Windows 11 23H2 이상, WSL2, RAM 12GB 이상
3. 대상 모델의 NIM support matrix/profile, 필요한 disk와 precision
4. NVIDIA Developer Program 가입과 NGC personal API key 발급
5. NIM WSL2 installer 또는 문서화된 container 설치 후 `/v1/health/ready`, `/v1/models`, `/v1/license` 확인
6. 고정 법률 평가셋으로 한국어 구조화 출력, 인용 gate, p95, VRAM과 cold start 측정

NGC API key는 이미지·모델 다운로드용 비밀이다. Vercel, 브라우저, 저장소에 노출하지 않고 PC의 비밀 저장소에만 둔다.

## Vercel에서 Windows PC로 연결하는 선택지

### 1순위: outbound 작업 중계

이 저장소에는 이미 Vercel/Supabase와 고정 IP Windows collector 경계가 있다. 같은 원칙으로 Vercel이 인증된 작업을 DB/queue에 넣고 PC worker가 outbound TLS로 가져가 추론한 뒤 결과를 쓰는 구조가 가장 안전하다.

- 집 공유기 port forwarding과 공인 inbound listener가 없다.
- PC가 꺼져 있으면 queue에 남기고 timeout 후 search-only로 폴백할 수 있다.
- job에는 사용자·만료시각·nonce·상태를 두고, 원문 전문이나 비밀을 로그에 남기지 않는다.
- service-role credential을 브라우저에 주지 않고 Vercel/PC에 분리한다.
- 결과는 기존 인용 검증을 다시 통과해야 한다.

이는 NVIDIA 제품 기능이 아니라 현재 저장소 보안 계약에서 도출한 설계 제안이다. 구현 전 Supabase 공식 queue/realtime 보안 계약은 별도 1차 자료 조사가 필요하다.

### 2순위: NVIDIA-hosted NIM endpoint

Vercel은 NVIDIA HTTPS endpoint로 outbound 호출한다. 집 PC 가용성·CGNAT·동적 IP 문제가 없고 OpenAI-compatible API를 쓸 수 있다. 반면 질문과 검색 근거가 외부로 전송되며 무료 Developer Program endpoint는 prototype 용도다. production 비용·rate limit·지역·보존 정책은 실제 catalog 계약 화면에서 확정해야 한다.

### 3순위: 인증된 reverse tunnel/gateway

NVIDIA 자료는 NIM 자체의 TLS와 mTLS를 지원한다. 최신 NIM proxy에서 `NIM_SSL_MODE=TLS|MTLS`, 인증서·키·CA 경로를 설정할 수 있다. 그러나 NIM은 `x-api-key`를 검증하지 않는다고 명시하므로 헤더 하나만 붙여 인터넷에 노출하면 인증이 되지 않는다.

터널을 택한다면 최소 조건은 다음과 같다.

- tunnel agent가 PC에서 outbound 연결하고 공유기 port forwarding은 금지
- 공개 hostname에 CA 발급 TLS, gateway에서 독립 인증·rate limit·body limit·timeout
- 가능하면 gateway-to-NIM도 mTLS, NIM은 loopback/private interface에만 bind
- Vercel secret과 PC secret 분리·회전, replay 방지 nonce/HMAC 또는 검증된 identity-aware proxy
- readiness/metrics/license endpoint는 공개하지 않고 inference path만 allowlist
- PC offline·timeout 시 search-only 폴백, circuit breaker와 queue 제한

특정 tunnel vendor의 보안·가격·Vercel 호환성은 NVIDIA 1차 자료만 사용한다는 이번 조사 범위에서는 비교하지 않았다. Cloudflare Tunnel, Tailscale Funnel/VPN, ngrok 같은 후보를 결정하려면 각 vendor와 Vercel 공식 문서를 별도로 조사해야 한다.

### 금지: WSL2 portproxy를 인터넷에 직접 공개

NVIDIA WSL2 문서는 다른 LAN client를 위해 Windows `netsh interface portproxy`와 firewall inbound rule을 안내하지만, TLS·사용자 인증·rate limit을 자동 제공하지 않는다. 이 문서를 공용 인터넷 공개 지침으로 확대 해석하지 않는다. 특히 NIM의 기본 SSL mode는 disabled이고 `x-api-key`도 검증하지 않으므로 직접 포트 공개는 금지한다.

## 비용·라이선스 판단표

| 항목 | 확인된 범위 | production 판단 |
|---|---|---|
| Developer Program downloadable NIM | 개발·테스트·연구/실험, 최대 16 GPUs 안내 | 무상 production 권리로 간주하지 않음 |
| NVIDIA-hosted NIM API | 무료 prototype access 안내 | SLA·rate limit·비용을 catalog 계약에서 재확인 |
| NVIDIA AI Enterprise | 90일 trial 안내 | 이후 가격은 영업/partner 견적 필요 |
| 로컬 전력·장비 | cloud inference 비용 없음 | 전기료, GPU 교체, uptime, 장애 대응은 사용자 부담 |
| 모델 weight | 모델별 별도 조건 가능 | `/v1/license`와 모델 카드 고정 후 승인 |

## 사용자가 해야 할 설정: 우선순위

### 지금 할 일

1. 현재 PC에서 Ollama Qwen3:4b의 실제 GPU/CPU offload, peak RAM/VRAM, 한국어 tokens/s를 측정한다.
2. 로컬 endpoint는 `127.0.0.1`에만 bind하고 외부 공개하지 않는다.
3. Vercel 연결은 outbound queue PoC부터 만든다. job TTL, 최대 prompt 크기, 동시 실행 1, search-only timeout을 먼저 정한다.
4. 생성 provider와 embedding provider의 키·활성 조건을 분리한다.
5. 법률 고정 평가셋의 구조화 성공률과 인용 검증률을 통과하기 전 production AI를 켜지 않는다.

### 장비 교체 후 할 일

1. RTX 40/50, Windows 11 23H2+, 충분한 VRAM/RAM 장비를 확정한다.
2. NIM support matrix에서 정확 모델 profile을 확인하고 Developer Program/NGC key를 준비한다.
3. NIM WSL2 설치 후 localhost smoke test, 실제 tokenizer endpoint, TLS/mTLS와 health probe를 검증한다.
4. direct tunnel보다 outbound queue를 우선 유지하고, 터널이 꼭 필요할 때만 vendor 공식 보안 검토를 추가한다.

## NVIDIA 공식 참고자료

- [NIM for Developers와 무료 prototype/development 범위](https://developer.nvidia.com/nim)
- [Developer Program NIM 무료 접근 발표(2024-07-29)](https://developer.nvidia.com/blog/access-to-nvidia-nim-now-available-free-to-developer-program-members/)
- [NIM LLM 최신 개요와 model-free NIM](https://docs.nvidia.com/nim/large-language-models/latest/introduction.html)
- [NIM LLM API와 tokenization/cancellation/license endpoint](https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html)
- [NIM TLS/mTLS와 CORS 설정](https://docs.nvidia.com/nim/large-language-models/latest/reference/advanced-configuration.html)
- [NIM on WSL2 요구사항](https://docs.nvidia.com/nim/wsl2/1.0.0/getting-started.html)
- [WSL2 port forwarding 안내](https://docs.nvidia.com/nim/wsl2/1.0.0/running-client-port-forwarding.html)
- [NIM LLM supported models](https://docs.nvidia.com/nim/large-language-models/1.15.0/supported-models.html)
- [NeMo AutoModel Qwen3 coverage](https://docs.nvidia.com/nemo/automodel/model-coverage/large-language-models/qwen-3)
- [RTX PC의 Nemotron 3 Nano 4B 발표(2026-03-17)](https://blogs.nvidia.com/blog/rtx-ai-garage-gtc-2026-nemoclaw/)
- [RTX PC용 open-source inference 최적화 발표(2026-01-05)](https://developer.nvidia.com/blog/open-source-ai-tool-upgrades-speed-up-llm-and-diffusion-models-on-nvidia-rtx-pcs)
- [NGC model download와 API key](https://docs.nvidia.com/nim/large-language-models/latest/deployment/model-download.html)
- [Nemotron 3 Ultra hosted endpoint와 호출 예제](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b?nim=hosted)
- [Nemotron 3 Ultra 모델 카드](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard)
- [NVIDIA hosted NIM prototype/Production 계약 안내](https://docs.api.nvidia.com/nim/re/docs/run-anywhere)
- [NIM structured generation](https://docs.nvidia.com/nim/large-language-models/1.15.0/structured-generation.html)

## 미확정 사항

- Qwen3-4B와 Nemotron 3 Nano 4B의 현재 장비 실제 성능·메모리
- Nemotron 3 Nano 4B의 정확 weight license 전문과 사용하려는 runtime 배포 artifact
- NVIDIA-hosted endpoint의 production 가격, 한국 region, rate limit과 데이터 보존
- tunnel vendor의 TLS termination, identity, 고정 egress와 Vercel 호환성

이 항목들은 사실처럼 확정하지 않고 실제 장비 smoke test와 해당 공급자 공식 계약 검토 후 결정한다.
