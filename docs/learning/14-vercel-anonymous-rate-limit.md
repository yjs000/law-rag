# Vercel 익명 IP rate limit

## 무엇을 바꿨나

Vercel Function의 `request.client.host`는 실행 프록시 주소일 수 있어 모든 익명 사용자가 같은 quota를 공유할 수 있다. Production에서는 Vercel이 제공하는 `x-forwarded-for` 공개 IP를 정규화한 뒤 날짜별 HMAC에 넣도록 바꿨다. IP 원문은 DB나 로그에 저장하지 않는다.

AI 질문은 IP별 하루 3회라는 기존 `ai` 한도를 유지한다. 검색 전용 요청은 기존 `search` 한도와 별도 카운터를 사용하므로 AI 한도를 소진해도 검색 quota에는 영향을 주지 않는다.

## 왜 헤더를 항상 믿지 않나

일반 서버에서 클라이언트가 보낸 `x-forwarded-for`를 그대로 믿으면 공격자가 값을 바꿀 때마다 새 사용자처럼 보일 수 있다. Vercel 공식 문서는 Vercel이 이 헤더를 덮어써 IP 위조를 방지한다고 설명한다. 따라서 현재 코드가 Vercel에 배포되는 Production일 때만 단일 헤더 값을 신뢰한다.

개발·테스트에서는 전달 헤더를 무시하고 실제 소켓 peer를 사용한다. Production에서 헤더가 없거나 쉼표가 든 체인·잘못된 IP라면 공격자가 고른 일부 값을 쓰지 않고 `unresolved-client` 하나로 합쳐 실패 폐쇄한다. IPv4와 IPv4-mapped IPv6도 같은 주체로 정규화한다.

## 검증한 경계

- 서로 다른 공개 IP는 각각 AI 3회를 사용한다.
- 같은 IP의 네 번째 AI 사용은 429가 된다.
- AI와 검색 전용 카운터는 분리된다.
- 로컬에서 위조한 전달 헤더는 무시된다.
- 복수 전달 IP와 잘못된 IP를 바꿔도 quota 주체가 회전하지 않는다.

## 한계와 다음 단계

IP 제한은 IP를 바꾸는 VPN·이동통신 재접속을 완전히 막지 못하고, 공유 NAT에서는 여러 사람이 하나의 한도를 공유한다. 베타 이후에는 OpenAI 프로젝트 비용 상한, Vercel WAF, 로그인 사용자별 quota와 이상 사용 관측을 함께 적용해야 한다. Vercel 앞에 별도 프록시를 둘 경우에는 Vercel Trusted Proxy 지원을 포함해 신뢰 경계를 다시 검토한다.
