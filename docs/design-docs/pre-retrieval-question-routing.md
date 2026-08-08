# 질문 사전 라우팅 설계 (tier1/tier2)

상태: 승인
작성일: 2026-08-07
최종 갱신: 2026-08-08

전체 실행 이력·calibration 수치·미해결 과제는 [0028 실행 계획](../exec-plans/active/0028-pre-retrieval-question-routing.md)에 있다. 이 문서는 "왜 이 구조인가"의 현재 결론만 담는다.

## 목표

`terra`(AI) 답변 요청은 embedding·법령 검색을 실행하기 전에, 질문이 애초에 법령 corpus만으로 답이 되는 유형인지 먼저 가른다. 법령으로 답할 수 없는 질문(실시간 정보, 사용자 문서 대조가 필요한 질문)을 억지로 검색하면 무관한 법령이 AI 문맥에 섞여 들어간다 — 실험 D-10/D-10-R1에서 실제로 관측된 문제다.

## 문제: 임베딩 유사도는 화용론적 충분성을 재지 못한다

처음에는 tier2를 "질문 embedding과 route별 예시 embedding의 최근접 유사도 + threshold"로 만들었다. 이 방식은 calibration에서 구조적으로 실패했다 — `"허가나 신고가 필요한지 어떻게 구분하나요"`(일반 설명으로 충분, `legal_search`)와 `"...에 따라 어떻게 달라지나요"`(사용자 사실이 있어야 갈림, `clarification_required`)는 어휘가 거의 같아 임베딩이 가깝게 붙지만, 실제 차이는 주제가 아니라 **"이 질문에 이미 검색을 실행할 만큼 충분한 정보가 담겼는가"**라는 화용론적(pragmatic) 판단이다. 실측에서 오답 매칭의 유사도(0.7185)가 정답 매칭 전체(0.326~0.6947)보다 순위가 높게 나와, 유사도 크기와 정답 여부가 사실상 무관했다.

임베딩 모델(`nvidia/nemotron-3-embed-1b`)은 "이 두 텍스트가 같은 주제를 다루는가"를 학습하도록 만들어졌다 — 라우팅이 필요로 하는 판단은 애초에 이 모델의 학습 목적이 아니다. 같은 문제를 다루는 공인 문헌(Self-RAG, Adaptive-RAG, FLARE의 adaptive retrieval; ClariQ/Qulac, INTENT-SIM의 clarification necessity detection)도 전부 이 판단을 임베딩 거리가 아니라 **모델 자신의 판단이나 답변 시뮬레이션의 엔트로피**로 만든다는 점이 공통적이다.

## 아키텍처: tier1(결정적 규칙) + tier2(LLM judgment)

라우팅은 두 단계를 순서대로 시도하고, 앞 단계가 확신 있게 판정하면 뒷 단계를 호출하지 않는다 — LLM 호출은 corpus 크기가 아니라 **모호함의 크기**에 비례한다.

- **tier1** (`app/domain/routing.py`의 `route_tier1`, 비용 0): Kiwi(`kiwipiepy`) 형태소 분석 기반 결정적 키워드·정규식 규칙. 한국어는 조사·어미 활용이 많아 표면형을 손으로 나열하면 금방 놓치므로, 승인된 질문은행 1,000문항 전체를 형태소 분석해 검증·확장한 사전([tier1-term-dictionary-analysis-v1.json](../../apps/api/evaluation/tier1-term-dictionary-analysis-v1.json))을 쓴다. 빈도 기반 후보는 자동 추출하되 채택 여부는 전부 사람이 읽고 판단했다 — 표면 어휘를 곧 화용론적 의미로 가정하지 않기 위해서다. "정말 답할 수 없는 것만 타이트하게 거른다"는 원칙에 따라 위양성(답할 수 있는데 차단)을 줄이는 쪽으로 조정돼 있다.
- **tier2** (`route_tier2`, `app/adapters/nvidia_nim_route_classifier.py`): tier1이 확신하지 못하면 질문 원문 + route 정의(10줄 미만)를 NVIDIA NIM LLM에 직접 판단시킨다. 기존에 tier2가 계산하던 최근접 예시 유사도는 버리지 않고, "참고용 힌트이며 최종 판단 근거로 쓰지 말 것"이라는 경고와 함께 프롬프트에 넣는다 — 이미 계산된 결과라 추가 비용이 없고 anchoring bias만 프롬프트로 통제한다. 라우팅 답변 생성 모델과는 별도 client/model을 쓴다 — 라우팅 오판이 답변 생성 품질에 번지지 않게 하기 위해서다.
- **tier3**: 미확정, 사용하지 않는다. INTENT-SIM류(여러 가정으로 답을 시뮬레이션해 갈리는지 확인)가 후보지만 tier2 운영 데이터가 쌓이기 전에는 착수하지 않는다.

