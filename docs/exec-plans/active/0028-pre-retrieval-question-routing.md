# 0028: 검색 전 질문 라우팅과 조건부 query 보강

상태: `진행 중 · schema/tier 1/관측 tracking 완료 · tier 1 사전 v1 질문은행(1,000문항) 전수
분석으로 확장 완료 · tier 2 설계를 embedding 유사도 gate에서 LLM 판단으로 교체 확정,
adapter 골격 구현 · tier 3 사용 안 함으로 확정(2026-08-08) · 라우팅 파이프라인
app/main.py 배선 완료(tier 2는 NVIDIA API key 미배선으로 MockRouteClassifier 임시 사용) ·
평가 fixture(14 케이스) 구축·실행 완료 · tier1 위양성 2건(법령 currency 질문·일반 법적
의무 질문이 잘못 차단되던 것) 타이트닝으로 제거해 misclassification_rate 0.2857→0.1429,
unnecessary_block_rate 0.1429→0(2026-08-08) · 남은 misclassification 0.1429는 API key 배선
전 잠정치`

착수일: 2026-08-07

제안 출처: 2026-08-05 사용자 후속 작업 요청. 실험 D-10과 D-10-R1에서 법령 corpus로 직접 답할 질문,
추가 사실이 필요한 질문, 실시간 정보와 사용자 문서가 필요한 질문을 같은 검색 경로에 넣을 때 무관
법령이 상위 문맥에 포함되는 문제가 확인됐다.

관련 계획: [0025 승인 질문에서 근거 기반 AI 답변까지](0025-approved-questions-to-grounded-answer-roadmap.md)
M4.5

## 목적과 사용자 결과

질문 embedding과 법령 검색 전에 질문의 필요한 근거 유형을 판정한다. 법령 corpus가 답할 수 없는 질문을
억지로 검색하지 않고, 추가 정보·최신 정보·사용자 문서가 필요한 상태를 사용자에게 정확히 돌려준다.

## 범위

**입력은 질문 text와 법령 corpus뿐이다.** 실시간 정보 source나 사용자 문서 업로드를 받지 않는다
(2026-08-07 사용자 결정, 아래 "받지 않는 두 경로" 참고).

- `clarification_required`: 위치·설비용량·자가소비·판매 방식 등 빠진 사용자 사실을 **텍스트로** 먼저
  요청한다(추가 텍스트 입력이라 "text만 받는다" 원칙과 호환).
- `realtime_required`: 올해 예산·현재 가격·고장 상태처럼 시점에 따라 변하는 질문은 법령 검색을
  실행하지 않고 **결정적 차단 메시지로 끝난다** — 수집·연동하지 않는다.
- `external_document_required`: 계약서·정산서·공사비 산출서 등 문서가 필요한 질문도 법령 검색을
  실행하지 않고 **결정적 차단 메시지로 끝난다** — 업로드·수집하지 않는다.
- 그 밖의 법령 질문만 동결된 D1/D2 검색·문맥 경로로 보낸다.
- route, 이유 코드, 필요한 추가 사실과 embedding/search 실행 여부를 기록한다.
- 라우팅 뒤 법령 검색 결과가 여전히 부족할 때만 query 보강을 별도 단계로 평가한다.

### 받지 않는 두 경로 — realtime과 external document는 항상 차단 응답

`clarification_required`와 달리 `realtime_required`·`external_document_required`는 **후속 수집
흐름이 없다.** 시스템이 실시간 데이터 source에 연결하거나 사용자 문서를 받는 기능 자체를 만들지
않기 때문에, 이 두 route로 판정되면 다음 결정적 메시지만 반환하고 종료한다 — embedding·검색·LLM
호출 0회.

```text
[realtime_required]
이 질문은 시점에 따라 달라지는 정보(예: 올해 예산, 현재 가격, 고장 상태)가 필요합니다.
법령 corpus만으로는 답할 수 없으니 해당 연도·기관의 최신 공고나 담당 기관에 직접 확인해 주세요.

[external_document_required]
이 질문은 계약서·정산서·공사비 산출서 같은 문서 확인이 필요합니다.
법령 corpus만으로는 확정할 수 없으니 해당 문서를 직접 대조해 확인해 주세요.
```

## 비용 최소화 결정 — 완성 질문 재제출

`clarification_required`에서는 서버가 이전 turn과 새 turn을 자동 병합하거나 별도 query 보강 모델을
호출하지 않는다. 대신 현재 질문과 빠진 사실을 넣은 **복사용 완성 질문 템플릿**을 반환하고, 사용자가
다음 메시지에 원 질문과 추가 정보를 모두 포함해 한 번에 다시 보내도록 안내한다.

예를 들어 0251은 다음 형태로 안내한다.

```text
정확한 절차를 확인하려면 추가 정보가 필요합니다.
다음 메시지에는 아래 내용을 전체 복사한 뒤 [ ]를 채워 한 번에 보내주세요.
추가 정보만 따로 보내지 마세요.

질문: 소규모 설비는 용량이나 전기 사용 방식에 따라 허가와 신고가 어떻게 달라지나요?
추가 정보:
- 발전설비용량: [ ] kW
- 전압: [ ] V
- 사용 방식: [판매 / 자가소비 / 둘 다]
- 공사 종류: [신규 설치 / 변경공사]
```

