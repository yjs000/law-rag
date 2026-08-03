# 학습 노트

각 마일스톤은 개념, 선택 이유, 데이터 흐름, 직접 실행 명령, 다음 학습 주제를 남긴다. 파일 번호는
작성 순서를 나타내며, 아래 목차는 다시 찾기 쉽도록 주제별로 묶었다.

## 시스템 구조와 런타임 기초

- [01 런타임과 모노레포](01-runtime-and-monorepo.md)

## 법령 수집, 시간과 저장소

- [02 법령 수집과 시간 모델](02-ingestion-and-time.md)
- [05 독립 수집기와 시간 효력](05-independent-collector.md)
- [10 Supavisor 런타임과 마이그레이션 연결](10-supavisor-runtime-and-migrations.md)
- [11 Supabase collector 영속화](11-supabase-collector-persistence.md)

## 검색, RAG, 평가와 임베딩

- [03 하이브리드 RAG와 인용](03-hybrid-rag-and-citations.md)
- [07 검색·원문 계보·답변 검증 기초](07-retrieval-storage-and-grounding-foundations.md)
- [13 조문 경로 검색과 빈 결과 계약](13-provision-path-and-empty-results.md)
- [18 질문·근거·답변 평가 계약](18-answer-quality-evaluation-contract.md)
- [19 AI 없는 자연어 검색과 단계별 진단](19-natural-language-retrieval-observability.md)
- [20 RAG 검색 시스템 디버깅과 로직 개선](20-rag-retrieval-debugging-and-improvement.md)
- [22 기존 법령 파서를 재사용한 일반 텍스트 청킹 실험](22-existing-parser-chunking-experiment.md)
- [24 NVIDIA NIM 임베딩 provider 교체](24-nvidia-nim-embedding-provider.md)
- [25 임베딩의 전체 개념: 차원, 내적, 코사인 유사도와 축약](25-embedding-concepts.md)
- [26 법률 구조 범위를 보존하는 로컬 벡터 검색](26-local-vector-search.md)
- [27 Dense 검색 후보와 답변 문맥의 분리](27-dense-retrieval-candidates-and-context.md)
- [31 RAG 평가 지표: 검색, 문맥, 답변과 근거 부족 판정](31-rag-evaluation-metrics.md)
- [32 NVIDIA RAG 평가를 한 질문으로 이해하기](32-nvidia-rag-evaluation-reading-guide.md)

## 모델 실행, 폴백과 취소

- [08 채팅 UI와 모델 선택 경계](08-chat-ui-and-model-choice.md)
- [14 NVIDIA RAG와 이벤트 기반 취소](14-nvidia-rag-event-cancellation.md)
- [15 Terra 런타임 폴백 계약](15-terra-runtime-fallback-contract.md)
- [16 Web Terra 폴백 상태 동기화](16-web-terra-fallback-state.md)
- [22 토큰 컨텍스트와 서버 작업 취소](22-token-context-and-server-cancellation.md)
- [23 Serverless에서의 분산 취소](23-distributed-cancellation-on-serverless.md)
- [24 NVIDIA Hosted NIM 답변 경계](24-nvidia-hosted-nim-answerer.md)

## 인증, 이력, 개인정보와 사용량 제한

- [04 웹 인증 상태, 질문 이력과 내보내기](04-web-auth-history-and-exports.md)
- [06 목업 인증, 질문 이력, 검색 전용 폴백](06-mock-api-history-and-fallback.md)
- [09 인증 UI와 구현 경계](09-auth-ui-and-implementation-boundary.md)
- [14 Vercel 익명 IP rate limit](14-vercel-anonymous-rate-limit.md)
- [16 Supabase Google 인증과 질문 이력 연결](16-supabase-google-auth-and-history.md)
- [17 로그인·익명 전체 흐름의 인증 경계](17-authenticated-and-anonymous-flow-edges.md)
- [21 대화 이력 페이지네이션과 인증 지연](21-conversation-history-and-auth-latency.md)
- [21 질문 이력 보존 정리와 감사 가능한 DB 작업](21-history-retention-job.md)

## 웹 결과 상태와 사용자 경험

- [12 웹의 빈 검색 결과 상태](12-web-empty-search-results.md)