## route 계약과 사용자 응답

판정은 4가지로 나온다.

- `legal_search`: 정상적으로 embedding·검색·생성으로 진행한다.
- `clarification_required`: 설비용량 등 빠진 사용자 사실을 **텍스트로** 먼저 요청한다. 서버가 이전 turn과 새 turn을 자동 병합하지 않는다 — 대신 원 질문과 누락 필드를 채운 "복사용 완성 질문 템플릿"을 반환하고, 사용자가 다음 메시지에 원 질문과 추가 정보를 모두 포함해 한 번에 재제출하게 한다. 이 방식은 서버 측 대화 상태·turn 병합·추가 모델 호출이 없어 가장 단순하고 비용이 낮다.
- `realtime_required` / `external_document_required`: 시점에 따라 변하는 정보(올해 예산, 현재 가격)나 사용자 문서 대조(계약서, 정산서)가 필요한 질문은 법령 검색을 실행하지 않고 **결정적 차단 메시지로 끝난다** — embedding·검색·LLM 호출 0회. 실시간 정보원이나 문서 업로드 기능 자체를 만들지 않기로 범위를 좁혔기 때문에 후속 수집 흐름이 없다. tier2가 판정한 경우 LLM이 이미 생성한 판단 근거(`RouteJudgment.reason` → `RouteDecision.explanation`)를 차단 메시지 뒤에 그대로 노출한다 — 추가 LLM 호출 없이 질문에 맞춘 구체적 안내를 준다.

## 실패 안전과 비용 경계

tier2 호출 자체가 실패(NVIDIA 오류·timeout)해도 요청을 500으로 죽이지 않고 `legal_search`로 안전하게 진행한다 — 근거 없이 차단 쪽을 기본값으로 두면 답할 수 있는 질문을 막는 피해가, 검색 쪽을 기본값으로 두는 피해보다 크다는 원칙을 실패 경로에도 그대로 적용한다. 입력은 질문 텍스트와 법령 corpus뿐이며, 실시간 데이터 source 연동이나 사용자 문서 저장소는 이 설계의 범위 밖이다. 관측(`emit_route_outcome`)은 route·tier·reason_code·confidence만 기록하고 질문 원문은 남기지 않는다.

## 알려진 한계와 후속 과제

fixture(14케이스) 실측에서 tier2 LLM이 "확인/대조" 같은 표현을 과대 해석해 legal_search 질문을 `external_document_required`로 잘못 차단한 사례가 2건 나왔다(TD-024) — tier1 키워드 매칭 때와 같은 종류의 실수(표면 표현을 화용론적 판단으로 오해)를 LLM도 반복할 수 있다는 뜻이다. "LLM이면 다 해결된다"고 가정하지 않고, 트래픽이 쌓이면 [0033](../exec-plans/todo/0033-traffic-based-routing-calibration-review.md)에서 tier2 자체의 calibration을 재검토한다.

## 결정 기록

- 2026-08-07: 입력을 질문 텍스트 + 법령 corpus로만 확정하고, `clarification_required`는 서버 자동 병합 없는 재제출 템플릿으로, `realtime_required`/`external_document_required`는 후속 수집 흐름 없는 결정적 차단으로 범위를 좁혔다.
- 2026-08-08: tier2를 "임베딩 최근접 + threshold gate"에서 "질문 원문 + route 정의를 LLM에 직접 판단시키는" 방식으로 교체했다. 공인 문헌 조사 결과 임베딩 유사도가 이 판단 축에 구조적으로 부적합함을 확인했기 때문이다.
- 2026-08-08: tier1 사전을 승인된 질문은행 1,000문항 전수 분석으로 재구축하고, 위양성을 없애는 방향으로 타이트닝했다.
- 2026-08-08: `realtime_required`/`external_document_required` 차단 메시지에 tier2가 이미 생성한 `explanation`을 재사용해 노출하기로 했다 — 추가 LLM 호출 없이 안내 품질을 높인다.
- 2026-08-08: tier3(INTENT-SIM류)는 착수하지 않기로 확정했다. tier2 운영 데이터가 쌓인 뒤 재검토 대상으로 남긴다.