이 경로의 계약은 다음과 같다.

1. 최초 질문의 route가 `clarification_required`이면 query embedding, 법령 검색과 법률 답변 생성을
   실행하지 않는다. clarification 응답은 route 결과의 원 질문과 누락 필드로 결정적으로 렌더링한다.
2. 응답에는 `다음 메시지에 현재 질문과 추가 정보를 모두 적어 달라`는 지시, 원 질문 원문, 누락 필드와
   빈칸을 포함한다. 원 질문의 법적 의미를 서버가 임의로 다시 쓰지 않는다.
3. 사용자가 보낸 완성 메시지는 대화 이력 병합에 의존하지 않는 새 독립 질문으로 취급한다. 이 한 메시지만
   다시 라우팅하고, 정보가 충분할 때만 query embedding과 검색을 각각 한 번 실행한다.
4. 사용자가 추가 사실만 보내거나 여전히 필드가 부족하면 검색하지 않고 남은 필드를 같은 형식으로 다시
   요청한다. 이전 turn을 추정해 조용히 결합하지 않는다.
5. clarification 응답을 만들기 위한 별도 answer model 호출, 서버 측 slot 상태, query rewrite, 추가
   passage embedding은 기본안에 포함하지 않는다. 라우터 자체 구현 방식과 비용은 active 승격 때 별도로
   고정한다.
6. 기존 `conversation_context`는 화면의 대화 연속성과 이후 답변 생성 보조에 쓸 수 있지만, 검색에 필요한
   사실을 복원하는 권위 입력으로 사용하지 않는다.

이 방식은 재제출 메시지의 입력 글자가 조금 늘지만, 서버 측 대화 상태·turn 병합·추가 모델 호출 없이
완성된 검색 질문 하나를 받으므로 현재 단계에서 가장 단순하고 비용이 낮다. 복사 버튼이나 자동 빈칸
채우기는 측정된 사용성 문제가 생긴 경우에만 후속 UI 개선으로 검토한다.

## 조건부 후속 단계

query 보강은 라우팅 구현과 평가를 통과한 뒤에도 직접 근거 순위가 부족한 법령 질문에만 적용한다.
원 질문과 보강 문구를 별도 version·SHA로 고정하고 D-10의 같은 10문항 query embedding을 한 batch로
최대 한 번 다시 만든다. 기존 3,066개 passage vector와 같은 corpus snapshot·embedding profile을
재사용하며 기존 D-10/D-10-R1 산출물을 덮어쓰지 않는다.

## 비범위

- 새 corpus 수집 또는 passage 재임베딩
- 실시간 정보원이나 사용자 문서 저장소 자체의 구현
- realtime·external-document 질문을 법령 검색으로 강제하는 동작
- AI 답변 생성과 실험 E
- 질문 ID나 D-10 수동 정답을 런타임 라우팅 규칙에 하드코딩
- 이전 turn과 새 메시지의 서버 측 자동 병합, slot 저장과 대화별 clarification 상태 머신
- clarification 문구를 만들기 위한 별도 생성 모델 호출이나 query rewrite
- 초기 구현의 전용 복사 버튼·자동완성 UI

## 의존성과 미결정

- D-10 M3/M4의 동결 검색·문맥 계약과 연결해야 한다. 10문항 밖 오분류율 일반화가 필요하면 예정 작업
  0029의 독립 Gold를 먼저 활성화한다.
- [해소, 2026-08-07] realtime 공식 source·external document 보안 계약은 더 이상 미결정이 아니다 —
  둘 다 수집하지 않고 결정적 차단 메시지로 끝내기로 확정했다(위 "받지 않는 두 경로" 참고).
- [2026-08-08 갱신] tier 2 유사도 컷오프는 더 이상 미결정 항목이 아니다 — 임베딩 유사도를 결정
  gate로 쓰는 설계 자체를 폐기했다(아래 "문제 탐색과 결론" 참고). 남은 threshold는 tier 2 LLM
  판단의 confidence 컷오프(있다면)와 tier 3 확신도 컷오프이며, 둘 다 동결 10문항의 partial·
  clarification·corpus 밖 사례를 보기 전에는 확정하지 않는다.

### 라우터 구현 방식 — tier 1/2 확정(2026-08-08), tier 3 미정

세 단계를 순서대로 시도하고, 앞 단계가 확신 있게 판정하면 뒷 단계를 호출하지 않는다는 원칙(LLM
호출은 corpus 크기가 아니라 **모호함의 크기**에 비례)은 그대로다. 다만 아래 "문제 탐색과 결론"의
calibration 결과로 tier 2의 방법 자체가 바뀌었다 — 자세한 내용은 해당 섹션을 참고.

1. **tier 1: 결정적 규칙(비용 0, 확정)** — 질문 텍스트에 대한 패턴 매칭만으로 확신 가능한 경우:
   - `realtime_required`: 시점·개인 계정 상태 의존 표현. v1 질문은행 1,000문항 전수 분석으로
     검증·확장된 사전(아래 "tier 1 사전 확장" 참고).
   - `external_document_required`: "계약서"·"정산서"·"보증서" 등 문서 대조를 요구하는 표현.
   - `clarification_required`의 일부: "~에 따라 달라지나요" 같은 조건부 비교 구문.
   여기서 잡히면 embedding·검색·LLM 호출 없이 바로 라우팅을 확정한다(0028 본문의 비용 계약과 동일).
