# Serverless에서의 분산 취소

프로세스 메모리의 `asyncio.Task`는 그 프로세스만 취소할 수 있다. serverless scale-out에서 취소 endpoint가 다른 인스턴스에 도착하는 것은 예외가 아니라 정상 동작이므로, 로컬 registry miss를 곧바로 “없는 요청” 404로 해석하면 안 된다.

공유 DB의 취소 상태는 인스턴스 사이에서 전달되는 **의도**다. 실제 실행을 멈추려면 작업 인스턴스가 polling watcher로 그 상태를 감지하고 자기 태스크에 `cancel()`을 호출해야 한다. 이 둘 중 하나만 있으면 분산 취소가 완성되지 않는다.

등록과 취소는 경합할 수 있다. 취소가 먼저 도착했을 때 만료되는 tombstone을 저장하면 이후 등록이 즉시 중지되어 검색이나 모델 호출을 시작하지 않는다. 완료 후 늦게 온 취소는 오류가 아니라 `already_finished`라는 멱등 결과다.

PostgreSQL `LISTEN/NOTIFY`는 장기 연결과 살아 있는 구독자가 필요하고 이벤트 자체를 보존하지 않는다. Supavisor transaction pooler와 Vercel Function에서는 영속 상태를 권위값으로 두고 polling하는 편이 복구 가능하다. polling 주기는 취소 지연과 DB 부하의 교환이므로 운영 동시성을 측정해 정한다.

watcher는 배포 프로세스가 아니라 실행 중 질문에 붙는다. 따라서 서비스가 24시간 켜져 있어도 질문이 없으면 DB 조회는 없다. 같은 인스턴스 취소는 즉시 로컬 처리하고, 다른 인스턴스 신호 확인만 기본 2초로 두면 30초 질문당 약 15회 조회다. 무료 플랜의 egress/API 항목 안에 들어갈 가능성과 DB shared CPU의 안정성은 다른 문제이므로 Production 측정 없이 무료 보장을 선언하지 않는다.

애플리케이션 취소가 upstream 모델 사업자의 이미 시작된 GPU 계산과 과금을 반드시 회수한다는 뜻은 아니다. SDK await와 HTTP 연결은 끊을 수 있지만, provider가 별도 generation cancel API를 제공하면 그 계약도 함께 구현하고 실측해야 한다.
