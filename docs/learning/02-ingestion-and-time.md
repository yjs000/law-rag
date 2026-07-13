# 02 법령 수집과 시간 모델

## 개념과 선택 이유

정규화는 JSON/XML처럼 모양이 다른 입력을 동일한 도메인 객체로 바꾸는 과정이다. 멱등 수집은 같은 문서/MST를 다시 실행해도 중복되지 않는 성질이다. 공포일은 발표일이고 시행일은 법적 효력 시작일이다.

JSON은 다루기 쉽고 XML은 경로별 호환성이 높다. JSON 도메인 검증 실패에만 XML로 폴백한다. 조·항·호·목 경계를 유지하면 인용에서 원문 위치로 돌아갈 수 있다.

## 데이터 흐름

검색 API → 정확 명칭 확인 → 본문 JSON → 검증 실패 시 XML → 정규화 → raw Storage → PostgreSQL → 임베딩.

실계약 결과 9개 모두 JSON으로 정규화됐다. Open API는 등록된 공인 출구 IP를 검증하므로 예약 수집은 그 IP를 사용하는 self-hosted runner에서 실행한다. Tailscale `100.64.0.0/10` 주소는 등록 대상이 아니다.

## 직접 실행

```powershell
cd apps/api
$env:LAW_OPEN_API_OC="발급받은 OC"
uv run python -m scripts.sync
uv run pytest tests/test_law_client.py tests/test_parsers.py
```

## 다음 학습 주제

연혁 MST, 시행 종료일 계산, 부칙·별표 구조와 삭제 데이터 API를 학습한다.