2. **tier 2: LLM 판단(확정, 2026-08-08)** — 1단계가 확신하지 못하면 질문 원문 + route 정의
   10줄 미만을 소형 LLM 호출에 직접 판단시킨다. 기존에 별도 gate였던 "근접 예시 유사도"는
   폐기하지 않고 판단을 돕는 **참고용 힌트**로 프롬프트에 포함한다(자세한 이유와 구현은 아래
   "문제 탐색과 결론" 참고).
3. **tier 3(최후 수단, 미정)** — tier 2 LLM 판단도 못 잡는 잔여 사례를 어떻게 처리할지는 아직
   정하지 않았다. INTENT-SIM류(여러 가정으로 답을 시뮬레이션해 갈리는지 확인)가 후보지만, tier 2
   운영 데이터가 쌓이기 전에는 착수하지 않는다.

평가 fixture는 각 단계에서 잡히는 사례를 구분해 기록한다 — tier 1 커버리지가 높을수록 tier 2
호출률(=비용)이 낮아지므로, 이 비율 자체가 라우터 품질 지표다.

## 문제 탐색과 결론 (2026-08-08)

### 문제: 임베딩 유사도는 화용론적 충분성을 재지 못한다

2026-08-07 tier 2 calibration(위 "실제 calibration 실행 결과")에서 확인된 실패는 threshold
튜닝으로 고칠 수 있는 문제가 아니었다. `0201`("허가나 신고가 필요한지 어떻게 구분하나요")과
`0251`("...에 따라 어떻게 달라지나요")은 어휘가 거의 같아 임베딩이 가깝게 붙지만, 실제로 다른 건
주제가 아니라 "일반 설명으로 충분한가(legal_search) vs 답이 갈려서 먼저 물어야 하는가
(clarification_required)"라는 **화용론적(pragmatic) 판단**이다.

NVIDIA nemotron-3-embed 같은 검색용 임베딩 모델은 "이 두 텍스트가 같은 주제를 다루는가"를
학습하도록 만들어졌다. 라우팅이 실제로 필요로 하는 "이 질문에 이미 검색을 실행할 만큼 충분한
정보가 담겼는가"는 이 모델이 애초에 학습받은 목적이 아니다 — 그래서 유사도 크기와 route 정답
여부가 이번 calibration 표본에서 사실상 무관했던 것이다(오답 매칭 0.7185가 정답 매칭 전체
0.326~0.6947보다 순위가 높았다).

### 공인 문헌 조사

같은 문제를 다루는 두 연구 분야를 확인했다 — 둘 다 **임베딩 유사도를 판단 메커니즘으로 쓰지
않는다**는 점이 공통적이다.

- **"검색을 실행해도 되는가" = adaptive retrieval.** Self-RAG(Asai et al., 2023)는 모델이
  reflection token을 출력해 검색 필요 여부를 직접 판단하게 한다. Adaptive-RAG(Jeong et al.,
  2024)는 질문 복잡도를 예측하는 별도 학습 분류기로 검색 전략을 라우팅한다. FLARE는 생성 중
  토큰 신뢰도가 낮아지는 지점에서 능동적으로 검색을 트리거한다. 셋 다 "판단"을 모델 출력이나
  생성 확신도로 만들지, 최근접 이웃 거리로 만들지 않는다.
