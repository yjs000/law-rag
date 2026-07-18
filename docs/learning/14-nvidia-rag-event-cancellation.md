# NVIDIA RAG와 이벤트 기반 취소 브리핑

NVIDIA Nemotron은 답변 생성기이므로 기존 임베딩 벡터 공간과 독립적이다. 검색 전용은 생성기 장애와 무관하게 유지한다. AI 입력은 검색 순위대로 조문 전체를 선택하되 중간 절단하지 않고 서버 문자 예산을 적용한다. 실제 tokenizer 총예산은 hosted `/tokenize` 지원 확인 뒤 보완한다.

분산 취소의 권위는 Supabase 행이고 Realtime Broadcast는 실행 인스턴스를 깨우는 신호다. 이 구조는 유휴 polling 비용이 없지만 Broadcast 유실 가능성 때문에 구독 전후 상태 확인과 tombstone이 필요하다. NVIDIA 서버 내부 계산 취소는 hosted Responses background/cancel 지원을 실제 key로 검증하기 전에는 보장하지 않는다.
