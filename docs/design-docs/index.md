# 설계 문서 색인

설계 문서는 `왜 이 구조인가`를 설명한다. 현재 동작만 나열하는 문서는 코드나 생성 문서에 둔다.

## 문서

| 문서 | 상태 | 설명 |
|---|---|---|
| [핵심 신념](core-beliefs.md) | 승인 전 초안 | 모든 구현 판단에 적용할 원칙 |
| [RAG 파이프라인](rag-pipeline.md) | 승인 전 초안 | 수집, 색인, 검색, 답변 검증 |
| [평가 전략](evaluation-strategy.md) | 승인 전 초안 | 검색과 답변의 오프라인/온라인 평가 |
| [실험 C 키워드 결합 검색](experiment-c-keyword-retrieval-options.md) | 제안·보류 | dense 기준선 이후 lexical·RRF를 비교할 후속 설계 |
| [실험 D-10 수동 검색·문맥 진단](experiment-d-10-manual-review.md) | 완료 | 현재 DB corpus의 정답 없는 10문항 수동 진단과 사용자 확인 gate |
| [실험 D-10-R1 로컬 재정렬](experiment-d-10-local-rerank.md) | 완료 | 동일 top 10의 부모 표제·직접성 무호출 재정렬 진단 |
| [실험 D-10 M2 동결과 M3 calibration](experiment-d-10-m3-calibration.md) | M2 완료·M3 전 | 사용자 확정 10문항 계약, 무호출 preflight와 소표본 M3 방법 |
| [실험 D-10 전수 qrel과 사용자 adjudication](experiment-d-10-gold-adjudication.md) | draft 완료·사용자 검토 대기 | 10문항×3,066 전수 판정, qrel·reference 제안과 사용자 seal gate |
| [근거 우선 검색 품질](evidence-first-retrieval-quality.md) | 실험 C·D 적용 | corpus 검증, 법률 계층 복원, 근거 부족 게이트와 검색 알고리즘 채택 기준 |
| [검색 인덱스와 임베딩 계보](retrieval-index-storage.md) | 구현 기준 | 벡터 저장·계보, exhaustive exact dense 계약과 BM25 확장 경계 |
| [실험 D-full 1,000문항 평가](experiment-d-1000-evaluation.md) | 보류·필요 시 재검사 | D-10 밖 일반화가 필요할 때만 여는 qrels·reference·adjudication 계약 |
| [실험 D 일반 사용자 질문은행](experiment-d-layperson-question-bank.md) | 질문 승인·Gold 보류 | 보존된 자연어 질문 후보와 필요 시 독립 Gold 승격 경계 |
| [Open API 수집 계약](open-law-api-ingestion.md) | 승인 | JSON 우선·XML 폴백과 허용 목록 |
| [기술 스택 ADR](technology-stack.md) | 승인 | 런타임, 데이터, AI, 배포 결정 |
| [Vercel·Supabase 운영 전환](vercel-supabase-deployment.md) | 승인 | FastAPI 전환 조건, 외부 선행 입력, Preview 프록시와 운영 책임 |
| [Google OAuth·Supabase Auth 연결](google-oauth-supabase-flow.md) | 승인 전 초안 | Google·Supabase·Next.js·FastAPI의 표준 OAuth/OIDC 역할과 프로젝트별 URI |
| [시간 효력 모델](temporal-validity.md) | 승인 | 공포일·시행일·기준일 계약 |
| [분산 질문 취소](distributed-question-cancellation.md) | 제안 | sticky routing 없는 영속 취소 신호와 상태 계약 |
| [AI 차별화](ai-differentiation.md) | 승인 | 생성 활용과 인용 안전 게이트 |
| [답변 근거 검증](answer-grounding-validation.md) | 승인 | `DraftAnswer.action` 구조화 신호와 `validate_draft` 검증 강도 분기 |
| [질문 사전 라우팅](pre-retrieval-question-routing.md) | 승인 | embedding·검색 전 tier1(결정적 규칙)·tier2(LLM judgment) 2단계 라우터 |
| [위협 모델](threat-model.md) | 승인 | 신뢰 경계, 주요 위협과 출시 전 통제 |
| [의사결정 기록 템플릿](decision-record-template.md) | 사용 가능 | 중요한 기술 결정 기록 형식 |
| [일반인 답변 계약 v2](layperson-answer-contract-v2.md) | 승인 전 초안 | 초보자용 프롬프트 v2, 별도 generation profile, 가독성 rubric, 원문 링크 UI |

## 상태 정의

- `제안`: 비교와 피드백 단계
- `승인 전 초안`: 구현 전 사용자 확인이 필요한 설계
- `승인`: 구현의 기준
- `대체됨`: 새 문서 링크를 포함한 과거 기록

## 새 문서가 필요한 경우

- 외부 서비스나 핵심 프레임워크 도입
- 데이터 모델 또는 보존 정책 변경
- 신뢰 경계, 인증, 개인정보 흐름 변경
- 검색·청킹·임베딩·재순위·답변 정책 변경
- 되돌리기 어렵거나 운영비가 지속되는 결정
