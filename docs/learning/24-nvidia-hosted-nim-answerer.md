# NVIDIA Hosted NIM 답변 경계

기준 시점: 2026-07-19

생성 provider는 검색과 임베딩에서 분리한다. `ANSWER_PROVIDER=nvidia_nim`이면 NVIDIA key의 존재만 생성 가용성을 결정하고, OpenAI key는 기존 임베딩을 사용할 때만 필요하다. 생성 provider 장애가 검색을 중단시키지 않으며 다른 모델로 조용히 전환하지 않는다.

기본 후보 `nvidia/nemotron-3-ultra-550b-a55b`는 NVIDIA가 한국어, frontier reasoning, long-context와 high-stakes RAG를 명시한 hosted 최상위 후보다. 모델 규모가 이 서비스의 법률 정확도를 증명하지는 않으므로 실제 법률 평가 전에는 `AI_MODE=off`를 유지한다.

Hosted NIM은 OpenAI-compatible Chat Completions를 사용한다. DraftAnswer JSON schema를 guided generation에 전달한 뒤에도 Pydantic 검증과 기존 citation grounding gate를 다시 실행한다. 빈 응답, invalid JSON, schema 불일치, timeout, quota와 grounding 실패는 모두 검색 전용 응답으로 돌아간다.

NVIDIA free endpoint는 prototype/trial이다. API key는 Vercel server secret에만 두고 브라우저·저장소·로그에 남기지 않는다. 24시간 공개 Production은 실제 rate limit, 데이터 보존, SLA와 partner/enterprise 계약을 확인한 뒤 승인해야 한다.