- **"지금 사용자에게 물어봐야 하는가" = clarification necessity detection.** ClariQ/Qulac
  (Aliannejadi et al., 2019), AmbigQA(Min et al., 2020) 등은 "clarification이 필요한가"를
  별도 판단 단계로 분리하는 공통 프레임워크를 쓴다. INTENT-SIM(Kuhn et al., 2023, "Clarify
  When Necessary")은 이 판단을 **의도(intent)에 대한 엔트로피**로 추정한다 — 같은 질문에 대해
  서로 다른 암묵적 가정 하에서 답을 시뮬레이션해보고, 답이 갈리면(엔트로피 높음) clarification이
  필요하다고 본다. 이 역시 임베딩 거리가 아니라 **모델이 직접 답을 시도해 갈리는지 확인하는
  방식**이다.

### 결론과 확정 사항

1. **tier 1 (결정적 규칙, 확정)** — 실시간/외부문서 키워드와 조건부 비교 구문처럼 순수
   어휘·문법 신호는 여전히 규칙으로 0원에 잡는다. 다만 손으로 나열한 표면형은 활용형과 corpus
   실제 표현을 놓친다는 게 확인되어(아래 "tier 1 사전 확장" 참고), 이제 corpus 전수 분석으로
   검증·확장한 사전을 쓴다.
2. **tier 2 (embedding 최근접 gate → LLM 판단, 확정)** — 기존 tier 2("근접 예시 분류 + threshold
   gate")는 폐기한다. 대신 Self-RAG 스타일로 **질문 원문 + route 정의 10줄 미만을 소형 LLM 호출에
   직접 판단시킨다.** 기존 tier 2가 계산하던 최근접 예시와 유사도는 버리지 않고 프롬프트 안에
   "참고용 힌트이며 최종 판단의 근거로 쓰지 말 것"이라는 명시적 경고와 함께 넣는다 — 이미 계산된
   결과라 추가 비용이 없고, anchoring bias만 프롬프트로 통제한다. 이렇게 하면 기존에 별도
   단계였던 "tier 2 근접 예시"와 "tier 3 소형 LLM"이 하나로 합쳐진다: LLM 판단이 최종 결정권을
   갖고, 임베딩 유사도는 그 판단의 입력 신호 중 하나로 격하된다.
3. **tier 3 (미정)** — INTENT-SIM처럼 "여러 가정 하에 답을 시뮬레이션해 갈리는지로 판단"하는
   방식은 tier 2 LLM 판단이 실제로 못 잡는 잔여 사례가 tracking으로 쌓인 뒤 재검토한다. 지금은
   비용 대비 효과를 판단할 데이터가 없어 착수하지 않는다.

### tier 1 사전 확장 — v1 질문은행(1,000문항) 전수 분석

한국어는 조사·어미 활용이 많아 표면형 나열은 금방 한계에 부딪힌다(다르다/다른가요/다릅니다/
달라요/달라지는지...). `kiwipiepy`(Kiwi, LGPL, 순수 pip 설치, JVM 불필요 — Vercel 서버리스
Python 함수에 적합)로 형태소를 분석해 어간만 매칭하면 활용형을 나열하지 않아도 된다. 학습된
분류 모델(BERT류)은 지금 채택하지 않는다 — fixture가 D-10 10개뿐이라 tier 2가 겪은 것과 같은
"라벨 부족" 문제가 재발하기 때문이다. 순수 규칙 기반 사전이 지금 단계의 데이터량에 맞는 방법이다.

`scripts/build_tier1_term_dictionary.py`가
[experiment-d-lay-energy-query-bank-v1-draft.json](../../../apps/api/evaluation/experiment-d-lay-energy-query-bank-v1-draft.json)의
1,000문항 전체를 Kiwi로 형태소 분석해
[tier1-term-dictionary-analysis-v1.json](../../../apps/api/evaluation/tier1-term-dictionary-analysis-v1.json)을
만든다. 결과:

- 기존 키워드 목록의 corpus 적중률이 낮았다(realtime 3.3%, document 2.8%) — 활용형 문제가
  아니라 목록 자체가 corpus의 실제 표현을 많이 놓치고 있었다는 뜻이다.
- "현재"·"지금"·"최근" 단독 어간이 등장한 문항 15개를 **전수 검토**(표본이 아니라 전부)한 결과
  전부 "현재 대기 순서"·"현재 계약 조건"·"현재 명의"처럼 개인 계정·시점 상태를 묻는 질문이라
  세 어간 모두 `_REALTIME_KEYWORDS`에 추가했다.
- `서`·`증`으로 끝나는 명사 후보(인증서·보증서·계산서·확인서 등)는 자동으로 채택하지 않고
  전부 읽어서 검토했다. "인증서"는 실제로는 REC(신재생에너지 공급인증서) 발급 절차를 묻는
  문항에 쏠려 있어 법령으로 설명 가능한 절차 질문이었고, "계산서"도 "달라지나요"·"무엇을 내야
  하나요"처럼 요건을 묻는 절차형 질문이라 **제외**했다. 명확히 "내가 가진 문서를 대조해야
  한다"는 의미로 쓰인 "보증서"만 채택했다. 빈도 1인 확인서·통지서·동의서는 근거 부족으로 보류.
- 조건부 비교 어간 후보(달라지·다르·따르·나뉘) 중 "따르"("~에 따라"의 활용형 자체)와 "나뉘"
  ("종류에 따라 어떻게 나뉘나요"처럼 일반적 분류를 묻는 질문에도 나타남, 즉 legal_search
  0201류와 구분이 안 됨)는 **채택하지 않았다** — 이 둘을 단독 신호로 추가하면 정확히 이 계획이
  경계하는 "주제 유사와 화용론적 판단을 혼동하는" 실수를 다시 반복하게 된다. 기존
  `match_conditional_variance_phrase`(에 따라...달라/다른가/다릅) 정규식만 유지한다.

빈도 기반 후보 추출은 자동화했지만 채택 여부는 전부 사람이 읽고 판단했다 — 사전 구축 자체도
"표면 어휘가 곧 화용론적 의미"라고 가정하지 않는다는 원칙을 지켰다.

### tier 2 구현 방식(확정, 2026-08-08)

`app/domain/routing.py`에 `RouteJudgment`, `RouteClassifier`(Protocol), `build_tier2_prompt`,
`route_tier2`(async, LLM 호출 기반)를 추가했다. `app/adapters/nvidia_nim_route_classifier.py`가
`NvidiaNimAnswerer`와 같은 guided_json 패턴으로 `NvidiaNimRouteClassifier`를 제공하되, 법률
답변 생성 모델과는 별도 client/model이라 라우팅 오판이 답변 생성에 번지지 않는다.
`cosine_similarity`/`nearest_example`은 그대로 남아 있고, tier 2 호출 전에 계산해 프롬프트에
힌트로 전달하는 용도로 재배치됐다. 실제 API key·모델 선정·설정 배선(`app/settings.py`)은 아직
하지 않았다 — active 승격 시 실행 순서에 포함한다.

## 세부 구현 계획 (active 승격 시 실행 순서)

1. **route schema 정의** — 완료(2026-08-07). `route: clarification_required | realtime_required |
   external_document_required | legal_search`, `reason_code`, `tier`(1/2/3 어디서 잡혔는지),
   `confidence`, `missing_fields`(clarification 한정)를 `app/domain/routing.py`의 `RouteDecision`
   dataclass로 고정했다.
2. **tier 1 결정적 규칙** — 완료(2026-08-07, `app/domain/routing.py`), 2026-08-08 v1
   질문은행(1,000문항) 전수 분석으로 사전 확장 완료(위 "tier 1 사전 확장" 참고). 시점 의존
   키워드 사전(realtime), 문서 키워드 사전(external document)을 구현하고 테스트를 통과시켰다.
   **clarification은 tier 1에 슬롯 사전을 손으로 만들지 않는다** — "어느 질문 유형에 어떤 슬롯이
   필요한가"는 이미 질문은행의 `scenario_family_id`·`missing_user_facts`에 있지만, 새 질문이 어느
   family에 속하는지는 tier 2(LLM 판단)가 있어야 알 수 있다. 그래서 clarification 판정은
   기본적으로 tier 2에서 하고, tier 1의 clarification 사전은 **아래 3단계 tracking으로 실제
   데이터를 모은 뒤** 자주 나오는 패턴만 추려서 추가한다(하드코딩 슬롯 나열이 아니라 관측 기반).
3. **관측 tracking 인프라** — tier 1 구현 직후, tier 2/3을 만들기 전에 먼저 넣는다. 이후 모든 실제
   질문이 처음부터 추적되게 하기 위해서다. `app/observability.py`의 기존
   `emit_question_outcome`(질문 원문·사용자·비밀 없이 결과만 기록하는 최소 관측 경계) 패턴을 그대로
   따라 `emit_route_outcome(route, tier, reason_code, confidence, missing_field_categories)`를
   추가한다. **질문 원문은 기록하지 않는다** — 개인정보 불변조건(`AGENTS.md`)과 이 계획의 완료 조건에
   이미 있는 제약이다. tier별 호출 비율, reason_code 빈도, clarification이 tier 2/3 중 어디서 얼마나
   잡히는지를 프로세스 로컬 counter로 누적한다. 이 신호가 "tier 1 clarification 사전에 뭘 추가해야
   하는지"를 알려주는 입력이 된다. 실제 문구(용어사전)까지 필요해지면, 새 raw-text 로그를 만들지 않고
   이미 동의를 받은 인증 사용자의 기존 질문 이력 저장소(1년 보존, 계정 삭제 시 삭제)를 사람이 검토하며
   샘플링한다 — D-10 검토와 같은 방식.
4. **tier 2 (superseded 설계) 근접 예시 gate — 2026-08-07 완료, 2026-08-08 폐기.** D-10 10문항 +
   v3 Gold의 answerability·insufficient_reason에서 도출한 route(clarification: `0251`·`0111`,
   realtime: `0605`·`0836`, 나머지 legal_search — 이 10문항엔 `external_document_required` 실례가
   없다)를 fixture로 저장하고 threshold gate를 구현했었다.

   **실제 calibration 실행 결과**(NIM 배치 호출 1회, 새 테스트 질문 10개, 기존 D-10 query vector
   cache 재사용): 유사도만으로는 신뢰 가능/불가능을 깨끗이 못 가른다 — clarification 테스트 질문
   (`0251`과 같은 "용량이나 사용 방식에 따라 허가와 신고가 어떻게 달라지나요" 계열)이
   **유사도 0.7185로 legal_search 예시(`0201`)에 잘못 매칭**됐는데, 이는 이 배치의 **정답 매칭
   6개 전부(0.326~0.6947)보다 높은 순위 1위** 유사도였다. 즉 유사도 크기와 정답 여부가 이 표본에서는
   사실상 무관했다 — 처음 `TIER2_CONFIDENCE_THRESHOLD = 0.70`으로 잡았던 값은 0.7185보다 낮아 이
   오류를 막지 못하는 버그였고, 이후 0.75로 정정했으나 그 값에서는 10문항 중 옳고 그름 상관없이
   아무 것도 threshold를 못 넘어 tier 2 커버리지가 사실상 0%였다. **원인 분석과 결론은 위 "문제
   탐색과 결론" 참고** — threshold 튜닝이 아니라 판단 메커니즘 자체(임베딩 유사도 → LLM 판단)를
   바꿔야 하는 문제였다. `TIER2_CONFIDENCE_THRESHOLD` 상수와 threshold gate형 `route_tier2`는
   코드에서 제거했고, `nearest_example`/`cosine_similarity`는 tier 2 LLM 판단의 힌트 계산용으로
   남겼다.

   **tier 1로 부분 해결**(그대로 유효): `0251`의 "~에 따라 달라지나요/다른가요/다릅니다" 조건부
   비교 구문은 순수 문법 패턴이라 임베딩과 무관하게 정규식으로 잡을 수 있어
   `match_conditional_variance_phrase`로 추가했다. 다만 `0111`처럼 이 구문을 안 쓰는 clarification
   질문은 여전히 못 잡는 부분 해결이다 — 이런 잔여 사례가 tier 2 LLM 판단이 필요한 이유다.
5. **tier 2 LLM 판단 (신규 설계, 확정 · 골격 구현 2026-08-08)** — `RouteJudgment`,
   `RouteClassifier`, `build_tier2_prompt`, async `route_tier2`를 `app/domain/routing.py`에,
   `NvidiaNimRouteClassifier` adapter를 `app/adapters/nvidia_nim_route_classifier.py`에 추가했다
   (설계는 위 "tier 2 구현 방식" 참고). **2026-08-08 사용자 결정**: 실제 NVIDIA API key는 아직
   배선하지 않고 `app/adapters/mock_route_classifier.py`의 `MockRouteClassifier`로 파이프라인을
   먼저 완성한다 — 힌트가 있으면 힌트를 그대로 따르고, 없으면 항상 `legal_search`로 기본
   처리한다(다른 세 route는 검색을 완전히 막으므로, 근거 없이 차단 쪽으로 기본값을 두면 답할 수
   있는 질문을 막는 피해가 검색 쪽 기본값보다 크다고 판단했다). **tier 3는 사용하지 않기로
   확정**했다 — INTENT-SIM류는 tier 2 운영 데이터가 쌓인 뒤 재검토 대상으로 미룬다.
6. **터미널 응답 구현 — 완료(2026-08-08)** — `app/application/answering.py`의
   `route_blocked_answer()`가 `realtime_required`·`external_document_required`는 결정적
   차단 메시지를(embedding·검색·LLM 호출 0회), `clarification_required`는 기존 "비용 최소화
   결정" 계약대로 원 질문+누락 필드 재제출 템플릿을 렌더링한다. `app/main.py`의
   `_answer_question()`에서 `route_tier1`→`route_tier2`를 embedding보다 먼저 호출하도록
   배선했다. **범위 축소 결정**: 지금은 `answer_mode="terra"`(AI 경로)에만 적용한다 —
   `search_only` 모드는 원문을 사용자가 직접 대조하는 모드라 D-10에서 발견된 "무관 법령이 AI
   문맥에 섞이는" 문제 자체가 없고, 기존 `search_only` 테스트 범위를 이번 변경에서 건드리지
   않기 위해서다. `search_only`까지 넓히는 건 별도 결정 필요.
7. **평가 fixture와 비용 gate — 완료(2026-08-08, 잠정치)**
   [route-fixture-v1.json](../../../apps/api/evaluation/route-fixture-v1.json)에 D-10 10문항
   전체와 경계 사례 4개(총 14 케이스)를 만들고
   [evaluate_routing_fixture.py](../../../apps/api/scripts/evaluate_routing_fixture.py)로
   실행했다. 1차 결과(`route-fixture-v1-results.json`): misclassification_rate 0.2857(4/14),
   unnecessary_search_rate 0.1429, **unnecessary_block_rate 0.1429**, tier1_resolution_rate
   0.4286, tier2_resolution_rate 0.5714.

   **2026-08-08 사용자 지적 — tier1 타이트닝**: `unnecessary_block_rate`(법령으로 답할 수
   있는 질문을 잘못 차단하는 비율)가 0이 아니었다. `boundary-document-keyword-false-positive`
   ("계약서를 꼭 써야 하는 법적 의무가 있나요")와 `boundary-realtime-keyword-false-positive`
   ("현재 시행 중인 신재생에너지법의 허가 절차")가 각각 "계약서"·"현재" 단어 존재만으로
   tier1에 잘못 차단됐다. "정말 답할 수 없는 것만 타이트하게 거른다"는 방향에 따라 두 가지를
   고쳤다: ① `match_realtime_personal_state_phrase`로 시점어(현재/지금/최근/요즘) 단독
   매칭을 버리고 개인·계정 상태 명사(순서·계약·명의·소유자 등, corpus 표본 15문항에서
   확인된 공기어)와의 12자 이내 근접 매칭으로 좁히면서, "시행/유효한/법령/법률/규정/기준일"이
   바로 뒤에 오면 애초에 제외(법령 currency 질문 구분). ② 문서 키워드에
   `_GENERAL_LEGAL_REQUIREMENT_INQUIRY_PATTERN`("법적 의무가 있나요" 류) 제외 규칙을
   추가해 "법이 요구하는가"를 묻는 일반 질문과 "내 문서를 대조해달라"를 구분. 재실행 결과:
   misclassification_rate 0.2857→**0.1429**(2/14), **unnecessary_block_rate 0.1429→0**.
   남은 오분류 2건(`0111`, `boundary-clarification-without-conditional-phrase`)은 둘 다
   `unnecessary_search`(검색 쪽으로 실패) 방향이지 `unnecessary_block`이 아니다 — tier1
   정규식이 못 잡는 조건부 질문을 tier2(mock)가 힌트 없이 `legal_search`로 기본 처리해서
   생기며, 실제 LLM 판단이 붙으면 해소될 것으로 예상한다. **이 수치는 여전히 잠정치다** —
   tier2가 `MockRouteClassifier`라 실제 LLM 판단이 아니다. NVIDIA API key를 배선한 뒤
   `evaluate_routing_fixture.py`를 다시 실행해서 갱신해야 한다(`app/main.py`의
   `_route_classifier()` TODO 참고).
8. **관측 로그 최종 검증 — 완료(2026-08-08)** — `emit_route_outcome()`을 `app/main.py`의 라우팅
   결정 직후에 연결했다. `RouteOutcomeEvent`는 `request_id`·`route`·`tier`·`reason_code`·
   `confidence`·`missing_field_categories`만 담고 질문 원문·자유 텍스트는 받지 않는다(개인정보
   불변조건 유지). 별도 후속 항목: 익명 사용자의 fallback/생성 실패 사유는 아직 분석 가능한
   형태로 안 남는다 — `app/observability.py`의 TODO(2026-08-08) 참고.
9. **통합 테스트 — 완료(2026-08-08)** —
   [test_routing_pipeline.py](../../../apps/api/tests/test_routing_pipeline.py)에 realtime·
   external-document 차단, clarification 재제출, 일반 legal_search 통과, `search_only` 모드가
   라우팅에 안 걸리는 경계 케이스를 end-to-end로 검증했다(전부 embedding/search 호출 수까지
   확인).

## active 승격 조건

- 사용자가 이 항목의 착수를 명시한다.
- route schema에 원 질문, 누락 필드, 복사용 완성 질문과 재제출 지시를 표현하고 실패·보류 동작,
  평가 fixture와 불필요 검색률 지표를 실행 계획에 고정한다.
- 현재 Git 변경과 파일 범위 충돌이 없음을 확인한다.

## 완료 조건

- 라우팅이 query embedding보다 먼저 실행되고 네 경로의 정상·실패·경계 테스트가 통과한다.
- clarification·realtime·external-document 경로에서 허용 조건 전 embedding/search가 실행되지 않는다.
- clarification 응답이 별도 answer model 없이 원 질문과 누락 필드를 포함한 완성 질문 템플릿을 반환한다.
- 추가 사실만 보낸 메시지는 이전 turn과 자동 병합되지 않으며, 원 질문까지 포함한 독립 재제출이 충분할
  때만 embedding/search를 각각 최대 한 번 실행한다.
- route와 검색 생략 사유가 개인정보·질문 전문 없이 관측 가능하다.
- 고정 평가 fixture에서 오분류와 불필요 검색률을 기록하고 사전 확정 gate를 통과한다.
- 조건부 query 보강을 실행한다면 별도 비교 run에서 직접 근거 순위와 무관 top 5 변화를 기록한다.

## 계획 검증 사례

- 0251 입력은 `clarification_required`와 발전용량·전압·사용 방식·공사 종류 네 필드를 반환한다.
- clarification 응답에는 0251 원 질문과 네 빈칸이 모두 있고 `추가 정보만 따로 보내지 말라`는 안내가
  있다.
- 이 응답까지 query embedding·검색·answer model 호출 수는 모두 0이다.
- 원 질문과 네 정보를 합친 재제출은 새 독립 질문으로 라우팅되어 통과한 경우에만 embedding·검색을
  각각 1회 실행한다.
- `100kW, 자가소비입니다`처럼 추가 사실만 보낸 입력은 과거 turn을 자동 추정하지 않고 남은 정보와
  원 질문을 함께 보내도록 다시 안내한다.
- route와 호출 여부는 기록하지만 원 질문 원문과 사용자가 채운 설비 정보는 관측 로그에 남기지 않는다.

## 결정 기록

- 2026-08-07: 비용 최소화를 위해 clarification 후속 입력은 서버가 대화 turn을 자동 병합하지 않고,
  사용자가 원 질문과 추가 정보를 한 메시지로 복사·보완해 재제출하는 방식을 기본안으로 정했다.
  clarification 응답은 결정적 템플릿으로 만들며 embedding·검색·별도 answer model을 호출하지 않는다.
- 2026-08-07: 사용자가 입력 범위를 "질문 text + 법령 corpus"로만 확정했다. 실시간 정보 source
  연동과 사용자 문서 업로드를 만들지 않기로 하면서, `realtime_required`·`external_document_required`
  는 후속 수집 흐름 없이 결정적 차단 메시지로 끝나는 것으로 범위를 좁혔다. 이전에 미결정이었던
  "승인된 공식 source"·"문서 보안·보존 계약" 항목은 이제 필요 자체가 없어져 해소됐다.
- 2026-08-07: clarification용 tier 1 슬롯 사전을 지금 손으로 만들지 않기로 했다. scenario family별
  필요 슬롯은 이미 질문은행에 있지만 family 매칭 자체가 tier 2(embedding) 기능이라, tier 1에서
  미리 정의하면 실제 사용 패턴과 안 맞을 위험이 크다. 대신 route/tier/reason_code/confidence만
  기록하는 개인정보 안전한 tracking을 tier 2/3보다 먼저 넣어서, 실제 데이터가 쌓이면 그걸 근거로
  tier 1 사전을 나중에 추가하기로 했다. 문구(용어사전) 수준까지 필요해지면 새 raw-text 로그를 만들지
  않고 기존 동의된 질문 이력 저장소를 사람이 검토하며 샘플링한다(D-10과 같은 방식).
- 2026-08-07: 사용자 승인 하에 tier 2 calibration용 NIM 배치 호출 1회(신규 테스트 질문 10개, D-10
  10문항은 기존 query vector cache 재사용해 새 호출 0회)를 실행했다. 틀린 매칭(0.7185)이 이 배치의
  정답 매칭 6개 전부(0.326~0.6947)보다 유사도 순위가 높아, 단순 유사도 크기만으로는 신뢰도를 못
  가른다는 게 확인됐다. 처음 `TIER2_CONFIDENCE_THRESHOLD = 0.70`으로 잡았던 값이 이 틀린 매칭보다
  낮아 오류를 못 막는 버그였음을 재검토 중 발견해 0.75로 정정했다 — 이 값에서는 10문항 전부가
  threshold를 못 넘어 tier 2 커버리지가 사실상 0%다. 원인은 임베딩이 "주제 유사도"를 재는 도구라서
  "검색이 지금 유용한가"라는 라우팅의 실제 판단 축과 다르기 때문이며, `0251`의 "~에 따라
  달라지나요/다른가요" 조건부 비교 구문처럼 순수 문법 신호는 tier 1 정규식으로 옮겨 부분적으로
  보완했다(`match_conditional_variance_phrase`). fixture가 D-10보다 커지기 전까지 threshold를 최종
  확정하지 않는다.
- 2026-08-08: 사용자 요청으로 2026-08-07 calibration 실패 원인을 공인 문헌과 대조해 "문제 탐색과
  결론" 섹션으로 정리했다. 결론: 임베딩 유사도는 "주제가 같은가"를 재는 도구고, 라우팅이 필요한
  건 "이 질문에 이미 충분한 정보가 있는가"라는 화용론적 판단이라 구조적으로 안 맞는다(Self-RAG,
  Adaptive-RAG, ClariQ/Qulac, INTENT-SIM 등 문헌 모두 이 판단을 임베딩 거리가 아니라 모델 판단이나
  답변 시뮬레이션의 엔트로피로 만든다). 이에 따라 tier 2를 "embedding 최근접 + threshold gate"에서
  "질문 원문 + route 정의를 소형 LLM에 직접 판단시키고, 기존 최근접 예시 유사도는 참고용 힌트로만
  넣는" 방식으로 교체하기로 확정했다(tier 3는 미정으로 남긴다). `TIER2_CONFIDENCE_THRESHOLD`와
  threshold gate형 `route_tier2`를 제거하고 `RouteJudgment`/`RouteClassifier`/`build_tier2_prompt`/
  async `route_tier2`와 `NvidiaNimRouteClassifier` adapter 골격을 추가했다(API key·설정 배선은
  아직 안 함).
- 2026-08-08: tier 1 사전을 "2천 개 질문"이 아니라 실제로 저장소에 있는 v1 질문은행
  1,000문항(experiment-d-lay-energy-query-bank-v1-draft.json) 전수를 Kiwi(kiwipiepy)로 형태소
  분석해 검증·확장했다 — 사용자가 처음 말한 "2천 개"는 저장소에 존재하지 않아 확인 후 1,000개로
  진행하기로 정정했다. `scripts/build_tier1_term_dictionary.py`로 빈도 기반 후보를 자동 추출했지만
  채택은 전부 사람이 직접 읽고 판단했다(예: "인증서"는 REC 발급 절차 질문에 쏠려 있어 실제로는
  법령으로 설명 가능한 절차 질문이라 제외, "나뉘"는 legal_search 0201류의 일반 분류 질문에도
  나타나 조건부 비교 신호로 채택하지 않음) — 자동 빈도 추출을 최종 판단으로 쓰면 이 계획이 경계하는
  "주제 유사와 화용론적 판단의 혼동"을 사전 구축 단계에서 반복하게 되기 때문이다.
- 2026-08-08: 사용자가 M4.5 게이트 작업을 계획대로 진행하기로 결정하면서 세 가지를 확정했다.
  ① tier 3는 사용하지 않는다 — INTENT-SIM류는 tier 2 운영 데이터가 쌓인 뒤 재검토. ② NVIDIA
  API key는 지금 배선하지 않고 `MockRouteClassifier`(힌트 있으면 힌트 따름, 없으면 항상
  `legal_search`)로 파이프라인을 먼저 완성한다. ③ 평가 fixture는 제안해서 만들고, 비용 게이트는
  잠정치로 진행하되 API key 배선 뒤 다시 계산해야 함을 명시한다. 이 결정에 따라
  `app/main.py`의 `_answer_question()`에 `route_tier1`→`route_tier2`를 embedding 앞에
  배선하고(단 `answer_mode="terra"`에만 적용, `search_only`는 범위 밖으로 남김),
  `route_blocked_answer()`로 세 차단 route의 결정적 응답을 구현했다. `route-fixture-v1.json`
  (D-10 10개 + 경계 사례 4개)을 만들어 `evaluate_routing_fixture.py`로 실행한 결과
  misclassification_rate 0.2857 — 오분류 4건 전부 의도적으로 넣은 경계 사례(tier1 키워드
  오탐 2건, tier2 mock의 힌트 없는 기본값이 놓친 조건부 질문 2건)라 예상과 일치했다. 이
  수치는 tier2가 mock이라 API key 배선 뒤 다시 재야 하는 잠정치임을 스크립트·fixture·이
  문서 세 곳에 모두 명시했다. `emit_route_outcome()`도 이번에 `app/main.py`에 연결해 라우팅
  결정이 관측 가능해졌다.
