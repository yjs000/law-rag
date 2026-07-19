# NVIDIA RAG 및 이벤트 기반 취소 실행 계획

기준일: 2026-07-19
상태: 로컬 구현 완료, 운영 연결은 0012·TD-014·TD-019로 이관

## 목표와 범위

NVIDIA Nemotron 생성과 검색 전용 모드를 함께 유지하고, 기존 512차원 OpenAI 임베딩을 재생성하지 않은 채 생성 입력을 제한한다. 분산 취소는 polling 대신 Supabase 영속 상태와 private Realtime Broadcast를 사용한다. 운영 migration, 비밀 등록, 유료 계약은 사용자 승인 전 제외한다.

## Agent별 TODO

### 주 Agent — 코드·통합

- [x] memory coordinator를 이벤트 대기로 바꾸고 polling 제거
- [x] 조문을 자르지 않는 생성 근거 문자 예산과 진단 추가
- [x] Supabase coordinator/Broadcast adapter 및 API 연결 범위를 `0012`의 운영 migration milestone로 이관
- [x] NVIDIA hosted Responses cancel capability smoke를 `TD-014`의 외부 key 검증으로 이관

### 취소 조사 Agent — 읽기 전용

- [x] NVIDIA cancel 계약, Supabase 무료 한도, Vercel 제약 확인

### RAG 감사 Agent — 읽기 전용

- [x] 벡터 변경 불필요 판정 및 비벡터 변경 범위 확인

### 부채 감사 Agent — 읽기 전용

- [x] AI/검색 전용 공통 P0~P2 및 사용자 병목 확인

## 결정

- 생성 모델 교체는 임베딩 공간을 바꾸지 않는다. `text-embedding-3-large` 512차원은 유지한다.
- 검색 전용은 NVIDIA·OpenAI 호출 없이 독립 동작한다.
- 취소 권위 상태는 DB 행이며 Broadcast는 깨우기 신호다. 구독 전후 행 확인으로 유실 경합을 막는다.
- Free 한도 보호값은 동시 Realtime 실행 100개, 취소 이벤트 50/s, 월 150만 메시지 경고다. 이는 Supabase Free 200 연결·100 msg/s·월 200만 메시지보다 여유가 있다.
- NVIDIA hosted Ultra 무료 endpoint는 개발/평가 Trial이다. 실제 사용자 대상 24시간 무료 Production으로 활성화하지 않는다.

## 검증

```powershell
$env:UV_CACHE_DIR='.uv-cache'
$env:PYTHONPATH='.'
uv run pytest tests/test_distributed_question_cancellation.py tests/test_generation_evidence_budget.py tests/test_ai_fallback.py tests/test_nvidia_nim_answerer.py
uv run ruff check app tests
```

## 사용자 병목

1. `NVIDIA_API_KEY`를 Preview secret에 등록하고 실제 capability smoke 허용
2. NVIDIA 데이터 보존·학습·국외 이전 및 Production 라이선스 확인
3. Supabase migration, private Broadcast RLS/trigger 적용 승인
4. Preview OAuth/NVIDIA 종단 검증 창구와 법률 전문가 평가

## 완료 결과

이 계획에서 외부 승인 없이 가능한 polling 제거와 생성 근거 예산 제한을 구현·검증했다. Supabase 운영 연결은 [분산 질문 취소 실행 계획](../active/0012-distributed-question-cancellation.md), NVIDIA 실호출과 정책 검토는 기술 부채 `TD-014`, `TD-019`가 단일 권위가 된다. 같은 차단 작업을 두 active 계획에서 중복 관리하지 않도록 이 계획을 완료 처리한다.

