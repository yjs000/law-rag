# 실험 D 후보 — 일반 사용자형 에너지 질문 1,000개

> 생성 명령: `uv run --directory apps/api python -m scripts.generate_layperson_energy_questions`
> bank version: `experiment-d-lay-energy-query-bank-v1-draft`
> question set SHA-256: `58be922c4bd9db7bce1360565da9b97de703e3b32c956c11e6a79285ee0b6b32`
> 상태: 질문 검토 초안 — 정답·qrels 없음, 검색 실험 실행 안 함

## 읽기 전에

공공기관 FAQ와 절차 안내에서 질문 주제를 조사한 뒤 일반 사용자가 말할 법한 표현으로 새로 쓴 합성 질문이다. 문장을 그대로 복사하지 않았으며 실제 사용자 로그나 질문 빈도 통계라고 주장하지 않는다.

현재 단계에서는 사용자 유형·사업 단계·현재 문서 모음의 답변 가능 여부를 질문별 정답처럼 붙이지 않았다. `not_annotated`는 평가용 정답 라벨이 없다는 뜻이며, 질문을 만든 주제·표현 방식 메타데이터는 존재한다. 실제 평가셋으로 쓰려면 필요한 답변 요소, 근거 범위, 기준일을 사람이 별도로 확정해야 한다.

이 파일만으로는 Recall·MRR 같은 검색 정확도를 계산할 수 없다. 질문을 승인한 뒤 검색 결과와 독립적으로 답변 가능 여부·필수 답변 요소·직접 근거 조문 목록(qrels)·기준 답변을 주석한 별도 gold 파일이 필요하다.

설계: [일반 사용자 질문은행과 gold 주석 경계](../design-docs/experiment-d-layperson-question-bank.md) · [질문 주제 참고 자료](../references/energy-layperson-question-sources-2026-08-03.md)

## 구성

상황 200개를 만들고 각 상황에 의미가 맞는 질문 관점 5개를 직접 짝지어 총 1,000개로 구성했다.

| 질문 의도 | 개수 |
|---|---:|
| 사업 시작·전체 절차 | 110 |
| 부지·건물·토지 이용 | 90 |
| 허가·신고·서류 | 90 |
| 계통연계·한전 계약 | 90 |
| 시공·설비·인증 | 60 |
| 검사·안전·고장·재난 | 70 |
| 수익·SMP·REC·정산 | 90 |
| 보조금·융자·지원 | 70 |
| 전기요금·계약전력·생활민원 | 70 |
| 주택 태양광·소비자보호 | 55 |
| 전기차 충전 | 50 |
| ESS | 35 |
| 분산에너지·직접거래·VPP·RE100 | 40 |
| 주민·환경·철거·폐기 | 40 |
| 기타 재생에너지 | 40 |

## 정적 검사

| 항목 | 결과 |
|---|---:|
| 전체 질문 | 1000 |
| 정규화 중복 | 0 |
| 전체 질문 간 근접 중복 쌍 | 0 |
| 법조문 번호·법률식 문구 | 0 |
| 길이 오류 | 0 |
| 형식 오류 | 0 |
| 전수 읽기 후 수동 교정 문항 | 162 |

## 전체 질문

<details>
<summary>사업 시작·전체 절차 — 110개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0001 | 태양광 발전사업을 처음 해보려고 하는데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0002 | 태양광 발전사업을 처음 해보려고 하는데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0003 | 태양광 발전사업을 처음 해보려고 하는데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0004 | 태양광 발전사업을 처음 해보려고 하는데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0005 | 태양광 발전사업을 처음 해보려고 하는데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0006 | 퇴직 후 작은 발전소를 운영해 보고 싶은데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0007 | 퇴직 후 작은 발전소를 운영해 보고 싶은데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0008 | 퇴직 후 작은 발전소를 운영해 보고 싶은데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0009 | 퇴직 후 작은 발전소를 운영해 보고 싶은데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0010 | 퇴직 후 작은 발전소를 운영해 보고 싶은데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0011 | 개인이 전기를 만들어 판매하는 사업을 알아보는 중인데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0012 | 개인이 전기를 만들어 판매하는 사업을 알아보는 중인데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0013 | 개인이 전기를 만들어 판매하는 사업을 알아보는 중인데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0014 | 개인이 전기를 만들어 판매하는 사업을 알아보는 중인데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0015 | 개인이 전기를 만들어 판매하는 사업을 알아보는 중인데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0016 | 가족과 함께 소규모 재생에너지 사업을 시작하려는데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0017 | 가족과 함께 소규모 재생에너지 사업을 시작하려는데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0018 | 가족과 함께 소규모 재생에너지 사업을 시작하려는데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0019 | 가족과 함께 소규모 재생에너지 사업을 시작하려는데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0020 | 가족과 함께 소규모 재생에너지 사업을 시작하려는데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0021 | 여러 사람이 돈을 모아 발전소를 운영하려는데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0022 | 여러 사람이 돈을 모아 발전소를 운영하려는데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0023 | 여러 사람이 돈을 모아 발전소를 운영하려는데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0024 | 여러 사람이 돈을 모아 발전소를 운영하려는데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0025 | 여러 사람이 돈을 모아 발전소를 운영하려는데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0026 | 농촌에서 태양광 사업을 부업으로 해보고 싶은데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0027 | 농촌에서 태양광 사업을 부업으로 해보고 싶은데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0028 | 농촌에서 태양광 사업을 부업으로 해보고 싶은데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0029 | 농촌에서 태양광 사업을 부업으로 해보고 싶은데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0030 | 농촌에서 태양광 사업을 부업으로 해보고 싶은데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0031 | 공장 전기요금을 줄이면서 남는 전기도 팔고 싶은데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0032 | 공장 전기요금을 줄이면서 남는 전기도 팔고 싶은데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0033 | 공장 전기요금을 줄이면서 남는 전기도 팔고 싶은데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0034 | 공장 전기요금을 줄이면서 남는 전기도 팔고 싶은데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0035 | 공장 전기요금을 줄이면서 남는 전기도 팔고 싶은데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0036 | 건물 옥상에 태양광 설비를 설치해 발전사업을 하면 수익이 날지 궁금한데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0037 | 건물 옥상에 태양광 설비를 설치해 발전사업을 하면 수익이 날지 궁금한데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0038 | 건물 옥상에 태양광 설비를 설치해 발전사업을 하면 수익이 날지 궁금한데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0039 | 건물 옥상에 태양광 설비를 설치해 발전사업을 하면 수익이 날지 궁금한데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0040 | 건물 옥상에 태양광 설비를 설치해 발전사업을 하면 수익이 날지 궁금한데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0041 | 빈 땅을 활용해 태양광 발전사업을 시작하고 싶은데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0042 | 빈 땅을 활용해 태양광 발전사업을 시작하고 싶은데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0043 | 빈 땅을 활용해 태양광 발전사업을 시작하고 싶은데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0044 | 빈 땅을 활용해 태양광 발전사업을 시작하고 싶은데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0045 | 빈 땅을 활용해 태양광 발전사업을 시작하고 싶은데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0046 | 재생에너지 발전소에 투자하기 전에 직접 운영도 검토 중인데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0047 | 재생에너지 발전소에 투자하기 전에 직접 운영도 검토 중인데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0048 | 재생에너지 발전소에 투자하기 전에 직접 운영도 검토 중인데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0049 | 재생에너지 발전소에 투자하기 전에 직접 운영도 검토 중인데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0050 | 재생에너지 발전소에 투자하기 전에 직접 운영도 검토 중인데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0051 | 법인을 만들어 태양광 발전소 여러 곳을 운영하려는데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0052 | 법인을 만들어 태양광 발전소 여러 곳을 운영하려는데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0053 | 법인을 만들어 태양광 발전소 여러 곳을 운영하려는데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0054 | 법인을 만들어 태양광 발전소 여러 곳을 운영하려는데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0055 | 법인을 만들어 태양광 발전소 여러 곳을 운영하려는데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0056 | 기존 사업과 별도로 전기 생산 사업을 추가하려는데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0057 | 기존 사업과 별도로 전기 생산 사업을 추가하려는데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0058 | 기존 사업과 별도로 전기 생산 사업을 추가하려는데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0059 | 기존 사업과 별도로 전기 생산 사업을 추가하려는데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0060 | 기존 사업과 별도로 전기 생산 사업을 추가하려는데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0061 | 지역 주민들과 협동조합 방식으로 발전사업을 시작하려는데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0062 | 지역 주민들과 협동조합 방식으로 발전사업을 시작하려는데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0063 | 지역 주민들과 협동조합 방식으로 발전사업을 시작하려는데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0064 | 지역 주민들과 협동조합 방식으로 발전사업을 시작하려는데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0065 | 지역 주민들과 협동조합 방식으로 발전사업을 시작하려는데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0066 | 작은 발전설비부터 시작해 나중에 규모를 키우고 싶은데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0067 | 작은 발전설비부터 시작해 나중에 규모를 키우고 싶은데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0068 | 작은 발전설비부터 시작해 나중에 규모를 키우고 싶은데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0069 | 작은 발전설비부터 시작해 나중에 규모를 키우고 싶은데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0070 | 작은 발전설비부터 시작해 나중에 규모를 키우고 싶은데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0071 | 토지 계약 전에 발전사업 전체 과정을 먼저 알고 싶은데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0072 | 토지 계약 전에 발전사업 전체 과정을 먼저 알고 싶은데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0073 | 토지 계약 전에 발전사업 전체 과정을 먼저 알고 싶은데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0074 | 토지 계약 전에 발전사업 전체 과정을 먼저 알고 싶은데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0075 | 토지 계약 전에 발전사업 전체 과정을 먼저 알고 싶은데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0076 | 허가부터 공사와 검사까지 한 번에 준비하고 싶은데, 무엇부터 준비해야 하나요? | `business_start_general` |
| lay-energy-0077 | 허가부터 공사와 검사까지 한 번에 준비하고 싶은데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | `business_start_general` |
| lay-energy-0078 | 허가부터 공사와 검사까지 한 번에 준비하고 싶은데, 처음 상담받을 때 어떤 자료와 서류를 챙겨야 하나요? | `business_start_general` |
| lay-energy-0079 | 허가부터 공사와 검사까지 한 번에 준비하고 싶은데, 돈을 쓰기 전에 가장 먼저 확인할 사업 위험은 무엇인가요? | `business_start_general` |
| lay-energy-0080 | 허가부터 공사와 검사까지 한 번에 준비하고 싶은데, 단계마다 어디에 문의하고 누구의 확인을 받아야 하나요? | `business_start_general` |
| lay-energy-0081 | 제가 쓸 전기만 만들지 남는 전기를 판매할지 고민인데, 두 방식 중 무엇이 맞는지 판단하려면 무엇을 먼저 비교해야 하나요? | `business_use_or_sale_choice` |
| lay-energy-0082 | 제가 쓸 전기만 만들지 남는 전기를 판매할지 고민인데, 두 방식은 준비 절차와 전력회사 계약이 어떻게 다른가요? | `business_use_or_sale_choice` |
| lay-energy-0083 | 제가 쓸 전기만 만들지 남는 전기를 판매할지 고민인데, 비교 상담을 받으려면 전기 사용량과 설치 장소 등 어떤 자료가 필요한가요? | `business_use_or_sale_choice` |
| lay-energy-0084 | 제가 쓸 전기만 만들지 남는 전기를 판매할지 고민인데, 비용·절감액·판매수익은 어떤 기준으로 비교해야 하나요? | `business_use_or_sale_choice` |
| lay-energy-0085 | 제가 쓸 전기만 만들지 남는 전기를 판매할지 고민인데, 각 방식의 조건은 어느 기관에 문의해야 하나요? | `business_use_or_sale_choice` |
| lay-energy-0086 | 시공업체가 제안한 태양광 사업을 진행해도 될지 고민인데, 업체와 제안을 무엇부터 검증해야 하나요? | `business_vendor_proposal` |
| lay-energy-0087 | 시공업체가 제안한 태양광 사업을 진행해도 될지 고민인데, 계약 전에 업체·수익·허가 가능성을 어떤 순서로 확인해야 하나요? | `business_vendor_proposal` |
| lay-energy-0088 | 시공업체가 제안한 태양광 사업을 진행해도 될지 고민인데, 사업성 계산서와 계약서 등 어떤 자료를 받아 확인해야 하나요? | `business_vendor_proposal` |
| lay-energy-0089 | 시공업체가 제안한 태양광 사업을 진행해도 될지 고민인데, 과장된 수익이나 숨은 비용을 어떻게 찾아낼 수 있나요? | `business_vendor_proposal` |
| lay-energy-0090 | 시공업체가 제안한 태양광 사업을 진행해도 될지 고민인데, 업체와 제안 내용은 어디에서 확인받거나 상담할 수 있나요? | `business_vendor_proposal` |
| lay-energy-0091 | 발전사업 경험이 전혀 없어 대행업체를 써야 할지 궁금한데, 직접 할 수 있는 일과 전문가에게 맡겨야 할 일은 어떻게 구분하나요? | `business_agency_choice` |
| lay-energy-0092 | 발전사업 경험이 전혀 없어 대행업체를 써야 할지 궁금한데, 직접 진행할 때와 대행업체에 맡길 때 절차와 책임은 어떻게 다른가요? | `business_agency_choice` |
| lay-energy-0093 | 발전사업 경험이 전혀 없어 대행업체를 써야 할지 궁금한데, 상담 전에 무엇을 준비하고 업체에서 어떤 자료를 받아야 하나요? | `business_agency_choice` |
| lay-energy-0094 | 발전사업 경험이 전혀 없어 대행업체를 써야 할지 궁금한데, 수수료·업무 범위·환불 조건을 계약서에서 어떻게 확인하나요? | `business_agency_choice` |
| lay-energy-0095 | 발전사업 경험이 전혀 없어 대행업체를 써야 할지 궁금한데, 믿을 만한 업체인지 어디서 확인하고 문제가 생기면 어디에 문의하나요? | `business_agency_choice` |
| lay-energy-0096 | 재생에너지 사업을 준비하면서 필요한 자격이 있는지 궁금한데, 직접 운영하려면 제가 갖춰야 하는 자격이나 경력이 있나요? | `business_qualification` |
| lay-energy-0097 | 재생에너지 사업을 준비하면서 필요한 자격이 있는지 궁금한데, 직접 할 일과 자격 있는 업체에 맡겨야 하는 일은 어떻게 나뉘나요? | `business_qualification` |
| lay-energy-0098 | 재생에너지 사업을 준비하면서 필요한 자격이 있는지 궁금한데, 필요한 자격을 확인받으려면 어떤 사업 정보를 준비해야 하나요? | `business_qualification` |
| lay-energy-0099 | 재생에너지 사업을 준비하면서 필요한 자격이 있는지 궁금한데, 자격이 없는 사람이나 업체에 맡기면 어떤 문제가 생길 수 있나요? | `business_qualification` |
| lay-energy-0100 | 재생에너지 사업을 준비하면서 필요한 자격이 있는지 궁금한데, 필요한 자격과 업체 등록 여부는 어느 기관에서 확인할 수 있나요? | `business_qualification` |
| lay-energy-0101 | 사업계획은 있지만 어느 기관부터 찾아가야 할지 모르겠는데, 첫 상담은 어디에 요청하는 것이 좋나요? | `business_first_agency` |
| lay-energy-0102 | 사업계획은 있지만 어느 기관부터 찾아가야 할지 모르겠는데, 지방자치단체·전력회사·안전검사 기관은 각각 무엇을 담당하나요? | `business_first_agency` |
| lay-energy-0103 | 사업계획은 있지만 어느 기관부터 찾아가야 할지 모르겠는데, 처음 문의할 때 위치·용량·사용 목적 중 무엇을 알려줘야 하나요? | `business_first_agency` |
| lay-energy-0104 | 사업계획은 있지만 어느 기관부터 찾아가야 할지 모르겠는데, 담당 기관을 확인한 뒤 어떤 순서로 상담과 신청을 이어가나요? | `business_first_agency` |
| lay-energy-0105 | 사업계획은 있지만 어느 기관부터 찾아가야 할지 모르겠는데, 사업 규모와 지역에 따라 담당 기관이 달라지는지 어디서 확인하나요? | `business_first_agency` |
| lay-energy-0106 | 발전소를 완공한 뒤 실제 전기 판매까지 어떻게 이어지는지 궁금한데, 전기를 팔기 전에 남은 검사와 계약은 무엇인가요? | `business_post_completion_sale` |
| lay-energy-0107 | 발전소를 완공한 뒤 실제 전기 판매까지 어떻게 이어지는지 궁금한데, 검사·계량기 설치·판매 계약은 어떤 순서로 진행하나요? | `business_post_completion_sale` |
| lay-energy-0108 | 발전소를 완공한 뒤 실제 전기 판매까지 어떻게 이어지는지 궁금한데, 전기 판매를 시작하려면 완공·검사 관련 어떤 서류가 필요한가요? | `business_post_completion_sale` |
| lay-energy-0109 | 발전소를 완공한 뒤 실제 전기 판매까지 어떻게 이어지는지 궁금한데, 완공 후에도 판매가 늦어질 수 있는 원인은 무엇인가요? | `business_post_completion_sale` |
| lay-energy-0110 | 발전소를 완공한 뒤 실제 전기 판매까지 어떻게 이어지는지 궁금한데, 각 절차의 진행 상태는 어느 기관에 확인해야 하나요? | `business_post_completion_sale` |

</details>

<details>
<summary>부지·건물·토지 이용 — 90개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0111 | 시골에 가진 땅에 태양광을 설치해도 되는지 알아보는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0112 | 제가 가진 땅이 공동 명의이거나 다른 사람이 사용 중이라면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0113 | 시골에 가진 땅에 태양광을 설치해도 되는지 알아보는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0114 | 시골 땅에 공사하기 전에 지반·경사·배수·진입로·주변 환경에서 어떤 위험을 살펴야 하나요? | `site_land_building` |
| lay-energy-0115 | 운영 중 토지 소유권이나 용도가 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0116 | 농사를 짓는 땅 일부를 발전사업에 활용하고 싶은데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0117 | 농사를 짓는 땅 일부를 발전사업에 활용하고 싶은데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0118 | 농사를 짓는 땅 일부를 발전사업에 활용하고 싶은데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0119 | 농지에서 공사하기 전에 지반·배수·경사와 농사에 미칠 영향을 어떻게 확인해야 하나요? | `site_land_building` |
| lay-energy-0120 | 농사를 짓는 땅 일부를 발전사업에 활용하고 싶은데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0121 | 산과 가까운 경사진 토지에 패널을 놓으려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0122 | 산과 가까운 경사진 토지에 패널을 놓으려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0123 | 산과 가까운 경사진 토지에 패널을 놓으려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0124 | 경사진 토지에서 공사하기 전에 경사면 붕괴·토사 유출·배수 위험을 어떻게 확인해야 하나요? | `site_land_building` |
| lay-energy-0125 | 산과 가까운 경사진 토지에 패널을 놓으려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0126 | 빌린 땅에서 장기간 태양광 발전소를 운영하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0127 | 토지 소유자의 동의를 받을 때 공사·철거·원상복구·임대기간을 계약서에 어떻게 정해야 하나요? | `site_land_building` |
| lay-energy-0128 | 빌린 땅에서 장기간 태양광 발전소를 운영하려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0129 | 빌린 땅에서 공사하기 전에 지반·배수·진입로와 주변 환경에서 어떤 위험을 살펴야 하나요? | `site_land_building` |
| lay-energy-0130 | 빌린 땅에서 장기간 태양광 발전소를 운영하려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0131 | 공장 지붕을 임차해 태양광 설비를 설치하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0132 | 공장 지붕 소유자와 공장 사용자가 다르면 각각 누구의 동의를 받고 임대계약에 무엇을 적어야 하나요? | `site_land_building` |
| lay-energy-0133 | 공장 지붕을 임차해 태양광 설비를 설치하려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0134 | 공장 지붕에 설치하기 전에 구조 안전·방수·화재·작업 동선에서 어떤 위험을 살펴야 하나요? | `site_land_building` |
| lay-energy-0135 | 공장 지붕을 임차해 태양광 설비를 설치하려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0136 | 상가 건물 옥상에 발전설비를 올리고 싶은데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0137 | 상가 건물 옥상에 발전설비를 올리고 싶은데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0138 | 상가 건물 옥상에 발전설비를 올리고 싶은데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0139 | 상가 옥상에 설치하기 전에 구조 안전·방수·화재·피난 동선에서 어떤 위험을 살펴야 하나요? | `site_land_building` |
| lay-energy-0140 | 상가 건물 옥상에 발전설비를 올리고 싶은데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0141 | 아파트 공용 옥상에 주민 공동 태양광을 설치하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0142 | 아파트 공용 옥상을 사용하려면 입주민과 관리주체의 동의를 어떤 방식으로 받아야 하나요? | `site_land_building` |
| lay-energy-0143 | 아파트 공용 옥상 설치에 필요한 공동주택 내부 절차와 건축 관련 절차는 무엇인가요? | `site_land_building` |
| lay-energy-0144 | 공사 전에 옥상 구조·방수·화재·피난과 주민 안전에서 어떤 위험을 살펴야 하나요? | `site_land_building` |
| lay-energy-0145 | 운영 중 입주자대표회의나 관리주체가 바뀌면 계약과 유지관리 책임은 어떻게 이어지나요? | `site_land_building` |
| lay-energy-0146 | 오래된 창고 지붕을 태양광 사업에 활용하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0147 | 오래된 창고 지붕을 태양광 사업에 활용하려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0148 | 오래된 창고 지붕을 태양광 사업에 활용하려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0149 | 오래된 창고 지붕에 태양광을 설치하기 전에 지붕 노후도·하중·석면·방수·화재 위험을 어떻게 확인해야 하나요? | `site_land_building` |
| lay-energy-0150 | 오래된 창고 지붕을 태양광 사업에 활용하려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0151 | 주차장 위에 태양광 구조물을 만들고 싶은데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0152 | 주차장 위에 태양광 구조물을 만들고 싶은데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0153 | 주차장 위에 태양광 구조물을 만들고 싶은데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0154 | 주차장 위에 태양광 구조물을 만들기 전에 기초·기둥·풍하중과 차량·보행자 동선의 위험을 어떻게 확인해야 하나요? | `site_land_building` |
| lay-energy-0155 | 주차장 위에 태양광 구조물을 만들고 싶은데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0156 | 축사 지붕에 패널을 설치해 전기를 판매하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0157 | 축사 지붕에 패널을 설치해 전기를 판매하려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0158 | 축사 지붕에 패널을 설치해 전기를 판매하려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0159 | 축사 지붕에 태양광을 설치하기 전에 지붕 하중·부식·화재와 가축·작업자 안전을 어떻게 확인해야 하나요? | `site_land_building` |
| lay-energy-0160 | 축사 지붕에 패널을 설치해 전기를 판매하려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0161 | 경계가 복잡한 여러 땅을 묶어 발전소를 지으려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0162 | 경계가 복잡한 여러 땅을 묶어 발전소를 지으려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0163 | 경계가 복잡한 여러 땅을 묶어 발전소를 지으려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0164 | 여러 필지를 묶어 공사하기 전에 경계·소유관계·진입로·지형에서 어떤 위험을 살펴야 하나요? | `site_land_building` |
| lay-energy-0165 | 경계가 복잡한 여러 땅을 묶어 발전소를 지으려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0166 | 도로가 없는 땅에 태양광 설비를 설치하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0167 | 도로가 없는 땅에 태양광 설비를 설치하려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0168 | 도로가 없는 땅에 태양광 설비를 설치하려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0169 | 공사차량 진입로와 장기 통행권을 어떻게 확보하고 확인해야 하나요? | `site_land_building` |
| lay-energy-0170 | 도로가 없는 땅에 태양광 설비를 설치하려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0171 | 문화재나 보호구역과 가까운 부지를 검토 중인데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0172 | 문화재나 보호구역과 가까운 부지를 검토 중인데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0173 | 문화재나 보호구역과 가까운 부지를 검토 중인데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0174 | 문화재나 보호구역과 가까운 부지에서 보호구역 규제·거리·경관·환경 또는 문화재 조사 필요성을 어떻게 확인해야 하나요? | `site_land_building` |
| lay-energy-0175 | 문화재나 보호구역과 가까운 부지를 검토 중인데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0176 | 주택가 근처 빈 땅에 소규모 발전소를 만들려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0177 | 주택가 근처 빈 땅에 소규모 발전소를 만들려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0178 | 주택가 근처 빈 땅에 소규모 발전소를 만들려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0179 | 공사 전에 소음·반사광·배수·화재와 주민 민원 위험을 무엇부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0180 | 주택가 근처 빈 땅에 소규모 발전소를 만들려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0181 | 건물 소유자와 사용자가 다른 곳에 설비를 설치하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0182 | 건물 소유자와 실제 사용자의 동의를 각각 받아야 하나요, 계약에는 책임을 어떻게 나눠 적어야 하나요? | `site_land_building` |
| lay-energy-0183 | 건물 소유자와 사용자가 다른 곳에 설비를 설치하려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0184 | 건물 소유자와 사용자가 다른 곳에서 공사를 위해 건물에 출입할 때 필요한 동의와 시설 훼손·안전·복구 책임을 어떻게 나눠야 하나요? | `site_land_building` |
| lay-energy-0185 | 건물 소유자와 사용자가 다른 곳에 설비를 설치하려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0186 | 곧 용도가 바뀔 예정인 토지에 먼저 발전소를 지으려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0187 | 곧 용도가 바뀔 예정인 토지에 먼저 발전소를 지으려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0188 | 곧 용도가 바뀔 예정인 토지에 먼저 발전소를 지으려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0189 | 토지 용도가 바뀌기 전에 공사를 시작해도 되는지와 공사 시점별 위험을 어디서 확인해야 하나요? | `site_land_building` |
| lay-energy-0190 | 곧 용도가 바뀔 예정인 토지에 먼저 발전소를 지으려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0191 | 침수 이력이 있는 부지에 태양광을 설치해도 될지 고민인데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0192 | 침수 이력이 있는 부지에 태양광을 설치해도 될지 고민인데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0193 | 침수 이력이 있는 부지에 태양광을 설치해도 될지 고민인데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0194 | 공사 전에 예상 침수 높이·배수 능력·전기설비 배치를 어떻게 확인해야 하나요? | `site_land_building` |
| lay-energy-0195 | 침수 이력이 있는 부지에 태양광을 설치해도 될지 고민인데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |
| lay-energy-0196 | 다른 시설과 태양광 발전소를 같은 부지에 함께 운영하려는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0197 | 다른 시설과 태양광 발전소를 같은 부지에 함께 운영하려는데, 땅이나 건물 주인이 따로 있다면 누구의 동의를 받고 계약에서 무엇을 확인해야 하나요? | `site_land_building` |
| lay-energy-0198 | 다른 시설과 태양광 발전소를 같은 부지에 함께 운영하려는데, 토지 이용과 건축 관련 절차를 어디서부터 확인해야 하나요? | `site_land_building` |
| lay-energy-0199 | 다른 시설과 태양광 발전소를 같은 부지에 함께 운영하려는데, 공사 전에 건물 구조·지형·주변 환경에서 어떤 위험을 살펴야 하나요? | `site_land_building` |
| lay-energy-0200 | 다른 시설과 태양광 발전소를 같은 부지에 함께 운영하려는데, 운영 중 주인·용도·임대기간이 바뀌면 허가나 운영에 어떤 문제가 생길 수 있나요? | `site_land_building` |

</details>

<details>
<summary>허가·신고·서류 — 90개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0201 | 태양광 발전소 허가를 준비하고 있는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0202 | 태양광 발전소 허가를 준비하고 있는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0203 | 태양광 발전소 허가를 준비하고 있는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0204 | 태양광 발전소 허가를 준비하고 있는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0205 | 태양광 발전소 허가를 준비하고 있는데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0206 | 발전설비 용량을 정한 뒤 신청하려는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0207 | 발전설비 용량을 정한 뒤 신청하려는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0208 | 발전설비 용량을 정한 뒤 신청하려는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0209 | 발전설비 용량을 정한 뒤 신청하려는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0210 | 발전설비 용량을 정한 뒤 신청하려는데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0211 | 개인 명의로 발전사업을 신청하려는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0212 | 개인 명의로 발전사업을 신청하려는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0213 | 개인 명의로 발전사업을 신청하려는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0214 | 개인 명의로 발전사업을 신청하려는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0215 | 개인 명의로 발전사업을 신청하려는데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0216 | 새 법인을 세워 발전소 허가를 받으려는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0217 | 새 법인을 세워 발전소 허가를 받으려는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0218 | 새 법인을 세워 발전소 허가를 받으려는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0219 | 새 법인을 세워 발전소 허가를 받으려는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0220 | 새 법인을 세워 발전소 허가를 받으려는데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0221 | 허가받은 사업계획에서 설비 구성을 바꾸려는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0222 | 허가받은 사업계획에서 설비 구성을 바꾸려는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0223 | 허가받은 사업계획에서 설비 구성을 바꾸려는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0224 | 허가받은 사업계획에서 설비 구성을 바꾸려는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0225 | 허가받은 설비를 먼저 바꾼 뒤 나중에 알리면 어떤 문제가 생기나요? | `permits_documents_general` |
| lay-energy-0226 | 발전소 위치를 다른 땅으로 옮기고 싶은데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0227 | 발전소 위치를 다른 땅으로 옮기고 싶은데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0228 | 발전소 위치를 다른 땅으로 옮기고 싶은데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0229 | 발전소 위치를 다른 땅으로 옮기고 싶은데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0230 | 발전소를 새 부지로 옮기기 전에 기존 허가 정리와 새 부지 검토 중 무엇을 먼저 처리해야 하나요? | `permits_documents_general` |
| lay-energy-0231 | 사업자 이름과 대표자가 바뀔 예정인데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0232 | 사업자 이름과 대표자가 바뀔 예정인데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0233 | 사업자 이름과 대표자가 바뀔 예정인데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0234 | 사업자 이름과 대표자가 바뀔 예정인데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0235 | 사업자 이름이나 대표자 변경을 늦게 신고하면 어떤 문제가 생기나요? | `permits_documents_general` |
| lay-energy-0236 | 발전소 일부만 먼저 가동하고 싶은데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0237 | 발전소 일부만 먼저 가동하고 싶은데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0238 | 발전소 일부만 먼저 가동하고 싶은데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0239 | 발전소 일부만 먼저 가동하고 싶은데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0240 | 일부 설비만 먼저 가동할 때 검사와 사업 개시 신고는 어느 범위까지 먼저 해야 하나요? | `permits_documents_general` |
| lay-energy-0241 | 여러 종류의 발전설비를 한 사업으로 신청하려는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0242 | 여러 종류의 발전설비를 한 사업으로 신청하려는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0243 | 여러 종류의 발전설비를 한 사업으로 신청하려는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0244 | 여러 종류의 발전설비를 한 사업으로 신청하려는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0245 | 여러 종류의 발전설비를 한 사업으로 신청하려는데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0246 | 기존 공장에 자가발전 설비를 추가하려는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0247 | 기존 공장에 자가발전 설비를 추가하려는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0248 | 기존 공장에 자가발전 설비를 추가하려는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0249 | 기존 공장에 자가발전 설비를 추가하려는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0250 | 기존 공장에 자가발전 설비를 추가하려는데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0251 | 소규모 설비는 용량이나 전기 사용 방식에 따라 허가와 신고가 어떻게 달라지나요? | `permits_documents_general` |
| lay-energy-0252 | 소규모 설비라 허가 대신 신고만 하면 되는지 궁금한데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0253 | 소규모 설비라 허가 대신 신고만 하면 되는지 궁금한데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0254 | 소규모 설비라 허가 대신 신고만 하면 되는지 궁금한데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0255 | 소규모 설비라 허가 대신 신고만 하면 되는지 궁금한데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0256 | 허가와 토지 관련 신청을 같이 진행하고 싶은데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0257 | 허가와 토지 관련 신청을 같이 진행하고 싶은데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0258 | 허가와 토지 관련 신청을 같이 진행하고 싶은데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0259 | 허가와 토지 관련 신청을 같이 진행하고 싶은데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0260 | 허가와 토지 관련 신청을 같이 진행하고 싶은데, 계획이 달라졌을 때 다시 허가받거나 알려야 하는 범위는 어디까지인가요? | `permits_documents_general` |
| lay-energy-0261 | 외국인이 투자한 법인으로 발전사업을 하려는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | `permits_documents_general` |
| lay-energy-0262 | 외국인이 투자한 법인으로 발전사업을 하려는데, 어디에 신청하고 담당 기관은 어떻게 찾나요? | `permits_documents_general` |
| lay-energy-0263 | 외국인이 투자한 법인으로 발전사업을 하려는데, 기본적으로 준비해야 할 서류는 무엇인가요? | `permits_documents_general` |
| lay-energy-0264 | 외국인이 투자한 법인으로 발전사업을 하려는데, 보완 요청을 줄이려면 신청 전에 무엇을 확인해야 하나요? | `permits_documents_general` |
| lay-energy-0265 | 외국인 투자 비율이나 주주 구성이 바뀌면 추가로 허가받거나 신고해야 하나요? | `permits_documents_general` |
| lay-energy-0266 | 공사가 늦어져 당초 계획대로 사업을 시작하기 어려운데, 사업 시작 기한을 연장하거나 계획을 바꾸려면 어떤 신청이 필요한가요? | `permit_construction_delay` |
| lay-energy-0267 | 공사가 늦어져 당초 계획대로 사업을 시작하기 어려운데, 기한 연장은 어느 기관에 언제까지 신청해야 하나요? | `permit_construction_delay` |
| lay-energy-0268 | 공사가 늦어져 당초 계획대로 사업을 시작하기 어려운데, 공사 지연 사유를 보여 줄 어떤 서류가 필요한가요? | `permit_construction_delay` |
| lay-energy-0269 | 공사가 늦어져 당초 계획대로 사업을 시작하기 어려운데, 지연 사유를 인정받으려면 무엇을 확인해야 하나요? | `permit_construction_delay` |
| lay-energy-0270 | 공사가 늦어져 당초 계획대로 사업을 시작하기 어려운데, 정해진 기한을 넘기면 사업 허가에 어떤 영향이 있나요? | `permit_construction_delay` |
| lay-energy-0271 | 사업 관련 신청을 온라인으로 진행하려는데, 온라인으로 할 수 있는 신청과 직접 방문해야 하는 신청은 무엇인가요? | `permit_online_application` |
| lay-energy-0272 | 사업 관련 신청을 온라인으로 진행하려는데, 신청 사이트와 본인·사업자 확인 방법은 어디서 안내받나요? | `permit_online_application` |
| lay-energy-0273 | 사업 관련 신청을 온라인으로 진행하려는데, 서류 형식과 파일 용량은 어디서 확인하나요? | `permit_online_application` |
| lay-energy-0274 | 사업 관련 신청을 온라인으로 진행하려는데, 접수 여부와 처리 상태는 어떻게 확인하나요? | `permit_online_application` |
| lay-energy-0275 | 사업 관련 신청을 온라인으로 진행하려는데, 제출한 신청을 고치거나 취소하려면 어떻게 하나요? | `permit_online_application` |
| lay-energy-0276 | 제출한 서류에 빠진 내용이 있다는 연락을 받았는데, 안내문과 기존 서류에서 무엇을 먼저 확인해야 하나요? | `permit_document_correction` |
| lay-energy-0277 | 제출한 서류에 빠진 내용이 있다는 연락을 받았는데, 보완 서류는 어디에 어떤 방법으로 다시 제출하나요? | `permit_document_correction` |
| lay-energy-0278 | 빠진 내용을 보완하려면 어떤 자료를 추가해야 하나요? | `permit_document_correction` |
| lay-energy-0279 | 제출한 서류에 빠진 내용이 있다는 연락을 받았는데, 보완 기한과 담당자는 어디서 확인하나요? | `permit_document_correction` |
| lay-energy-0280 | 제출한 서류에 빠진 내용이 있다는 연락을 받았는데, 기한을 넘기거나 다시 빠뜨리면 신청은 어떻게 되나요? | `permit_document_correction` |
| lay-energy-0281 | 신청 후 담당 기관이 달라졌다는 안내를 받았는데, 기존 신청은 자동으로 넘어가나요, 다시 신청해야 하나요? | `permit_office_change` |
| lay-energy-0282 | 신청 후 담당 기관이 달라졌다는 안내를 받았는데, 새 담당 기관과 담당자를 어디서 확인하나요? | `permit_office_change` |
| lay-energy-0283 | 신청 후 담당 기관이 달라졌다는 안내를 받았는데, 이미 낸 서류를 다시 제출해야 하나요? | `permit_office_change` |
| lay-energy-0284 | 신청 후 담당 기관이 달라졌다는 안내를 받았는데, 담당 기관 변경으로 처리가 늦어지지 않게 무엇을 확인해야 하나요? | `permit_office_change` |
| lay-energy-0285 | 신청 후 담당 기관이 달라졌다는 안내를 받았는데, 이전 기관의 보완 요청과 처리 기한은 그대로 이어지나요? | `permit_office_change` |
| lay-energy-0286 | 허가받기 전에 시공업체와 공사 계약을 맺으려는데, 허가 전에 계약해도 되는지 무엇을 먼저 확인해야 하나요? | `permit_before_construction_contract` |
| lay-energy-0287 | 허가받기 전에 시공업체와 공사 계약을 맺으려는데, 허가가 나지 않으면 계약을 취소하고 계약금을 돌려받을 수 있나요? | `permit_before_construction_contract` |
| lay-energy-0288 | 허가받기 전에 시공업체와 공사 계약을 맺으려는데, 허가 실패 때 처리와 비용 부담을 계약서에 어떻게 적어야 하나요? | `permit_before_construction_contract` |
| lay-energy-0289 | 허가받기 전에 시공업체와 공사 계약을 맺으려는데, 업체가 말한 허가 가능성을 어디서 확인해야 하나요? | `permit_before_construction_contract` |
| lay-energy-0290 | 허가받기 전에 시공업체와 공사 계약을 맺으려는데, 허가 내용이 예상과 다르면 공사 범위와 대금을 어떻게 바꾸나요? | `permit_before_construction_contract` |

</details>

<details>
<summary>계통연계·한전 계약 — 90개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0291 | 태양광 발전소를 전력망에 연결하려는데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? | `grid_connection_general` |
| lay-energy-0292 | 태양광 발전소를 전력망에 연결하려는데, 신청부터 공사와 계량기 설치까지 어떤 순서로 진행하나요? | `grid_connection_general` |
| lay-energy-0293 | 태양광 발전소를 전력망에 연결하려는데, 가능한 계약 방식과 각각의 차이는 무엇인가요? | `grid_connection_general` |
| lay-energy-0294 | 태양광 발전소를 전력망에 연결하려는데, 용량 부족이나 대기가 생기면 어떤 선택지가 있나요? | `grid_connection_general` |
| lay-energy-0295 | 태양광 발전소를 전력망에 연결하려는데, 연계 공사 범위와 비용 부담은 어떻게 확인하나요? | `grid_connection_general` |
| lay-energy-0296 | 사업 부지 근처 선로에 여유가 없다는 말을 들었는데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? | `grid_connection_general` |
| lay-energy-0297 | 사업 부지 근처 선로에 여유가 없다는 말을 들었는데, 신청부터 공사와 계량기 설치까지 어떤 순서로 진행하나요? | `grid_connection_general` |
| lay-energy-0298 | 사업 부지 근처 선로에 여유가 없다는데, 신청을 유지한 채 기다리거나 다른 연결 지점을 검토할 수 있나요? | `grid_connection_general` |
| lay-energy-0299 | 사업 부지 근처 선로에 여유가 없다는 말을 들었는데, 용량 부족이나 대기가 생기면 어떤 선택지가 있나요? | `grid_connection_general` |
| lay-energy-0300 | 사업 부지 근처 선로에 여유가 없다는 말을 들었는데, 연계 공사 범위와 비용 부담은 어떻게 확인하나요? | `grid_connection_general` |
| lay-energy-0301 | 발전소 용량을 늘리면서 전력망 연결도 확대하려는데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? | `grid_connection_general` |
| lay-energy-0302 | 발전소 용량을 늘리면서 전력망 연결도 확대하려는데, 신청부터 공사와 계량기 설치까지 어떤 순서로 진행하나요? | `grid_connection_general` |
| lay-energy-0303 | 발전소 용량을 늘리면서 전력망 연결도 확대하려는데, 가능한 계약 방식과 각각의 차이는 무엇인가요? | `grid_connection_general` |
| lay-energy-0304 | 발전소 용량을 늘리면서 전력망 연결도 확대하려는데, 용량 부족이나 대기가 생기면 어떤 선택지가 있나요? | `grid_connection_general` |
| lay-energy-0305 | 발전소 용량을 늘리면서 전력망 연결도 확대하려는데, 연계 공사 범위와 비용 부담은 어떻게 확인하나요? | `grid_connection_general` |
| lay-energy-0306 | 여러 발전소를 한 곳의 연결 지점으로 묶으려는데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? | `grid_connection_general` |
| lay-energy-0307 | 여러 발전소를 한 곳의 연결 지점으로 묶으려는데, 신청부터 공사와 계량기 설치까지 어떤 순서로 진행하나요? | `grid_connection_general` |
| lay-energy-0308 | 여러 발전소를 한 곳의 연결 지점으로 묶으려는데, 가능한 계약 방식과 각각의 차이는 무엇인가요? | `grid_connection_general` |
| lay-energy-0309 | 여러 발전소를 한 곳의 연결 지점으로 묶으려는데, 용량 부족이나 대기가 생기면 어떤 선택지가 있나요? | `grid_connection_general` |
| lay-energy-0310 | 여러 발전소를 한 곳의 연결 지점으로 묶으려는데, 연계 공사 범위와 비용 부담은 어떻게 확인하나요? | `grid_connection_general` |
| lay-energy-0311 | 발전소 위치를 바꾼 뒤 기존 전력망 연결 계약을 유지하고 싶은데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? | `grid_connection_general` |
| lay-energy-0312 | 발전소 위치를 바꾼 뒤 기존 전력망 연결 계약을 유지하고 싶은데, 신청부터 공사와 계량기 설치까지 어떤 순서로 진행하나요? | `grid_connection_general` |
| lay-energy-0313 | 발전소 위치를 바꾼 뒤 기존 연결 계약을 변경·승계할 수 있는지, 해지하고 다시 신청해야 하는지 어떻게 확인하나요? | `grid_connection_general` |
| lay-energy-0314 | 발전소 위치를 바꾼 뒤 기존 전력망 연결 계약을 유지하고 싶은데, 용량 부족이나 대기가 생기면 어떤 선택지가 있나요? | `grid_connection_general` |
| lay-energy-0315 | 발전소 위치를 바꾼 뒤 기존 전력망 연결 계약을 유지하고 싶은데, 연계 공사 범위와 비용 부담은 어떻게 확인하나요? | `grid_connection_general` |
| lay-energy-0316 | 전력망 연결이 확정되기 전에 발전설비 공사를 먼저 시작하려는데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? | `grid_connection_general` |
| lay-energy-0317 | 전력망 연결이 확정되기 전에 발전설비 공사를 먼저 시작하려는데, 신청부터 공사와 계량기 설치까지 어떤 순서로 진행하나요? | `grid_connection_general` |
| lay-energy-0318 | 전력망 연결이 확정되기 전에 공사를 시작했다가 연결이 취소되거나 용량이 줄면 공사비를 누가 부담하는지 계약서에서 무엇을 확인해야 하나요? | `grid_connection_general` |
| lay-energy-0319 | 전력망 연결이 확정되기 전에 발전설비 공사를 먼저 시작하려는데, 용량 부족이나 대기가 생기면 어떤 선택지가 있나요? | `grid_connection_general` |
| lay-energy-0320 | 전력망 연결이 확정되기 전에 발전설비 공사를 먼저 시작하려는데, 연계 공사 범위와 비용 부담은 어떻게 확인하나요? | `grid_connection_general` |
| lay-energy-0321 | 전력회사에 전기를 파는 방식으로 계약하려는데, 가능한 판매 방식과 적용 조건은 어떻게 다른가요? | `electricity_sale_contract_options` |
| lay-energy-0322 | 전력회사에 전기를 파는 방식으로 계약하려는데, 누구와 어떤 계약을 맺어야 하나요? | `electricity_sale_contract_options` |
| lay-energy-0323 | 전력회사에 전기를 파는 방식으로 계약하려는데, 판매를 시작하기 전에 어떤 신청과 등록이 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0324 | 전량을 파는 경우와 제가 먼저 쓰고 남는 전기를 파는 경우에는 계량기가 어떻게 달라지나요? | `electricity_sale_contract_options` |
| lay-energy-0325 | 전력회사에 전기를 파는 방식으로 계약하려는데, 전기요금 처리와 판매대금 정산은 어떻게 달라지나요? | `electricity_sale_contract_options` |
| lay-energy-0326 | 전력시장에서 직접 전기를 판매하는 방식을 검토 중인데, 가능한 판매 방식과 적용 조건은 어떻게 다른가요? | `electricity_sale_contract_options` |
| lay-energy-0327 | 전력시장에서 직접 전기를 판매하는 방식을 검토 중인데, 누구와 어떤 계약을 맺어야 하나요? | `electricity_sale_contract_options` |
| lay-energy-0328 | 전력시장에서 직접 전기를 판매하는 방식을 검토 중인데, 판매를 시작하기 전에 어떤 신청과 등록이 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0329 | 전력시장 판매량과 발전소에서 자체 사용한 전력을 구분하려면 어떤 계량 설비가 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0330 | 전력시장 판매대금은 어떤 기준과 주기로 정산되며, 발전소가 외부 전력망에서 공급받아 사용한 전기의 요금은 어떻게 처리되나요? | `electricity_sale_contract_options` |
| lay-energy-0331 | 공장에서 쓰고 남는 태양광 전기를 판매하려는데, 가능한 판매 방식과 적용 조건은 어떻게 다른가요? | `electricity_sale_contract_options` |
| lay-energy-0332 | 공장에서 쓰고 남는 태양광 전기를 판매하려는데, 누구와 어떤 계약을 맺어야 하나요? | `electricity_sale_contract_options` |
| lay-energy-0333 | 공장에서 쓰고 남는 태양광 전기를 판매하려는데, 판매를 시작하기 전에 어떤 신청과 등록이 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0334 | 공장에서 쓰고 남는 태양광 전기를 판매하려는데, 사용한 전기와 판매한 전기를 구분하려면 어떤 계량기가 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0335 | 공장에서 쓰고 남는 태양광 전기를 판매하려는데, 전기요금 처리와 판매대금 정산은 어떻게 달라지나요? | `electricity_sale_contract_options` |
| lay-energy-0336 | 제가 먼저 쓰고 남는 전기를 파는 방식으로 바꾸려는데, 가능한 판매 방식과 적용 조건은 어떻게 다른가요? | `electricity_sale_contract_options` |
| lay-energy-0337 | 제가 먼저 쓰고 남는 전기를 파는 방식으로 바꾸려는데, 누구와 어떤 계약을 맺어야 하나요? | `electricity_sale_contract_options` |
| lay-energy-0338 | 제가 먼저 쓰고 남는 전기를 파는 방식으로 바꾸려는데, 판매를 시작하기 전에 어떤 신청과 등록이 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0339 | 제가 먼저 쓰고 남는 전기를 파는 방식으로 바꾸려는데, 사용한 전기와 판매한 전기를 구분하려면 어떤 계량기가 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0340 | 제가 먼저 쓰고 남는 전기를 파는 방식으로 바꾸려는데, 전기요금 처리와 판매대금 정산은 어떻게 달라지나요? | `electricity_sale_contract_options` |
| lay-energy-0341 | 남는 전기를 전기요금에서 빼는 방식과 현금으로 파는 방식 중 무엇이 맞는지 고민인데, 가능한 판매 방식과 적용 조건은 어떻게 다른가요? | `electricity_sale_contract_options` |
| lay-energy-0342 | 남는 전기를 전기요금에서 빼는 방식과 현금으로 파는 방식 중 무엇이 맞는지 고민인데, 누구와 어떤 계약을 맺어야 하나요? | `electricity_sale_contract_options` |
| lay-energy-0343 | 남는 전기를 전기요금에서 차감하는 방식과 현금으로 판매하는 방식 중 하나를 이용하려면 어떤 신청과 등록이 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0344 | 남는 전기를 전기요금에서 빼는 방식과 현금으로 파는 방식 중 무엇이 맞는지 고민인데, 사용한 전기와 판매한 전기를 구분하려면 어떤 계량기가 필요한가요? | `electricity_sale_contract_options` |
| lay-energy-0345 | 남는 전기를 전기요금에서 빼는 방식과 현금으로 파는 방식 중 무엇이 맞는지 고민인데, 전기요금 처리와 판매대금 정산은 어떻게 달라지나요? | `electricity_sale_contract_options` |
| lay-energy-0346 | 전력망 연결 공사비가 예상보다 많이 나왔는데, 공사비가 어떻게 계산됐는지 어떤 항목을 확인해야 하나요? | `grid_connection_cost` |
| lay-energy-0347 | 전력망 연결 공사비가 예상보다 많이 나왔는데, 산정 금액에 이의가 있으면 누구에게 확인을 요청하나요? | `grid_connection_cost` |
| lay-energy-0348 | 전력망 연결 공사비가 예상보다 많이 나왔는데, 연결 방식이나 설비 용량을 바꾸면 비용을 줄일 수 있나요? | `grid_connection_cost` |
| lay-energy-0349 | 전력망 연결 공사비가 예상보다 많이 나왔는데, 비용 때문에 신청을 바꾸거나 미루면 대기 순서에 어떤 영향이 있나요? | `grid_connection_cost` |
| lay-energy-0350 | 전력망 연결 공사비가 예상보다 많이 나왔는데, 발전사업자와 전력회사가 각각 부담하는 공사 범위는 어디까지인가요? | `grid_connection_cost` |
| lay-energy-0351 | 전력망 연결 신청 후 오랫동안 순서를 기다리고 있는데, 현재 대기 순서와 예상 연결 시점을 어디서 확인하나요? | `grid_connection_wait` |
| lay-energy-0352 | 전력망 연결 신청 후 오랫동안 순서를 기다리고 있는데, 차례가 돌아온 뒤 검토·공사·계량기 설치는 어떤 순서로 진행되나요? | `grid_connection_wait` |
| lay-energy-0353 | 전력망 연결 신청 후 오랫동안 순서를 기다리고 있는데, 기다리는 동안 신청 용량이나 연결 위치를 바꾸면 순서가 달라지나요? | `grid_connection_wait` |
| lay-energy-0354 | 전력망 연결 신청 후 오랫동안 순서를 기다리고 있는데, 다른 연결 위치나 더 작은 용량으로 먼저 시작할 수 있나요? | `grid_connection_wait` |
| lay-energy-0355 | 전력망 연결 신청 후 오랫동안 순서를 기다리고 있는데, 대기가 길어지면 처음 안내받은 공사 범위와 비용이 바뀔 수 있나요? | `grid_connection_wait` |
| lay-energy-0356 | 건물에 들어오는 전력회사 전기와 옥상 태양광 전기를 함께 쓰려는데, 두 전원을 안전하게 함께 쓰려면 설비 구성이 어떻게 달라야 하나요? | `building_solar_parallel_use` |
| lay-energy-0357 | 건물에 들어오는 전력회사 전기와 옥상 태양광 전기를 함께 쓰려는데, 전력회사에 어떤 연결 신청을 해야 하나요? | `building_solar_parallel_use` |
| lay-energy-0358 | 건물에 들어오는 전력회사 전기와 옥상 태양광 전기를 함께 쓰려는데, 공사 뒤 어떤 검사와 확인을 받아야 하나요? | `building_solar_parallel_use` |
| lay-energy-0359 | 건물에 들어오는 전력회사 전기와 옥상 태양광 전기를 함께 쓰려는데, 전력회사 전기와 태양광 발전량을 어떻게 나눠 측정하나요? | `building_solar_parallel_use` |
| lay-energy-0360 | 전력회사 전기와 옥상 태양광을 함께 쓰는 건물에서 정전이나 고장이 나면, 직접 만지지 않고 두 전원이 안전하게 끊어지도록 어떤 차단 장치와 전문가 점검이 필요한가요? | `building_solar_parallel_use` |
| lay-energy-0361 | 정전 때도 태양광 전기를 계속 쓰고 싶은데, 일반 태양광 설비와 무엇이 달라야 하나요? | `solar_during_outage` |
| lay-energy-0362 | 정전 때도 태양광 전기를 계속 쓰고 싶은데, 배터리나 전환 장치는 어떤 기준으로 골라야 하나요? | `solar_during_outage` |
| lay-energy-0363 | 정전 때도 태양광 전기를 계속 쓰고 싶은데, 추가 설비를 설치한 뒤 어떤 검사와 확인이 필요한가요? | `solar_during_outage` |
| lay-energy-0364 | 정전 때도 태양광 전기를 계속 쓰고 싶은데, 정전 중 사용할 전력에 맞춰 설비 용량을 어떻게 정하나요? | `solar_during_outage` |
| lay-energy-0365 | 정전 때도 태양광 전기를 계속 쓰고 싶은데, 정전 대비 기능을 추가할 때 필요한 공사와 비용은 어떻게 확인하나요? | `solar_during_outage` |
| lay-energy-0366 | 발전량 계량기를 추가하거나 교체해야 한다는 안내를 받았는데, 왜 추가하거나 교체해야 하는지 어떤 기준과 자료로 확인하나요? | `generation_meter_change` |
| lay-energy-0367 | 발전량 계량기를 추가하거나 교체해야 한다는 안내를 받았는데, 계량기 작업은 어디에 신청하고 어떤 순서로 진행하나요? | `generation_meter_change` |
| lay-energy-0368 | 발전량 계량기를 추가하거나 교체해야 한다는 안내를 받았는데, 추가하는 경우와 교체하는 경우 계약·정산 방식이 어떻게 달라지나요? | `generation_meter_change` |
| lay-energy-0369 | 발전량 계량기를 추가하거나 교체해야 한다는 안내를 받았는데, 작업 중에는 발전이나 전기 판매를 중단해야 하나요? | `generation_meter_change` |
| lay-energy-0370 | 발전량 계량기를 추가하거나 교체해야 한다는 안내를 받았는데, 교체 뒤 이전 계량값과 정산 내역은 어떻게 이어지나요? | `generation_meter_change` |
| lay-energy-0371 | 연결 가능한 용량이 발전사업 계획보다 작게 나왔는데, 가능한 용량만으로 먼저 사업을 시작할 수 있나요? | `grid_capacity_below_plan` |
| lay-energy-0372 | 연결 가능한 용량이 발전사업 계획보다 작게 나왔는데, 용량이 작게 나온 이유와 계산 근거를 어디서 확인하나요? | `grid_capacity_below_plan` |
| lay-energy-0373 | 연결 가능한 용량이 발전사업 계획보다 작게 나왔는데, 발전설비와 사업계획을 줄이려면 어떤 변경 절차가 필요한가요? | `grid_capacity_below_plan` |
| lay-energy-0374 | 연결 가능한 용량이 발전사업 계획보다 작게 나왔는데, 부족한 용량은 나중에 추가하거나 증설 때까지 기다릴 수 있나요? | `grid_capacity_below_plan` |
| lay-energy-0375 | 연결 가능한 용량이 발전사업 계획보다 작게 나왔는데, 다른 연결 위치나 방식을 검토하려면 누구와 상담해야 하나요? | `grid_capacity_below_plan` |
| lay-energy-0376 | 전력회사 계약과 전력거래소 절차가 어떻게 다른지 궁금한데, 전력망 연결과 시장 등록은 각각 어느 기관이 담당하나요? | `grid_market_agency_roles` |
| lay-energy-0377 | 전력회사 계약과 전력거래소 절차가 어떻게 다른지 궁금한데, 두 기관의 신청은 어떤 순서로 진행해야 하나요? | `grid_market_agency_roles` |
| lay-energy-0378 | 전력회사 계약과 전력거래소 절차가 어떻게 다른지 궁금한데, 같은 서류를 두 기관에 모두 제출해야 하나요? | `grid_market_agency_roles` |
| lay-energy-0379 | 전력회사 계약과 전력거래소 절차가 어떻게 다른지 궁금한데, 연결 용량이 부족하면 어느 기관에 먼저 확인해야 하나요? | `grid_market_agency_roles` |
| lay-energy-0380 | 전력회사 계약과 전력거래소 절차가 어떻게 다른지 궁금한데, 연결 공사비와 전력거래 비용은 각각 누가 청구하나요? | `grid_market_agency_roles` |

</details>

<details>
<summary>시공·설비·인증 — 60개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0381 | 태양광 시공업체를 처음 고르려는데, 업체의 자격과 실적을 어떻게 확인해야 하나요? | `construction_equipment_general` |
| lay-energy-0382 | 태양광 시공업체를 처음 고르려는데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0383 | 태양광 시공업체를 처음 고르려는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0384 | 태양광 시공업체를 처음 고르려는데, 공사 중 자재나 설계를 바꾸면 어떤 확인이 필요한가요? | `construction_equipment_general` |
| lay-energy-0385 | 태양광 시공업체를 처음 고르려는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0386 | 견적서마다 패널과 인버터 구성이 다른데, 효율·호환성·보증을 같은 기준으로 어떻게 비교하나요? | `construction_equipment_general` |
| lay-energy-0387 | 견적서마다 패널과 인버터 구성이 달라 고민인데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0388 | 견적서마다 패널과 인버터 구성이 달라 고민인데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0389 | 서로 다른 견적의 패널 수, 인버터 용량, 예상 발전량을 어떻게 같은 기준으로 맞춰 비교하나요? | `construction_equipment_general` |
| lay-energy-0390 | 견적서마다 패널과 인버터 구성이 달라 고민인데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0391 | 제품에 적힌 인증번호와 모델명이 실제 인증 정보와 같은지 어디서 확인하나요? | `construction_equipment_general` |
| lay-energy-0392 | 인증받은 설비인지 확인하고 계약하려는데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0393 | 인증받은 설비인지 확인하고 계약하려는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0394 | 인증받은 설비인지 확인하고 계약하려는데, 공사 중 자재나 설계를 바꾸면 어떤 확인이 필요한가요? | `construction_equipment_general` |
| lay-energy-0395 | 인증받은 설비인지 확인하고 계약하려는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0396 | 외국산 모듈과 국산 인버터를 함께 써도 호환성과 국내 인증에 문제가 없는지 어떻게 확인하나요? | `construction_equipment_general` |
| lay-energy-0397 | 외국산 모듈과 국산 인버터를 함께 쓰려는데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0398 | 외국산 모듈과 국산 인버터를 함께 쓰려는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0399 | 서로 다른 제조사의 모듈과 인버터를 조합하면 성능·보증·검사에 어떤 영향이 있나요? | `construction_equipment_general` |
| lay-energy-0400 | 외국산 모듈과 국산 인버터를 함께 쓰려는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0401 | 기존 구조물 위에 새 패널을 추가하려는데, 업체의 자격과 실적을 어떻게 확인해야 하나요? | `construction_equipment_general` |
| lay-energy-0402 | 기존 구조물 위에 새 패널을 추가하려는데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0403 | 기존 구조물 위에 새 패널을 추가하려는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0404 | 기존 구조물 위에 새 패널을 추가하려는데, 공사 중 자재나 설계를 바꾸면 어떤 확인이 필요한가요? | `construction_equipment_general` |
| lay-energy-0405 | 기존 구조물 위에 새 패널을 추가하려는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0406 | 제안받은 대체 부품이 원래 설계한 부품과 성능·인증 면에서 같은지 어떻게 확인하나요? | `construction_equipment_general` |
| lay-energy-0407 | 공사 중 설계와 다른 부품을 쓰겠다는 제안을 받았는데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0408 | 공사 중 설계와 다른 부품을 쓰겠다는 제안을 받았는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0409 | 부품을 바꾸기 전에 설계자 승인, 계약 변경, 재검사 중 무엇이 필요한가요? | `construction_equipment_general` |
| lay-energy-0410 | 공사 중 설계와 다른 부품을 쓰겠다는 제안을 받았는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0411 | 여러 시공업체가 공정을 나눠 맡기로 했는데, 업체의 자격과 실적을 어떻게 확인해야 하나요? | `construction_equipment_general` |
| lay-energy-0412 | 공정을 나눠 맡는 각 업체가 담당 작업에 필요한 자격을 갖췄는지 어떻게 확인하나요? | `construction_equipment_general` |
| lay-energy-0413 | 여러 시공업체가 공정을 나눠 맡기로 했는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0414 | 업체 사이에 설계 변경이나 하자 책임이 떠넘겨지지 않게 승인 절차를 어떻게 정해야 하나요? | `construction_equipment_general` |
| lay-energy-0415 | 여러 시공업체가 공정을 나눠 맡기로 했는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0416 | 발전효율이 높아진다는 업체 설명을 실제 시험자료와 보증 조건으로 어떻게 확인하나요? | `construction_equipment_general` |
| lay-energy-0417 | 발전효율을 높여준다는 추가 장치를 설치하려는데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0418 | 발전효율을 높여준다는 추가 장치를 설치하려는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0419 | 추가 장치를 달면 기존 설비의 인증·보증·검사를 다시 확인해야 하나요? | `construction_equipment_general` |
| lay-energy-0420 | 발전효율을 높여준다는 추가 장치를 설치하려는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0421 | 중고 발전설비를 이전해 다시 설치하려는데, 업체의 자격과 실적을 어떻게 확인해야 하나요? | `construction_equipment_general` |
| lay-energy-0422 | 중고 발전설비를 이전해 다시 설치하려는데, 설비 인증과 제품 정보를 어디서 확인할 수 있나요? | `construction_equipment_general` |
| lay-energy-0423 | 중고 발전설비를 이전해 다시 설치하려는데, 계약서에 성능과 하자 책임을 어떻게 적어야 하나요? | `construction_equipment_general` |
| lay-energy-0424 | 중고 발전설비를 이전해 다시 설치하려는데, 공사 중 자재나 설계를 바꾸면 어떤 확인이 필요한가요? | `construction_equipment_general` |
| lay-energy-0425 | 중고 발전설비를 이전해 다시 설치하려는데, 완공 때 검사 기록과 도면 등 무엇을 받아야 하나요? | `construction_equipment_general` |
| lay-energy-0426 | 오래된 건물 지붕에 무거운 태양광 설비를 올리려는데, 지붕 구조 안전을 확인할 자격과 경험이 있는 업체인지 어떻게 확인하나요? | `construction_old_roof` |
| lay-energy-0427 | 오래된 건물 지붕에 무거운 태양광 설비를 올리려는데, 지붕이 설비 무게를 견디는지와 보강 필요성을 어떤 자료로 확인하나요? | `construction_old_roof` |
| lay-energy-0428 | 오래된 건물 지붕에 무거운 태양광 설비를 올리려는데, 계약서에 구조 안전·지붕 보강·누수 책임을 어떻게 적어야 하나요? | `construction_old_roof` |
| lay-energy-0429 | 오래된 건물 지붕에 무거운 태양광 설비를 올리려는데, 검토 때와 다른 자재나 설비로 바꾸면 안전 확인을 다시 받아야 하나요? | `construction_old_roof` |
| lay-energy-0430 | 오래된 건물 지붕에 무거운 태양광 설비를 올리려는데, 완공 때 구조 검토서·보강 기록·방수 보증서 중 무엇을 받아야 하나요? | `construction_old_roof` |
| lay-energy-0431 | 태양광 공사가 끝나 인계 자료를 받으려는데, 자료를 넘겨줄 책임은 어느 업체에 있고 누락되면 누구에게 요구하나요? | `construction_handover_documents` |
| lay-energy-0432 | 태양광 공사가 끝나 인계 자료를 받으려는데, 준공도면과 실제 설치 상태가 같은지 어떻게 확인하나요? | `construction_handover_documents` |
| lay-energy-0433 | 태양광 공사가 끝나 인계 자료를 받으려는데, 검사 결과와 보완 완료 기록 중 무엇을 받아야 하나요? | `construction_handover_documents` |
| lay-energy-0434 | 태양광 공사가 끝나 인계 자료를 받으려는데, 제품 인증서·일련번호·보증서는 어떻게 정리해야 하나요? | `construction_handover_documents` |
| lay-energy-0435 | 태양광 공사가 끝나 인계 자료를 받으려는데, 운전·점검·고장 대응을 위해 꼭 받아야 할 자료는 무엇인가요? | `construction_handover_documents` |
| lay-energy-0436 | 태양광 설치 후 성능이 견적보다 낮게 나오고 있는데, 견적의 예상 발전량과 실제 값을 어떤 기준으로 비교해야 하나요? | `construction_low_performance` |
| lay-energy-0437 | 태양광 설치 후 성능이 견적보다 낮게 나오고 있는데, 날씨·그늘·고장 중 원인을 구분하려면 어떤 자료가 필요한가요? | `construction_low_performance` |
| lay-energy-0438 | 태양광 설치 후 성능이 견적보다 낮게 나오고 있는데, 설계·자재·시공 상태를 누구에게 점검받아야 하나요? | `construction_low_performance` |
| lay-energy-0439 | 태양광 설치 후 성능이 견적보다 낮게 나오고 있는데, 성능 보증과 보완 책임을 계약서에서 어떻게 확인하나요? | `construction_low_performance` |
| lay-energy-0440 | 태양광 설치 후 성능이 견적보다 낮게 나오고 있는데, 업체가 해결하지 않으면 어디에 상담이나 분쟁조정을 요청하나요? | `construction_low_performance` |

</details>

<details>
<summary>검사·안전·고장·재난 — 70개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0441 | 발전설비 공사를 마치고 사용을 시작하려는데, 어떤 검사를 언제 신청해야 하나요? | `inspection_application` |
| lay-energy-0442 | 발전설비 공사를 마치고 사용을 시작하려는데, 필요한 서류와 현장 준비사항은 무엇인가요? | `inspection_application` |
| lay-energy-0443 | 발전설비 공사를 마치고 사용을 시작하려는데, 신청부터 결과 확인까지 어떤 순서로 진행되나요? | `inspection_application` |
| lay-energy-0444 | 발전설비 공사를 마치고 사용을 시작하려는데, 보완이 필요하면 무엇을 고치고 다시 확인받아야 하나요? | `inspection_application` |
| lay-energy-0445 | 발전설비 공사를 마치고 사용을 시작하려는데, 검사 결과와 설비 자료는 어떻게 보관해야 하나요? | `inspection_application` |
| lay-energy-0446 | 내 설비가 사용 전 검사의 대상인지 설비 종류와 용량으로 어떻게 확인하나요? | `inspection_application` |
| lay-energy-0447 | 사용 전 검사를 온라인으로 신청할 때 도면·계산서·시험기록 중 무엇을 내야 하나요? | `inspection_application` |
| lay-energy-0448 | 발전설비 사용 전 검사를 신청한 뒤 현장 검사 날짜는 어떻게 정하고 변경할 수 있나요? | `inspection_application` |
| lay-energy-0449 | 발전설비 사용 전 검사에서 서류만 보완하면 되는 경우와 현장 검사를 다시 받아야 하는 경우는 어떻게 다른가요? | `inspection_application` |
| lay-energy-0450 | 발전설비 사용 전 검사 합격 확인서는 전력망 연결이나 사업 시작 절차에서 어디에 제출하나요? | `inspection_application` |
| lay-energy-0451 | 발전설비 사용 전 검사 보완 통지서에 적힌 기한 안에 무엇을 고치고 재검사를 언제 신청해야 하나요? | `inspection_application` |
| lay-energy-0452 | 발전설비 사용 전 검사 보완을 마쳤다는 것을 보여주려면 수정 도면·사진·시험기록 중 어떤 자료를 내야 하나요? | `inspection_application` |
| lay-energy-0453 | 발전설비 사용 전 검사 보완 공사를 끝낸 뒤 재검사를 신청하고 결과를 확인하기까지 어떤 순서로 진행되나요? | `inspection_application` |
| lay-energy-0454 | 발전설비 사용 전 검사의 보완 요구가 불분명하거나 동의하기 어려우면 어디에 설명이나 재검토를 요청하나요? | `inspection_application` |
| lay-energy-0455 | 발전설비 사용 전 검사의 처음 결과, 보완 내역, 재검사 결과는 무엇을 얼마나 오래 보관해야 하나요? | `inspection_application` |
| lay-energy-0456 | 태양광 설비가 태풍을 맞은 뒤 상태가 걱정되는데, 사람이 다치지 않도록 가장 먼저 어떤 안전조치를 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0457 | 태양광 설비가 태풍을 맞은 뒤 상태가 걱정되는데, 사용을 멈추거나 바로 신고해야 하는 기준은 무엇인가요? | `safety_weather_fault_incident` |
| lay-energy-0458 | 태양광 설비가 태풍을 맞은 뒤 상태가 걱정되는데, 점검이나 조치를 요청하려면 어디에 연락해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0459 | 태양광 설비가 태풍을 맞은 뒤 상태가 걱정되는데, 사업자·시공업체·안전관리자는 각각 무엇을 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0460 | 태양광 설비가 태풍을 맞은 뒤 상태가 걱정되는데, 조치 후 재가동과 기록 관리는 어떻게 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0461 | 집중호우 뒤 산지 발전소를 점검하려는데, 사람이 다치지 않도록 가장 먼저 어떤 안전조치를 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0462 | 집중호우 뒤 산지 발전소를 점검하려는데, 사용을 멈추거나 바로 신고해야 하는 기준은 무엇인가요? | `safety_weather_fault_incident` |
| lay-energy-0463 | 집중호우 뒤 산지 발전소를 점검하려는데, 점검이나 조치를 요청하려면 어디에 연락해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0464 | 집중호우 뒤 산지 발전소를 점검하려는데, 사업자·시공업체·안전관리자는 각각 무엇을 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0465 | 집중호우 뒤 산지 발전소를 점검하려는데, 조치 후 재가동과 기록 관리는 어떻게 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0466 | 패널이나 전선에서 이상한 냄새가 나는데, 사람이 다치지 않도록 가장 먼저 어떤 안전조치를 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0467 | 패널이나 전선에서 이상한 냄새가 나는데, 사용을 멈추거나 바로 신고해야 하는 기준은 무엇인가요? | `safety_weather_fault_incident` |
| lay-energy-0468 | 패널이나 전선에서 이상한 냄새가 나는데, 점검이나 조치를 요청하려면 어디에 연락해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0469 | 패널이나 전선에서 이상한 냄새가 나는데, 사업자·시공업체·안전관리자는 각각 무엇을 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0470 | 패널이나 전선에서 이상한 냄새가 나는데, 조치 후 재가동과 기록 관리는 어떻게 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0471 | 인버터가 자꾸 멈추고 경고가 뜨는데, 사람이 다치지 않도록 가장 먼저 어떤 안전조치를 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0472 | 인버터가 자꾸 멈추고 경고가 뜨는데, 사용을 멈추거나 바로 신고해야 하는 기준은 무엇인가요? | `safety_weather_fault_incident` |
| lay-energy-0473 | 인버터가 자꾸 멈추고 경고가 뜨는데, 점검이나 조치를 요청하려면 어디에 연락해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0474 | 인버터가 자꾸 멈추고 경고가 뜨는데, 사업자·시공업체·안전관리자는 각각 무엇을 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0475 | 인버터가 자꾸 멈추고 경고가 뜨는데, 조치 후 재가동과 기록 관리는 어떻게 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0476 | 발전소 주변에서 누전이 의심되는데, 사람이 다치지 않도록 가장 먼저 어떤 안전조치를 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0477 | 발전소 주변에서 누전이 의심되는데, 사용을 멈추거나 바로 신고해야 하는 기준은 무엇인가요? | `safety_weather_fault_incident` |
| lay-energy-0478 | 발전소 주변에서 누전이 의심되는데, 점검이나 조치를 요청하려면 어디에 연락해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0479 | 발전소 주변에서 누전이 의심되는데, 사업자·시공업체·안전관리자는 각각 무엇을 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0480 | 발전소 주변에서 누전이 의심되는데, 조치 후 재가동과 기록 관리는 어떻게 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0481 | 사고가 발생해 전기 공급을 즉시 끊어야 하는데, 사람이 다치지 않도록 가장 먼저 어떤 안전조치를 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0482 | 사고가 나 전기 공급을 끊어야 할 때, 일반인이 직접 전원을 끄지 말고 전문가에게 맡겨야 하는 상황은 무엇인가요? | `safety_weather_fault_incident` |
| lay-energy-0483 | 사고가 발생해 전기 공급을 즉시 끊어야 하는데, 점검이나 조치를 요청하려면 어디에 연락해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0484 | 사고가 발생해 전기 공급을 즉시 끊어야 하는데, 사업자·시공업체·안전관리자는 각각 무엇을 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0485 | 사고가 발생해 전기 공급을 즉시 끊어야 하는데, 조치 후 재가동과 기록 관리는 어떻게 해야 하나요? | `safety_weather_fault_incident` |
| lay-energy-0486 | 발전설비를 오래 비워둔 뒤 다시 가동하려는데, 접근하거나 만지지 않고 외부에서 확인할 수 있는 이상 징후는 무엇인가요? | `safety_restart_after_idle` |
| lay-energy-0487 | 발전설비를 오래 비워둔 뒤 다시 가동하려는데, 재가동하지 말고 먼저 점검받아야 하는 상태는 무엇인가요? | `safety_restart_after_idle` |
| lay-energy-0488 | 발전설비를 오래 비워둔 뒤 다시 가동하려는데, 어떤 점검이나 검사를 누구에게 요청해야 하나요? | `safety_restart_after_idle` |
| lay-energy-0489 | 발전설비를 오래 비워둔 뒤 다시 가동하려는데, 이전 점검·고장·수리 기록 중 무엇을 확인해야 하나요? | `safety_restart_after_idle` |
| lay-energy-0490 | 발전설비를 오래 비워둔 뒤 다시 가동하려는데, 전문가 점검이 끝난 뒤 누가 어떤 순서로 다시 가동해야 하나요? | `safety_restart_after_idle` |
| lay-energy-0491 | 안전관리 업무를 외부 업체에 맡기려는데, 외부 업체가 맡을 수 있는 업무 범위는 어디까지인가요? | `safety_management_outsourcing` |
| lay-energy-0492 | 안전관리 업무를 외부 업체에 맡기려는데, 업체를 정하기 전에 신고나 선임 절차가 필요한가요? | `safety_management_outsourcing` |
| lay-energy-0493 | 안전관리 업무를 외부 업체에 맡기려는데, 업체의 자격과 등록 여부는 어느 기관에서 확인하나요? | `safety_management_outsourcing` |
| lay-energy-0494 | 안전관리 업무를 외부 업체에 맡기려는데, 점검 주기·비상대응·보고 책임을 계약서에 어떻게 적어야 하나요? | `safety_management_outsourcing` |
| lay-energy-0495 | 안전관리 업무를 외부 업체에 맡기려는데, 맡긴 뒤 점검 기록과 사고 대응 책임은 누가 관리해야 하나요? | `safety_management_outsourcing` |
| lay-energy-0496 | 발전설비 점검 기록을 정리하려는데, 반드시 적어야 할 점검 항목은 무엇인가요? | `safety_inspection_records` |
| lay-energy-0497 | 발전설비 점검 기록을 정리하려는데, 기록을 얼마나 오래 보관해야 하나요? | `safety_inspection_records` |
| lay-energy-0498 | 발전설비 점검 기록을 정리하려는데, 정해진 서식과 작성 방법은 어디서 확인하나요? | `safety_inspection_records` |
| lay-energy-0499 | 발전설비 점검 기록을 정리하려는데, 종이와 전자 기록 중 어떤 방식으로 보관할 수 있나요? | `safety_inspection_records` |
| lay-energy-0500 | 발전설비 점검 기록을 정리하려는데, 기록을 고칠 때 수정 이력은 어떻게 남겨야 하나요? | `safety_inspection_records` |
| lay-energy-0501 | 발전설비 일부를 교체한 뒤 다시 검사받아야 할지 궁금한데, 어떤 부품을 교체했을 때 재검사나 변경 신고가 필요한가요? | `safety_after_component_change` |
| lay-energy-0502 | 발전설비 일부를 교체한 뒤 다시 검사받아야 할지 궁금한데, 교체 공사 전에 누구에게 확인해야 하나요? | `safety_after_component_change` |
| lay-energy-0503 | 발전설비 일부를 교체한 뒤 다시 검사받아야 할지 궁금한데, 기존 설비와 새 부품 정보를 증명할 어떤 자료가 필요한가요? | `safety_after_component_change` |
| lay-energy-0504 | 발전설비 일부를 교체한 뒤 다시 검사받아야 할지 궁금한데, 교체 후 점검과 검사 신청은 어떤 순서로 진행하나요? | `safety_after_component_change` |
| lay-energy-0505 | 발전설비 일부를 교체한 뒤 다시 검사받아야 할지 궁금한데, 검사 전 가동 가능 여부와 안전조치는 어디서 확인하나요? | `safety_after_component_change` |
| lay-energy-0506 | 발전소를 운영하던 중 주민이 설비의 안전 문제를 신고했는데, 신고 내용과 위험 상황을 어떻게 확인해야 하나요? | `safety_resident_report` |
| lay-energy-0507 | 발전소를 운영하던 중 주민이 설비의 안전 문제를 신고했는데, 신고만으로 설비 사용을 멈춰야 하는지 어떤 기준으로 판단하나요? | `safety_resident_report` |
| lay-energy-0508 | 발전소를 운영하던 중 주민이 설비의 안전 문제를 신고했는데, 현장 점검은 누구에게 요청하고 주민에게 어떻게 알려야 하나요? | `safety_resident_report` |
| lay-energy-0509 | 발전소를 운영하던 중 주민이 설비의 안전 문제를 신고했는데, 조사·보완·재가동 과정을 어떤 기록으로 남겨야 하나요? | `safety_resident_report` |
| lay-energy-0510 | 발전소를 운영하던 중 주민이 설비의 안전 문제를 신고했는데, 문제가 확인되면 시정과 후속 점검은 어떻게 진행하나요? | `safety_resident_report` |

</details>

<details>
<summary>수익·SMP·REC·정산 — 90개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0511 | 태양광으로 만든 전기를 어떤 방식으로 팔지 고민인데, 가능한 판매와 계약 방식은 어떻게 다른가요? | `electricity_sales_entry` |
| lay-energy-0512 | 태양광으로 만든 전기를 어떤 방식으로 팔지 고민인데, 누구와 계약하고 어느 기관의 절차를 거쳐야 하나요? | `electricity_sales_entry` |
| lay-energy-0513 | 태양광으로 만든 전기를 어떤 방식으로 팔지 고민인데, 거래를 시작하기 전에 어떤 등록과 확인이 필요한가요? | `electricity_sales_entry` |
| lay-energy-0514 | 태양광으로 만든 전기를 어떤 방식으로 팔지 고민인데, 발전량을 측정하고 거래하려면 어떤 계량 준비가 필요한가요? | `electricity_sales_entry` |
| lay-energy-0515 | 태양광으로 만든 전기를 어떤 방식으로 팔지 고민인데, 가격과 수수료처럼 바뀔 수 있는 정보는 어디서 확인하나요? | `electricity_sales_entry` |
| lay-energy-0516 | 기업과 직접 재생전력 계약을 맺고 싶은데, 가능한 판매와 계약 방식은 어떻게 다른가요? | `electricity_sales_entry` |
| lay-energy-0517 | 기업과 직접 재생전력 계약을 맺고 싶은데, 누구와 계약하고 어느 기관의 절차를 거쳐야 하나요? | `electricity_sales_entry` |
| lay-energy-0518 | 기업과 직접 재생전력 계약을 맺고 싶은데, 거래를 시작하기 전에 어떤 등록과 확인이 필요한가요? | `electricity_sales_entry` |
| lay-energy-0519 | 기업과 직접 재생전력 계약을 맺고 싶은데, 발전량을 측정하고 거래하려면 어떤 계량 준비가 필요한가요? | `electricity_sales_entry` |
| lay-energy-0520 | 기업과 직접 재생전력 계약을 맺고 싶은데, 가격과 수수료처럼 바뀔 수 있는 정보는 어디서 확인하나요? | `electricity_sales_entry` |
| lay-energy-0521 | 발전량은 기록되지만 신재생에너지 공급인증서(REC)가 발급되지 않고 있는데, 발급 대상과 신청 조건을 어떻게 확인하나요? | `rec_issue_timing` |
| lay-energy-0522 | 발전량은 기록되지만 신재생에너지 공급인증서(REC)가 발급되지 않고 있는데, 지금 할 수 있는 신청이나 보완 절차는 무엇인가요? | `rec_issue_timing` |
| lay-energy-0523 | 발전량은 기록되지만 신재생에너지 공급인증서(REC)가 발급되지 않고 있는데, 발전량과 설비 상태를 증명할 어떤 자료가 필요한가요? | `rec_issue_timing` |
| lay-energy-0524 | 발전량은 기록되지만 신재생에너지 공급인증서(REC)가 발급되지 않고 있는데, 신청 기한과 처리 상태는 어디서 확인하나요? | `rec_issue_timing` |
| lay-energy-0525 | 발전량은 기록되지만 신재생에너지 공급인증서(REC)가 발급되지 않고 있는데, 발급이 늦거나 기한을 넘겼다면 어디에 문의해야 하나요? | `rec_issue_timing` |
| lay-energy-0526 | REC 신청 기한을 넘겼다면 놓친 기간의 발전량도 나중에 발급받을 수 있나요? | `rec_issue_timing` |
| lay-energy-0527 | 신재생에너지 공급인증서(REC) 신청 시기를 놓친 것 같은데, 지금 할 수 있는 신청이나 보완 절차는 무엇인가요? | `rec_issue_timing` |
| lay-energy-0528 | 신재생에너지 공급인증서(REC) 신청 시기를 놓친 것 같은데, 발전량과 설비 상태를 증명할 어떤 자료가 필요한가요? | `rec_issue_timing` |
| lay-energy-0529 | 어느 날짜를 신청 마감으로 보는지와 제가 실제로 기한을 넘겼는지 어떻게 확인하나요? | `rec_issue_timing` |
| lay-energy-0530 | REC 신청 기한을 놓친 경우 소급 신청이나 이의 제기가 가능한지 어디에 문의하나요? | `rec_issue_timing` |
| lay-energy-0531 | 여러 발전소의 REC를 한 계정에서 관리할 수 있나요? | `rec_multiple_plants_account` |
| lay-energy-0532 | 여러 발전소의 신재생에너지 공급인증서(REC)를 한 계정에서 관리하려는데, 발전소를 계정에 추가하거나 대표자를 바꾸려면 어떻게 하나요? | `rec_multiple_plants_account` |
| lay-energy-0533 | 여러 발전소의 신재생에너지 공급인증서(REC)를 한 계정에서 관리하려는데, 발전소별 발전량과 REC 소유 내역을 어떻게 구분하나요? | `rec_multiple_plants_account` |
| lay-energy-0534 | 여러 발전소의 신재생에너지 공급인증서(REC)를 한 계정에서 관리하려는데, 발전소별 신청·발급 상태를 따로 확인할 수 있나요? | `rec_multiple_plants_account` |
| lay-energy-0535 | 여러 발전소의 신재생에너지 공급인증서(REC)를 한 계정에서 관리하려는데, 계정 통합이나 접속 문제가 생기면 어디에 문의해야 하나요? | `rec_multiple_plants_account` |
| lay-energy-0536 | 발전소를 인수한 뒤 기존 REC 발급과 거래를 이어가려는데, 이전 사업자의 발급과 거래를 그대로 이어갈 수 있나요? | `rec_after_acquisition` |
| lay-energy-0537 | 발전소를 인수한 뒤 기존 REC 발급과 거래를 이어가려는데, 사업자와 계정 정보를 바꾸려면 어떤 절차가 필요한가요? | `rec_after_acquisition` |
| lay-energy-0538 | 발전소를 인수한 뒤 기존 REC 발급과 거래를 이어가려는데, 양수도와 설비 소유를 증명할 어떤 서류가 필요한가요? | `rec_after_acquisition` |
| lay-energy-0539 | 발전소를 인수한 뒤 기존 REC 발급과 거래를 이어가려는데, 인수 전후 REC와 거래대금은 어떻게 구분하나요? | `rec_after_acquisition` |
| lay-energy-0540 | 발전소를 인수한 뒤 기존 REC 발급과 거래를 이어가려는데, 승계 처리가 되지 않으면 어디에 문의해야 하나요? | `rec_after_acquisition` |
| lay-energy-0541 | 모듈이나 인버터를 바꾼 뒤 기존 REC 발급을 이어가려는데, 설비 교체가 기존 인증과 발급량에 어떤 영향을 주나요? | `rec_after_equipment_change` |
| lay-energy-0542 | 모듈이나 인버터를 바꾼 뒤 기존 REC 발급을 이어가려는데, 교체 전후 어느 기관에 무엇을 알려야 하나요? | `rec_after_equipment_change` |
| lay-energy-0543 | 모듈이나 인버터를 바꾼 뒤 기존 REC 발급을 이어가려는데, 새 제품 정보와 공사 내역을 증명할 어떤 자료가 필요한가요? | `rec_after_equipment_change` |
| lay-energy-0544 | 모듈이나 인버터를 바꾼 뒤 기존 REC 발급을 이어가려는데, 설비 확인이나 검사를 다시 받아야 하나요? | `rec_after_equipment_change` |
| lay-energy-0545 | 모듈이나 인버터를 바꾼 뒤 기존 REC 발급을 이어가려는데, 변경 처리 뒤 REC 발급 재개 시점은 어떻게 확인하나요? | `rec_after_equipment_change` |
| lay-energy-0546 | 고정가격 계약과 시장가격에 따라 파는 방식 중 무엇이 나은지 궁금한데, 가격 변동·계약기간·위험은 어떻게 비교해야 하나요? | `sale_contract_choice_change` |
| lay-energy-0547 | 고정가격 계약과 시장가격 판매 방식의 최소 계약기간과 중도해지 조건은 어떻게 비교하나요? | `sale_contract_choice_change` |
| lay-energy-0548 | 고정가격 계약과 시장가격 판매 방식을 선택할 수 있는 모집·계약 시점은 각각 언제인가요? | `sale_contract_choice_change` |
| lay-energy-0549 | 고정가격 계약과 시장가격 판매 방식 중 원하는 방식을 선택하려면 어느 기관이나 계약 상대에게 무엇을 신청하나요? | `sale_contract_choice_change` |
| lay-energy-0550 | 고정가격 계약과 시장가격에 따라 파는 방식 중 무엇이 나은지 궁금한데, 최신 시장가격과 계약 조건은 어디서 확인하나요? | `sale_contract_choice_change` |
| lay-energy-0551 | 시장가격이 크게 바뀌어 전기 판매 계약을 바꾸고 싶은데, 가격 변동·계약기간·위험은 어떻게 비교해야 하나요? | `sale_contract_choice_change` |
| lay-energy-0552 | 시장가격이 크게 바뀌어 전기 판매 계약을 바꾸고 싶은데, 현재 계약의 변경·해지 조건을 어디서 확인하나요? | `sale_contract_choice_change` |
| lay-energy-0553 | 시장가격이 크게 바뀌어 전기 판매 계약을 바꾸고 싶은데, 계약 방식을 고르거나 바꿀 수 있는 시점은 언제인가요? | `sale_contract_choice_change` |
| lay-energy-0554 | 시장가격이 크게 바뀌어 전기 판매 계약을 바꾸고 싶은데, 새 계약으로 바꾸려면 누구에게 어떤 신청을 해야 하나요? | `sale_contract_choice_change` |
| lay-energy-0555 | 시장가격이 크게 바뀌어 전기 판매 계약을 바꾸고 싶은데, 최신 시장가격과 계약 조건은 어디서 확인하나요? | `sale_contract_choice_change` |
| lay-energy-0556 | 계약한 설비와 실제 설치한 설비가 달라졌는데, 전기 판매대금이나 REC 정산액이 달라질 수 있나요? | `sale_contract_equipment_mismatch` |
| lay-energy-0557 | 계약한 설비와 실제 설치한 설비가 달라졌는데, 계약 내용과 실제 설비의 차이를 어떤 자료로 확인하나요? | `sale_contract_equipment_mismatch` |
| lay-energy-0558 | 계약한 설비와 실제 설치한 설비가 달라졌는데, 계약과 인증 정보 중 무엇을 먼저 고쳐야 하나요? | `sale_contract_equipment_mismatch` |
| lay-energy-0559 | 계약한 설비와 실제 설치한 설비가 달라졌는데, 설비 확인이나 검사를 다시 받아야 하나요? | `sale_contract_equipment_mismatch` |
| lay-energy-0560 | 계약한 설비와 실제 설치한 설비가 달라졌는데, 변경 사실과 새 정산 기준은 어디서 확인하나요? | `sale_contract_equipment_mismatch` |
| lay-energy-0561 | 예상보다 전기 판매 정산금이 적게 들어왔는데, 발전량·계약가격·공제액을 어떤 자료와 대조해야 하나요? | `sale_settlement_error` |
| lay-energy-0562 | 예상보다 전기 판매 정산금이 적게 들어왔는데, 계량값이 정확한지 누구에게 확인을 요청해야 하나요? | `sale_settlement_error` |
| lay-energy-0563 | 예상보다 전기 판매 정산금이 적게 들어왔는데, 오류 기간의 발전량과 정산액은 어떻게 다시 계산하나요? | `sale_settlement_error` |
| lay-energy-0564 | 예상보다 전기 판매 정산금이 적게 들어왔는데, 정산 결과에 이의가 있으면 어떤 절차로 신청하나요? | `sale_settlement_error` |
| lay-energy-0565 | 예상보다 전기 판매 정산금이 적게 들어왔는데, 수정된 계량값과 정산 결과는 어디서 확인하나요? | `sale_settlement_error` |
| lay-energy-0566 | 현장 계량기 표시값, 원격 검침값, 정산서의 발전량을 어떻게 대조하나요? | `sale_settlement_error` |
| lay-energy-0567 | 발전량 계량값에 오류가 있는 것 같은데, 계량값이 정확한지 누구에게 확인을 요청해야 하나요? | `sale_settlement_error` |
| lay-energy-0568 | 발전량 계량값에 오류가 있는 것 같은데, 오류 기간의 발전량과 정산액은 어떻게 다시 계산하나요? | `sale_settlement_error` |
| lay-energy-0569 | 계량기 검사 결과나 정정된 발전량에 이의가 있으면 어떤 절차로 다시 확인받나요? | `sale_settlement_error` |
| lay-energy-0570 | 발전량 계량값에 오류가 있는 것 같은데, 수정된 계량값과 정산 결과는 어디서 확인하나요? | `sale_settlement_error` |
| lay-energy-0571 | 전기 판매대금과 REC 수익이 언제 들어오는지 궁금한데, 두 수익은 각각 언제 어떤 주기로 지급되나요? | `sale_payment_schedule` |
| lay-energy-0572 | 전기 판매대금과 REC 수익이 언제 들어오는지 궁금한데, 지급일이 다른 이유와 계약상 조건은 무엇인가요? | `sale_payment_schedule` |
| lay-energy-0573 | 전기 판매대금과 REC 수익이 언제 들어오는지 궁금한데, 계량 확인이나 REC 발급이 늦으면 지급도 늦어지나요? | `sale_payment_schedule` |
| lay-energy-0574 | 전기 판매대금과 REC 수익이 언제 들어오는지 궁금한데, 지급 예정일이 지났는데 입금되지 않으면 어디에 문의하나요? | `sale_payment_schedule` |
| lay-energy-0575 | 전기 판매대금과 REC 수익이 언제 들어오는지 궁금한데, 최신 지급·정산 일정은 어디서 확인하나요? | `sale_payment_schedule` |
| lay-energy-0576 | 고정가격 계약 후 발전소 준공이 늦어지고 있는데, 준공 지연이 계약기한과 위약 책임에 어떤 영향을 주나요? | `fixed_contract_completion_delay` |
| lay-energy-0577 | 고정가격 계약 후 발전소 준공이 늦어지고 있는데, 일정 변경을 어느 기관과 계약 상대에게 알려야 하나요? | `fixed_contract_completion_delay` |
| lay-energy-0578 | 고정가격 계약 후 발전소 준공이 늦어지고 있는데, 준공기한을 연장할 수 있는 조건과 절차는 무엇인가요? | `fixed_contract_completion_delay` |
| lay-energy-0579 | 고정가격 계약 후 발전소 준공이 늦어지고 있는데, 지연 사유를 증명하려면 어떤 자료가 필요한가요? | `fixed_contract_completion_delay` |
| lay-energy-0580 | 고정가격 계약 후 발전소 준공이 늦어지고 있는데, 현재 준공기한과 연장 안내는 어디서 확인하나요? | `fixed_contract_completion_delay` |
| lay-energy-0581 | REC 거래 수수료와 세금 처리가 궁금한데, 판매대금에서 거래수수료와 세금이 각각 어떻게 계산되나요? | `rec_fee_tax` |
| lay-energy-0582 | REC 거래 수수료와 세금 처리가 궁금한데, 거래 방식에 따라 세금계산서 처리가 달라지나요? | `rec_fee_tax` |
| lay-energy-0583 | REC 거래 수수료와 세금 처리가 궁금한데, 개인·개인사업자·법인은 수익을 어떻게 신고하나요? | `rec_fee_tax` |
| lay-energy-0584 | REC 거래 수수료와 세금 처리가 궁금한데, 공제 내역이 예상과 다르면 어느 기관에 문의해야 하나요? | `rec_fee_tax` |
| lay-energy-0585 | REC 거래 수수료와 세금 처리가 궁금한데, 현재 수수료율과 세금 안내는 어디서 확인하나요? | `rec_fee_tax` |
| lay-energy-0586 | 태양광으로 만든 전기 중 직접 쓴 양과 판매한 양을 구분하려면 어떤 계량값을 봐야 하나요? | `self_use_sale_settlement` |
| lay-energy-0587 | 태양광으로 만든 전기 중 집이나 건물에서 직접 쓴 양은 전기요금에 어떻게 반영되나요? | `self_use_sale_settlement` |
| lay-energy-0588 | 태양광으로 만든 전기 중 남아서 판매한 전기의 대금은 누구와 어떻게 정산하나요? | `self_use_sale_settlement` |
| lay-energy-0589 | 직접 쓴 양과 판매한 양이 계량 기록과 맞지 않으면 어디에 확인을 요청해야 하나요? | `self_use_sale_settlement` |
| lay-energy-0590 | 월별 발전량·직접 사용량·판매량 기록은 어떻게 보관해야 하나요? | `self_use_sale_settlement` |
| lay-energy-0591 | 발전소 두 곳의 수익을 같은 기준으로 비교하고 싶은데, 발전량·계약가격·REC 수량 중 어떤 값을 모아야 하나요? | `revenue_comparison_validation` |
| lay-energy-0592 | 발전소 두 곳의 수익을 같은 기준으로 비교하고 싶은데, 설비 용량과 운영기간이 다르면 어떻게 맞춰 비교하나요? | `revenue_comparison_validation` |
| lay-energy-0593 | 발전소 두 곳의 수익을 같은 기준으로 비교하고 싶은데, 공사비·운영비·수수료를 수익에서 어떻게 반영하나요? | `revenue_comparison_validation` |
| lay-energy-0594 | 발전소 두 곳의 수익을 같은 기준으로 비교하고 싶은데, 각 계산값은 어느 공식 자료에서 확인해야 하나요? | `revenue_comparison_validation` |
| lay-energy-0595 | 발전소 두 곳의 수익을 같은 기준으로 비교하고 싶은데, 계산 결과와 실제 정산액이 다르면 어디에 문의해야 하나요? | `revenue_comparison_validation` |
| lay-energy-0596 | 태양광 수익 계산을 믿을 수 있는 자료로 확인하고 싶은데, 발전량·계약가격·REC 수량 중 어떤 값을 모아야 하나요? | `revenue_comparison_validation` |
| lay-energy-0597 | 예상 발전량, 손실률, 가동 중단 시간을 계산에 넣을 때 믿을 만한 수치는 어디서 구하나요? | `revenue_comparison_validation` |
| lay-energy-0598 | 태양광 수익 계산을 믿을 수 있는 자료로 확인하고 싶은데, 공사비·운영비·수수료를 수익에서 어떻게 반영하나요? | `revenue_comparison_validation` |
| lay-energy-0599 | 태양광 수익 계산을 믿을 수 있는 자료로 확인하고 싶은데, 각 계산값은 어느 공식 자료에서 확인해야 하나요? | `revenue_comparison_validation` |
| lay-energy-0600 | 태양광 수익 계산을 믿을 수 있는 자료로 확인하고 싶은데, 계산 결과와 실제 정산액이 다르면 어디에 문의해야 하나요? | `revenue_comparison_validation` |

</details>

<details>
<summary>보조금·융자·지원 — 70개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0601 | 태양광 설치비 지원을 받을 수 있는지 알아보는데, 지원 대상인지 어떤 조건으로 판단하나요? | `subsidy_finance_application` |
| lay-energy-0602 | 태양광 설치비 지원을 받을 수 있는지 알아보는데, 언제 신청하고 계약과 공사는 어느 시점에 해야 하나요? | `subsidy_finance_application` |
| lay-energy-0603 | 태양광 설치비 지원을 받을 수 있는지 알아보는데, 신청자·설치 장소·사업계획을 보여 줄 어떤 서류가 필요한가요? | `subsidy_finance_application` |
| lay-energy-0604 | 태양광 설치비 지원을 받을 수 있는지 알아보는데, 다른 보조금이나 대출과 함께 이용할 수 있나요? | `subsidy_finance_application` |
| lay-energy-0605 | 태양광 설치비 지원을 받을 수 있는지 알아보는데, 올해 예산과 세부 조건은 어디서 최신 정보를 확인하나요? | `subsidy_finance_application` |
| lay-energy-0606 | 주택에 재생에너지 설비를 설치하면서 보조금을 신청하려는데, 지원 대상인지 어떤 조건으로 판단하나요? | `subsidy_finance_application` |
| lay-energy-0607 | 주택에 재생에너지 설비를 설치하면서 보조금을 신청하려는데, 언제 신청하고 계약과 공사는 어느 시점에 해야 하나요? | `subsidy_finance_application` |
| lay-energy-0608 | 주택에 재생에너지 설비를 설치하면서 보조금을 신청하려는데, 신청자·설치 장소·사업계획을 보여 줄 어떤 서류가 필요한가요? | `subsidy_finance_application` |
| lay-energy-0609 | 주택에 재생에너지 설비를 설치하면서 보조금을 신청하려는데, 다른 보조금이나 대출과 함께 이용할 수 있나요? | `subsidy_finance_application` |
| lay-energy-0610 | 주택에 재생에너지 설비를 설치하면서 보조금을 신청하려는데, 올해 예산과 세부 조건은 어디서 최신 정보를 확인하나요? | `subsidy_finance_application` |
| lay-energy-0611 | 공장 에너지 절감 설비에 정책자금을 쓰고 싶은데, 지원 대상인지 어떤 조건으로 판단하나요? | `subsidy_finance_application` |
| lay-energy-0612 | 공장 에너지 절감 설비에 정책자금을 쓰고 싶은데, 언제 신청하고 계약과 공사는 어느 시점에 해야 하나요? | `subsidy_finance_application` |
| lay-energy-0613 | 공장 에너지 절감 설비에 정책자금을 쓰고 싶은데, 신청자·설치 장소·사업계획을 보여 줄 어떤 서류가 필요한가요? | `subsidy_finance_application` |
| lay-energy-0614 | 공장 에너지 절감 설비에 정책자금을 쓰고 싶은데, 다른 보조금이나 대출과 함께 이용할 수 있나요? | `subsidy_finance_application` |
| lay-energy-0615 | 공장 에너지 절감 설비에 정책자금을 쓰고 싶은데, 올해 예산과 세부 조건은 어디서 최신 정보를 확인하나요? | `subsidy_finance_application` |
| lay-energy-0616 | 담보가 부족해도 발전사업의 예상 수익이나 보증을 이용해 신청할 수 있는 정책자금 대출이 있나요? | `subsidy_finance_application` |
| lay-energy-0617 | 담보가 부족한 상태에서 발전사업 정책자금 대출을 알아보는데, 언제 신청하고 계약과 공사는 어느 시점에 해야 하나요? | `subsidy_finance_application` |
| lay-energy-0618 | 발전사업 정책자금 대출에서 담보 가치, 자기자금, 발전소 예상 수익을 증명하려면 어떤 자료가 필요한가요? | `subsidy_finance_application` |
| lay-energy-0619 | 담보가 부족한 상태에서 발전사업 정책자금 대출을 알아보는데, 다른 보조금이나 대출과 함께 이용할 수 있나요? | `subsidy_finance_application` |
| lay-energy-0620 | 담보가 부족한 상태에서 발전사업 정책자금 대출을 알아보는데, 올해 예산과 세부 조건은 어디서 최신 정보를 확인하나요? | `subsidy_finance_application` |
| lay-energy-0621 | 임차한 건물에도 설치 지원을 받을 수 있는지 궁금한데, 지원 대상인지 어떤 조건으로 판단하나요? | `subsidy_finance_application` |
| lay-energy-0622 | 임차한 건물에도 설치 지원을 받을 수 있는지 궁금한데, 언제 신청하고 계약과 공사는 어느 시점에 해야 하나요? | `subsidy_finance_application` |
| lay-energy-0623 | 임차한 건물의 에너지 설비 설치 지원을 신청할 때 임대차계약서와 건물주의 설치 동의서 등 어떤 서류가 필요한가요? | `subsidy_finance_application` |
| lay-energy-0624 | 임차한 건물에도 설치 지원을 받을 수 있는지 궁금한데, 다른 보조금이나 대출과 함께 이용할 수 있나요? | `subsidy_finance_application` |
| lay-energy-0625 | 임차한 건물에도 설치 지원을 받을 수 있는지 궁금한데, 올해 예산과 세부 조건은 어디서 최신 정보를 확인하나요? | `subsidy_finance_application` |
| lay-energy-0626 | 소규모 사업장의 에너지 설비 설치 지원 제도를 찾고 있는데, 지원 대상인지 어떤 조건으로 판단하나요? | `subsidy_finance_application` |
| lay-energy-0627 | 소규모 사업장의 에너지 설비 설치 지원 제도를 찾고 있는데, 언제 신청하고 계약과 공사는 어느 시점에 해야 하나요? | `subsidy_finance_application` |
| lay-energy-0628 | 소규모 사업장의 에너지 설비 설치 지원 제도를 찾고 있는데, 신청자·설치 장소·사업계획을 보여 줄 어떤 서류가 필요한가요? | `subsidy_finance_application` |
| lay-energy-0629 | 소규모 사업장의 에너지 설비 설치 지원 제도를 찾고 있는데, 다른 보조금이나 대출과 함께 이용할 수 있나요? | `subsidy_finance_application` |
| lay-energy-0630 | 소규모 사업장의 에너지 설비 설치 지원 제도를 찾고 있는데, 올해 예산과 세부 조건은 어디서 최신 정보를 확인하나요? | `subsidy_finance_application` |
| lay-energy-0631 | 보조금과 금융지원을 함께 받을 수 있는지 궁금한데, 같은 설비에 두 지원을 함께 이용할 수 있나요? | `subsidy_combination` |
| lay-energy-0632 | 보조금과 금융지원을 함께 받을 수 있는지 궁금한데, 중복 지원 제한과 우선순위는 어디서 확인하나요? | `subsidy_combination` |
| lay-energy-0633 | 보조금과 금융지원을 함께 받을 수 있는지 궁금한데, 두 제도를 신청한다면 어떤 순서로 진행해야 하나요? | `subsidy_combination` |
| lay-energy-0634 | 보조금과 금융지원을 함께 받을 수 있는지 궁금한데, 이미 받은 지원과 대출을 어떤 자료로 밝혀야 하나요? | `subsidy_combination` |
| lay-energy-0635 | 보조금과 금융지원을 함께 받을 수 있는지 궁금한데, 올해 함께 이용할 수 있는 제도 조합은 어디서 확인하나요? | `subsidy_combination` |
| lay-energy-0636 | 지원사업 공고가 나오기 전에 설치 계약을 맺으려는데, 공고 전에 계약하면 지원 대상에서 빠질 수 있나요? | `subsidy_contract_before_notice` |
| lay-energy-0637 | 지원사업 공고가 나오기 전에 설치 계약을 맺으려는데, 계약·신청·공사를 어떤 순서로 해야 하나요? | `subsidy_contract_before_notice` |
| lay-energy-0638 | 지원사업 공고가 나오기 전에 설치 계약을 맺으려는데, 지원받지 못할 때를 대비해 계약서에 무엇을 적어야 하나요? | `subsidy_contract_before_notice` |
| lay-energy-0639 | 지원사업 공고가 나오기 전에 설치 계약을 맺으려는데, 계약금 지급 시점을 어떻게 정하는 것이 안전한가요? | `subsidy_contract_before_notice` |
| lay-energy-0640 | 지원사업 공고가 나오기 전에 설치 계약을 맺으려는데, 공고 예정과 사전 준비 안내는 어디서 확인하나요? | `subsidy_contract_before_notice` |
| lay-energy-0641 | 지원사업 예산이 소진됐다는 안내를 받았는데, 접수가 끝난 것인지 대기 신청이 가능한지 어디서 확인하나요? | `subsidy_budget_exhausted` |
| lay-energy-0642 | 지원사업 예산이 소진됐다는 안내를 받았는데, 추가 모집이나 다음 공고 일정은 어디서 확인하나요? | `subsidy_budget_exhausted` |
| lay-energy-0643 | 지원사업 예산이 소진됐다는 안내를 받았는데, 이미 낸 신청은 유지되는지 다시 내야 하는지 어떻게 확인하나요? | `subsidy_budget_exhausted` |
| lay-energy-0644 | 지원사업 예산이 소진됐다는 안내를 받았는데, 같은 목적의 다른 지원이나 융자를 찾아볼 수 있나요? | `subsidy_budget_exhausted` |
| lay-energy-0645 | 지원사업 예산이 소진됐다는 안내를 받았는데, 이미 맺은 설치 계약과 공사 일정은 어떻게 조정해야 하나요? | `subsidy_budget_exhausted` |
| lay-energy-0646 | 지난해와 올해 지원 조건이 달라졌는데, 제 신청에는 어느 연도의 조건이 적용되나요? | `subsidy_terms_changed` |
| lay-energy-0647 | 지난해와 올해 지원 조건이 달라졌는데, 대상·지원액·설비 기준 중 무엇이 바뀌었나요? | `subsidy_terms_changed` |
| lay-energy-0648 | 지난해와 올해 지원 조건이 달라졌는데, 지난해 접수한 신청에 올해 기준이 적용될 수 있나요? | `subsidy_terms_changed` |
| lay-energy-0649 | 지난해와 올해 지원 조건이 달라졌는데, 바뀐 조건 때문에 추가로 내야 할 자료가 있나요? | `subsidy_terms_changed` |
| lay-energy-0650 | 지난해와 올해 지원 조건이 달라졌는데, 변경된 조건의 공식 공고는 어디서 확인하나요? | `subsidy_terms_changed` |
| lay-energy-0651 | 설비를 이미 설치한 뒤 지원금을 신청하려는데, 설치가 끝난 뒤에도 신청할 수 있는 지원이 있나요? | `subsidy_after_installation` |
| lay-energy-0652 | 설비를 이미 설치한 뒤 지원금을 신청하려는데, 계약·공사 전에 신청했어야 하는 제도인지 어떻게 확인하나요? | `subsidy_after_installation` |
| lay-energy-0653 | 설비를 이미 설치한 뒤 지원금을 신청하려는데, 설치일·비용·제품 정보를 증명할 어떤 자료가 필요한가요? | `subsidy_after_installation` |
| lay-energy-0654 | 설비를 이미 설치한 뒤 지원금을 신청하려는데, 완공 검사나 설비 확인을 새로 받아야 하나요? | `subsidy_after_installation` |
| lay-energy-0655 | 설비를 이미 설치한 뒤 지원금을 신청하려는데, 신청할 수 없다면 다른 지원이나 세제 안내는 어디서 확인하나요? | `subsidy_after_installation` |
| lay-energy-0656 | 지원받은 설비를 중간에 팔거나 철거하려는데, 현재 지원·대출 조건에서 가능한 처리인지 어떻게 확인하나요? | `subsidy_finance_change` |
| lay-energy-0657 | 지원받은 설비를 중간에 팔거나 철거하려는데, 변경 전에 어느 기관과 금융회사에 알려야 하나요? | `subsidy_finance_change` |
| lay-energy-0658 | 지원받은 설비를 중간에 팔거나 철거하려는데, 지원금 반환이나 대출 상환 의무가 생기는지 어떻게 확인하나요? | `subsidy_finance_change` |
| lay-energy-0659 | 지원받은 설비를 중간에 팔거나 철거하려는데, 업체나 금융회사와 맺은 계약에서 무엇을 다시 확인해야 하나요? | `subsidy_finance_change` |
| lay-energy-0660 | 지원받은 설비를 중간에 팔거나 철거하려는데, 변경 승인이 필요한지와 처리 결과는 어디서 확인하나요? | `subsidy_finance_change` |
| lay-energy-0661 | 대출 상환 전에 사업자를 바꾸려는데, 현재 지원·대출 조건에서 가능한 처리인지 어떻게 확인하나요? | `subsidy_finance_change` |
| lay-energy-0662 | 대출 상환 전에 사업자를 바꾸려는데, 변경 전에 어느 기관과 금융회사에 알려야 하나요? | `subsidy_finance_change` |
| lay-energy-0663 | 새 사업자가 남은 대출을 승계할 수 있는지와 기존 사업자에게 조기상환 의무가 생기는지 어떻게 확인하나요? | `subsidy_finance_change` |
| lay-energy-0664 | 대출계약에서 채무자 변경·담보 유지·조기상환과 관련된 어떤 조항을 확인해야 하나요? | `subsidy_finance_change` |
| lay-energy-0665 | 대출 상환 전에 사업자를 바꾸려는데, 변경 승인이 필요한지와 처리 결과는 어디서 확인하나요? | `subsidy_finance_change` |
| lay-energy-0666 | 지원사업 참여업체가 예상하지 못한 추가 비용을 요구하는데, 추가 비용이 지원사업 기준이나 계약에 맞는지 어디서 확인하나요? | `subsidy_vendor_extra_charge` |
| lay-energy-0667 | 지원사업 참여업체가 예상하지 못한 추가 비용을 요구하는데, 업체에 어떤 견적·증빙·비용 산출 자료를 요구해야 하나요? | `subsidy_vendor_extra_charge` |
| lay-energy-0668 | 지원사업 참여업체가 예상하지 못한 추가 비용을 요구하는데, 확인 전까지 추가 비용 지급을 미룰 수 있는지 어떻게 판단하나요? | `subsidy_vendor_extra_charge` |
| lay-energy-0669 | 지원사업 참여업체가 예상하지 못한 추가 비용을 요구하는데, 계약서의 추가공사·환불·해지 조건을 어떻게 확인하나요? | `subsidy_vendor_extra_charge` |
| lay-energy-0670 | 지원사업 참여업체가 예상하지 못한 추가 비용을 요구하는데, 업체와 해결되지 않으면 어디에 상담이나 분쟁조정을 요청하나요? | `subsidy_vendor_extra_charge` |

</details>

<details>
<summary>전기요금·계약전력·생활민원 — 70개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0671 | 본인 소유 가게를 새로 열어 전기를 신청하려는데, 어디에 신청하고 어떤 순서로 처리하나요? | `electricity_new_service_application` |
| lay-energy-0672 | 본인 소유 가게를 새로 열어 전기를 신청하려는데, 사용 목적과 설비에 맞는 계약 종류와 용량을 어떻게 정하나요? | `electricity_new_service_application` |
| lay-energy-0673 | 본인 소유 가게에 전기를 신청할 때 소유 관계와 신분·사업자 정보를 확인할 어떤 서류가 필요한가요? | `electricity_new_service_application` |
| lay-energy-0674 | 본인 소유 가게를 새로 열어 전기를 신청하려는데, 공사비·보증금·기본요금은 어디서 확인하나요? | `electricity_new_service_application` |
| lay-energy-0675 | 본인 소유 가게를 새로 열어 전기를 신청하려는데, 원하는 날짜부터 전기를 쓰려면 언제까지 신청해야 하나요? | `electricity_new_service_application` |
| lay-energy-0676 | 건물주가 아닌 임차인 이름으로 전기를 신청하려는데, 어디에 신청하고 어떤 순서로 처리하나요? | `electricity_new_service_application` |
| lay-energy-0677 | 건물주가 아닌 임차인 이름으로 전기를 신청하려는데, 사용 목적과 설비에 맞는 계약 종류와 용량을 어떻게 정하나요? | `electricity_new_service_application` |
| lay-energy-0678 | 건물주가 아닌 임차인 이름으로 전기를 신청하려는데, 소유자 동의와 신분·사업 관련 어떤 서류가 필요한가요? | `electricity_new_service_application` |
| lay-energy-0679 | 건물주가 아닌 임차인 이름으로 전기를 신청하려는데, 공사비·보증금·기본요금은 어디서 확인하나요? | `electricity_new_service_application` |
| lay-energy-0680 | 건물주가 아닌 임차인 이름으로 전기를 신청하려는데, 원하는 날짜부터 전기를 쓰려면 언제까지 신청해야 하나요? | `electricity_new_service_application` |
| lay-energy-0681 | 공장 설비가 늘어 계약전력을 높이려는데, 최근 사용량과 새 설비를 기준으로 적정 용량을 어떻게 정하나요? | `electricity_contract_capacity_change` |
| lay-energy-0682 | 공장 설비가 늘어 계약전력을 높이려는데, 변경은 어디에 언제 신청해야 하나요? | `electricity_contract_capacity_change` |
| lay-energy-0683 | 공장 설비가 늘어 계약전력을 높이려는데, 설비 용량과 사용계획을 보여 줄 어떤 자료가 필요한가요? | `electricity_contract_capacity_change` |
| lay-energy-0684 | 공장 설비가 늘어 계약전력을 높이려는데, 변경 후 기본요금과 초과 사용 위험은 어떻게 달라지나요? | `electricity_contract_capacity_change` |
| lay-energy-0685 | 공장 설비가 늘어 계약전력을 높이려는데, 새 계약전력은 언제부터 적용되고 다시 바꿀 수 있나요? | `electricity_contract_capacity_change` |
| lay-energy-0686 | 최근 사용량과 최대 사용전력을 기준으로 적정 계약전력을 어떻게 정하나요? | `electricity_contract_capacity_change` |
| lay-energy-0687 | 사용량이 줄어 계약전력을 낮추고 싶은데, 변경은 어디에 언제 신청해야 하나요? | `electricity_contract_capacity_change` |
| lay-energy-0688 | 사용량이 줄어 계약전력을 낮추고 싶은데, 설비 용량과 사용계획을 보여 줄 어떤 자료가 필요한가요? | `electricity_contract_capacity_change` |
| lay-energy-0689 | 사용량이 줄어 계약전력을 낮추고 싶은데, 변경 후 기본요금과 초과 사용 위험은 어떻게 달라지나요? | `electricity_contract_capacity_change` |
| lay-energy-0690 | 사용량이 줄어 계약전력을 낮추고 싶은데, 새 계약전력은 언제부터 적용되고 다시 바꿀 수 있나요? | `electricity_contract_capacity_change` |
| lay-energy-0691 | 이사를 앞두고 전기 명의를 바꾸려는데, 이사 전후 언제 명의 변경을 신청해야 하나요? | `electricity_name_change` |
| lay-energy-0692 | 이사를 앞두고 전기 명의를 바꾸려는데, 어디에 어떤 방법으로 신청할 수 있나요? | `electricity_name_change` |
| lay-energy-0693 | 이사를 앞두고 전기 명의를 바꾸려는데, 이전 사용자와 새 사용자, 주소를 확인할 어떤 서류가 필요한가요? | `electricity_name_change` |
| lay-energy-0694 | 이사를 앞두고 전기 명의를 바꾸려는데, 이사 전후 사용분은 어떻게 나눠 정산하나요? | `electricity_name_change` |
| lay-energy-0695 | 이사를 앞두고 전기 명의를 바꾸려는데, 새 명의가 언제부터 적용됐는지 어떻게 확인하나요? | `electricity_name_change` |
| lay-energy-0696 | 태양광 설치 후에도 전기요금이 생각보다 줄지 않아 이유가 궁금한데, 태양광 발전량이 정상인지 어떤 계량값으로 확인하나요? | `solar_bill_not_reduced` |
| lay-energy-0697 | 태양광 설치 후에도 전기요금이 생각보다 줄지 않아 이유가 궁금한데, 만든 전기 중 집이나 건물에서 직접 쓴 양은 어떻게 확인하나요? | `solar_bill_not_reduced` |
| lay-energy-0698 | 태양광 설치 후에도 전기요금이 생각보다 줄지 않아 이유가 궁금한데, 현재 요금제와 계약 방식이 절감액에 어떤 영향을 주나요? | `solar_bill_not_reduced` |
| lay-energy-0699 | 태양광 설치 후에도 전기요금이 생각보다 줄지 않아 이유가 궁금한데, 설치 전후 사용량과 요금을 어떤 기간으로 비교해야 하나요? | `solar_bill_not_reduced` |
| lay-energy-0700 | 태양광 설치 후에도 전기요금이 생각보다 줄지 않아 이유가 궁금한데, 발전량과 요금 반영이 맞지 않으면 어디에 문의해야 하나요? | `solar_bill_not_reduced` |
| lay-energy-0701 | 계량기 고장으로 사용량이 이상하게 나온 것 같은데, 평소 사용량과 계량기 표시 중 무엇을 기록해야 하나요? | `electricity_meter_fault` |
| lay-energy-0702 | 계량기 고장으로 사용량이 이상하게 나온 것 같은데, 계량기 고장인지 사용 방식의 변화인지 어떻게 구분하나요? | `electricity_meter_fault` |
| lay-energy-0703 | 계량기 고장으로 사용량이 이상하게 나온 것 같은데, 점검과 교체는 어디에 신청해야 하나요? | `electricity_meter_fault` |
| lay-energy-0704 | 계량기에서 타는 냄새나 열이 나면 직접 만지지 않고 어디에 긴급 신고해야 하나요? | `electricity_meter_fault` |
| lay-energy-0705 | 계량기 고장으로 사용량이 이상하게 나온 것 같은데, 잘못 측정된 사용량과 요금은 어떻게 정정하나요? | `electricity_meter_fault` |
| lay-energy-0706 | 갑자기 전기 공급이 제한된다는 안내를 받았는데, 제한 사유와 적용 시점을 어디서 확인하나요? | `electricity_supply_restriction` |
| lay-energy-0707 | 갑자기 전기 공급이 제한된다는 안내를 받았는데, 계약전력·미납·안전 문제 중 어떤 이유인지 어떻게 구분하나요? | `electricity_supply_restriction` |
| lay-energy-0708 | 갑자기 전기 공급이 제한된다는 안내를 받았는데, 공급 제한을 피하거나 해제하려면 무엇을 해야 하나요? | `electricity_supply_restriction` |
| lay-energy-0709 | 갑자기 전기 공급이 제한된다는 안내를 받았는데, 생명·안전과 관련된 설비가 있다면 어디에 긴급히 알려야 하나요? | `electricity_supply_restriction` |
| lay-energy-0710 | 갑자기 전기 공급이 제한된다는 안내를 받았는데, 안내가 잘못됐다고 생각하면 어떤 절차로 이의를 제기하나요? | `electricity_supply_restriction` |
| lay-energy-0711 | 주택과 상가가 한 계량기를 함께 쓰고 있는데, 현재 계약과 요금이 두 공간에 어떻게 적용되는지 확인할 수 있나요? | `shared_home_shop_meter` |
| lay-energy-0712 | 주택과 상가가 한 계량기를 함께 쓰고 있는데, 계량기와 전기 계약을 나눌 수 있는 조건은 무엇인가요? | `shared_home_shop_meter` |
| lay-energy-0713 | 주택과 상가가 한 계량기를 함께 쓰고 있는데, 건물주와 사용자 중 누구의 동의와 신청이 필요한가요? | `shared_home_shop_meter` |
| lay-energy-0714 | 주택과 상가가 한 계량기를 함께 쓰고 있는데, 분리 공사와 새 계약에 드는 비용은 어떻게 확인하나요? | `shared_home_shop_meter` |
| lay-energy-0715 | 주택과 상가가 한 계량기를 함께 쓰고 있는데, 분리 전 사용량과 요금은 어떤 기준으로 나눠야 하나요? | `shared_home_shop_meter` |
| lay-energy-0716 | 폐업하면서 전기 계약을 해지하려는데, 폐업일에 맞춰 언제 어디에 해지를 신청해야 하나요? | `electricity_service_termination` |
| lay-energy-0717 | 폐업하면서 전기 계약을 해지하려는데, 마지막 사용량은 어떻게 확인하고 기록하나요? | `electricity_service_termination` |
| lay-energy-0718 | 폐업하면서 전기 계약을 해지하려는데, 남은 요금·보증금·환급액은 어떤 자료로 확인하나요? | `electricity_service_termination` |
| lay-energy-0719 | 폐업하면서 전기 계약을 해지하려는데, 명의와 폐업 사실을 확인할 어떤 서류가 필요한가요? | `electricity_service_termination` |
| lay-energy-0720 | 폐업하면서 전기 계약을 해지하려는데, 계약과 정산이 끝났는지 어떻게 확인하나요? | `electricity_service_termination` |
| lay-energy-0721 | 전출한 뒤 전기요금 정산이 남은 것을 알았는데, 어디에 전출일과 마지막 사용량을 알려야 하나요? | `electricity_move_out_settlement` |
| lay-energy-0722 | 전출 후 남은 전기요금을 정산하려는데, 마지막 사용량은 어떻게 확인하고 사진으로 남기나요? | `electricity_move_out_settlement` |
| lay-energy-0723 | 전출 후 남은 전기요금을 정산하려는데, 전출 전후 요금과 환급액은 어떤 자료로 확인하나요? | `electricity_move_out_settlement` |
| lay-energy-0724 | 전출 후 남은 전기요금을 정산하려는데, 현재 명의와 계약 종료 상태는 어떻게 확인하나요? | `electricity_move_out_settlement` |
| lay-energy-0725 | 전출 후 남은 전기요금을 정산하려는데, 정산과 계약 종료가 끝났는지 어디서 확인하나요? | `electricity_move_out_settlement` |
| lay-energy-0726 | 에너지바우처를 처음 신청하려는데, 지원 대상과 이용 조건을 어디서 확인하나요? | `energy_voucher_application` |
| lay-energy-0727 | 에너지바우처를 처음 신청하려는데, 어디에 어떤 방법으로 신청할 수 있나요? | `energy_voucher_application` |
| lay-energy-0728 | 에너지바우처를 처음 신청하려는데, 가구와 주소를 확인할 어떤 서류가 필요한가요? | `energy_voucher_application` |
| lay-energy-0729 | 에너지바우처를 처음 신청하려는데, 신청 결과와 이용 시작일은 어떻게 확인하나요? | `energy_voucher_application` |
| lay-energy-0730 | 에너지바우처를 처음 신청하려는데, 올해 지원액과 사용기한은 어디서 확인하나요? | `energy_voucher_application` |
| lay-energy-0731 | 에너지바우처 잔액과 사용기한이 궁금한데, 남은 금액은 어디서 확인하나요? | `energy_voucher_balance` |
| lay-energy-0732 | 에너지바우처 잔액과 사용기한이 궁금한데, 어디에 얼마를 사용했는지 내역을 볼 수 있나요? | `energy_voucher_balance` |
| lay-energy-0733 | 에너지바우처 잔액과 사용기한이 궁금한데, 남은 금액을 어떤 에너지 비용에 사용할 수 있나요? | `energy_voucher_balance` |
| lay-energy-0734 | 에너지바우처 잔액과 사용기한이 궁금한데, 잔액이 있는데 결제가 되지 않으면 어디에 문의하나요? | `energy_voucher_balance` |
| lay-energy-0735 | 에너지바우처 잔액과 사용기한이 궁금한데, 올해 사용할 수 있는 마지막 날은 언제인가요? | `energy_voucher_balance` |
| lay-energy-0736 | 에너지바우처 지원카드를 잃어버렸는데, 부정 사용을 막기 위해 어디에 분실 신고해야 하나요? | `energy_voucher_lost_card` |
| lay-energy-0737 | 에너지바우처 지원카드를 잃어버렸는데, 카드 재발급은 어떤 절차로 진행하나요? | `energy_voucher_lost_card` |
| lay-energy-0738 | 에너지바우처 지원카드를 잃어버렸는데, 재발급할 때 신분과 주소를 확인할 어떤 정보가 필요한가요? | `energy_voucher_lost_card` |
| lay-energy-0739 | 에너지바우처 지원카드를 잃어버렸는데, 기존 카드의 남은 금액은 새 카드로 이어지나요? | `energy_voucher_lost_card` |
| lay-energy-0740 | 에너지바우처 지원카드를 잃어버렸는데, 재발급을 기다리다 사용기한이 지나면 남은 금액은 어떻게 되나요? | `energy_voucher_lost_card` |

</details>

<details>
<summary>주택 태양광·소비자보호 — 55개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0741 | 우리 집 지붕에 태양광을 달고 싶은데, 설치 가능한지와 예상 발전량을 무엇으로 확인하나요? | `home_solar_install` |
| lay-energy-0742 | 우리 집 지붕에 태양광을 달고 싶은데, 소유자나 다른 주민의 동의가 필요한지 어떻게 확인하나요? | `home_solar_install` |
| lay-energy-0743 | 우리 집 지붕에 태양광을 달고 싶은데, 설치 장소와 사용 목적에 맞는 설비와 시공업체를 어떻게 고르나요? | `home_solar_install` |
| lay-energy-0744 | 우리 집 지붕에 태양광을 달고 싶은데, 설치비와 예상 절감액을 어떤 자료로 비교해야 하나요? | `home_solar_install` |
| lay-energy-0745 | 우리 집 지붕에 태양광을 달고 싶은데, 상담부터 설치와 점검까지 어떤 순서로 진행하나요? | `home_solar_install` |
| lay-energy-0746 | 전세로 사는 집에 태양광 설비를 설치하려는데, 설치 가능한지와 예상 발전량을 무엇으로 확인하나요? | `home_solar_install` |
| lay-energy-0747 | 전세로 사는 집에 태양광 설비를 설치하려는데, 소유자나 다른 주민의 동의가 필요한지 어떻게 확인하나요? | `home_solar_install` |
| lay-energy-0748 | 전세로 사는 집에 태양광 설비를 설치하려는데, 설치 장소와 사용 목적에 맞는 설비와 시공업체를 어떻게 고르나요? | `home_solar_install` |
| lay-energy-0749 | 전세로 사는 집에 태양광 설비를 설치하려는데, 설치비와 예상 절감액을 어떤 자료로 비교해야 하나요? | `home_solar_install` |
| lay-energy-0750 | 전세로 사는 집에 태양광 설비를 설치하려는데, 상담부터 설치와 점검까지 어떤 순서로 진행하나요? | `home_solar_install` |
| lay-energy-0751 | 다가구주택 옥상에 입주자 공동 태양광 설비를 놓으려는데, 설치 가능한지와 예상 발전량을 무엇으로 확인하나요? | `home_solar_install` |
| lay-energy-0752 | 다가구주택 옥상에 입주자 공동 태양광 설비를 놓으려는데, 소유자나 다른 주민의 동의가 필요한지 어떻게 확인하나요? | `home_solar_install` |
| lay-energy-0753 | 다가구주택 옥상에 입주자 공동 태양광 설비를 놓으려는데, 설치 장소와 사용 목적에 맞는 설비와 시공업체를 어떻게 고르나요? | `home_solar_install` |
| lay-energy-0754 | 다가구주택 옥상에 입주자 공동 태양광 설비를 놓으려는데, 설치비와 예상 절감액을 어떤 자료로 비교해야 하나요? | `home_solar_install` |
| lay-energy-0755 | 다가구주택 옥상에 입주자 공동 태양광 설비를 놓으려는데, 상담부터 설치와 점검까지 어떤 순서로 진행하나요? | `home_solar_install` |
| lay-energy-0756 | 무료 설치라는 태양광 영업 전화를 받았는데, 무료나 절감 보장이 사실인지 어떤 자료로 확인하나요? | `home_solar_sales_contract` |
| lay-energy-0757 | 무료 설치라는 태양광 영업 전화를 받았는데, 업체와 제품을 믿을 수 있는지 어디서 확인하나요? | `home_solar_sales_contract` |
| lay-energy-0758 | 무료 설치라는 태양광 영업 전화를 받았는데, 계약서에서 총비용·기간·설비 소유권을 어떻게 확인해야 하나요? | `home_solar_sales_contract` |
| lay-energy-0759 | 무료 설치라는 태양광 영업 전화를 받았는데, 계약을 취소하거나 바꾸려면 어떤 조건을 살펴야 하나요? | `home_solar_sales_contract` |
| lay-energy-0760 | 무료 설치라는 태양광 영업 전화를 받았는데, 과장광고가 의심되면 어디에 상담하거나 신고하나요? | `home_solar_sales_contract` |
| lay-energy-0761 | 전기요금 절감액을 보장한다는 계약을 권유받았는데, 약속한 절감액의 계산 근거와 보장 조건을 어떤 자료로 확인하나요? | `home_solar_sales_contract` |
| lay-energy-0762 | 전기요금 절감액을 보장한다는 계약을 권유받았는데, 업체와 제품을 믿을 수 있는지 어디서 확인하나요? | `home_solar_sales_contract` |
| lay-energy-0763 | 전기요금 절감액을 보장한다는 계약을 권유받았는데, 실제 절감액이 약속보다 적을 때의 제외 조건과 보상 내용을 어떻게 확인하나요? | `home_solar_sales_contract` |
| lay-energy-0764 | 전기요금 절감액을 보장한다는 계약을 권유받았는데, 중도해지하면 내야 할 비용과 설비 처리 조건은 무엇인가요? | `home_solar_sales_contract` |
| lay-energy-0765 | 전기요금 절감액을 보장한다는 계약을 권유받았는데, 분쟁에 대비해 어떤 자료를 남기고 어디에 상담해야 하나요? | `home_solar_sales_contract` |
| lay-energy-0766 | 설치업체가 계약금을 받은 뒤 연락이 되지 않는데, 계약과 입금 사실을 증명하려면 어떤 자료를 모아야 하나요? | `home_solar_seller_missing` |
| lay-energy-0767 | 설치업체가 계약금을 받은 뒤 연락이 되지 않는데, 업체에 연락이 닿지 않으면 어디에 상담하거나 신고하나요? | `home_solar_seller_missing` |
| lay-energy-0768 | 설치업체가 계약금을 받은 뒤 연락이 되지 않는데, 남은 대금 지급을 멈추고 이미 낸 계약금을 돌려받을 수 있는지 어떻게 확인하나요? | `home_solar_seller_missing` |
| lay-energy-0769 | 설치업체가 계약금을 받은 뒤 연락이 되지 않는데, 계약을 끝내려면 어떤 절차와 통지가 필요한가요? | `home_solar_seller_missing` |
| lay-energy-0770 | 설치업체가 계약금을 받은 뒤 연락이 되지 않는데, 다른 업체에 맡기기 전에 기존 계약에서 무엇을 정리해야 하나요? | `home_solar_seller_missing` |
| lay-energy-0771 | 패널 설치 후 지붕에서 물이 새는데, 피해가 커지기 전에 무엇을 기록하고 조치해야 하나요? | `home_solar_defect` |
| lay-energy-0772 | 패널 설치 후 지붕에서 물이 새는데, 계약서와 보증서에서 수리 책임을 어떻게 확인하나요? | `home_solar_defect` |
| lay-energy-0773 | 패널 설치 후 지붕에서 물이 새는데, 문제 원인과 수리 범위를 누구에게 점검받아야 하나요? | `home_solar_defect` |
| lay-energy-0774 | 패널 설치 후 지붕에서 물이 새는데, 수리비와 추가 손해는 누구에게 요구할 수 있나요? | `home_solar_defect` |
| lay-energy-0775 | 패널 설치 후 지붕에서 물이 새는데, 해결되지 않으면 어디에 상담이나 분쟁조정을 요청하나요? | `home_solar_defect` |
| lay-energy-0776 | 인버터가 고장 났지만 설치업체가 폐업한 상황인데, 피해가 커지기 전에 무엇을 기록하고 조치해야 하나요? | `home_solar_defect` |
| lay-energy-0777 | 인버터가 고장 났지만 설치업체가 폐업한 상황인데, 계약서와 보증서에서 수리 책임을 어떻게 확인하나요? | `home_solar_defect` |
| lay-energy-0778 | 인버터가 고장 났지만 설치업체가 폐업한 상황인데, 문제 원인과 수리 범위를 누구에게 점검받아야 하나요? | `home_solar_defect` |
| lay-energy-0779 | 인버터가 고장 났지만 설치업체가 폐업한 상황인데, 수리비와 추가 손해는 누구에게 요구할 수 있나요? | `home_solar_defect` |
| lay-energy-0780 | 인버터가 고장 났지만 설치업체가 폐업한 상황인데, 해결되지 않으면 어디에 상담이나 분쟁조정을 요청하나요? | `home_solar_defect` |
| lay-energy-0781 | 집을 팔면서 태양광 설비 계약도 넘기려는데, 설비와 계약의 소유자·남은 기간·승계 가능 여부를 어떻게 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0782 | 집을 팔면서 태양광 설비 계약도 넘기려는데, 매수인·설치업체·전력회사에는 무엇을 언제 알려야 하나요? | `home_solar_transfer_exit` |
| lay-energy-0783 | 집을 팔면서 태양광 설비 계약도 넘기려는데, 이전 수수료·미납금·철거 비용은 누가 부담하는지 어떻게 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0784 | 집을 팔면서 태양광 설비 계약도 넘기려는데, 계약과 전기 명의를 바꾸려면 어떤 서류와 확인이 필요한가요? | `home_solar_transfer_exit` |
| lay-energy-0785 | 집을 팔면서 태양광 설비 계약도 넘기려는데, 계약·명의·설비 인계가 모두 끝났는지 어떻게 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0786 | 임대형 태양광 계약을 중간에 끝내고 싶은데, 계약기간과 중도해지 조건을 어디서 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0787 | 임대형 태양광 계약을 중간에 끝내고 싶은데, 임대업체·집주인·전력회사 중 누구에게 먼저 알려야 하나요? | `home_solar_transfer_exit` |
| lay-energy-0788 | 임대형 태양광 계약을 중간에 끝내고 싶은데, 위약금과 철거·원상복구 비용은 누가 부담하는지 어떻게 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0789 | 임대형 태양광 계약을 중간에 끝내고 싶은데, 중도해지와 설비 반환·철거에 어떤 서류와 확인이 필요한가요? | `home_solar_transfer_exit` |
| lay-energy-0790 | 임대형 태양광 계약을 중간에 끝내고 싶은데, 계약 종료와 설비 처리가 모두 끝났는지 어떻게 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0791 | 오래된 주택 태양광 설비를 철거하려는데, 설비 소유자와 남은 계약이 있는지 어떻게 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0792 | 오래된 주택 태양광 설비를 철거하려는데, 소유자·설치업체·전력회사 중 누구에게 먼저 알려야 하나요? | `home_solar_transfer_exit` |
| lay-energy-0793 | 오래된 주택 태양광 설비를 철거하려는데, 철거·폐기·지붕 복구 비용은 누가 부담하는지 어떻게 확인하나요? | `home_solar_transfer_exit` |
| lay-energy-0794 | 오래된 주택 태양광 설비를 철거하려는데, 전기 연결 해제와 철거에 어떤 서류와 확인이 필요한가요? | `home_solar_transfer_exit` |
| lay-energy-0795 | 오래된 주택 태양광 설비를 철거하려는데, 설비 제거와 지붕 복구, 계약 종료가 끝났는지 어떻게 확인하나요? | `home_solar_transfer_exit` |

</details>

<details>
<summary>전기차 충전 — 50개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0796 | 아파트에 공용 전기차 충전기를 설치하려는데, 누구의 동의를 받고 어떤 장소 조건을 확인해야 하나요? | `ev_charging_install` |
| lay-energy-0797 | 아파트에 공용 전기차 충전기를 설치하려는데, 설치 신청과 현장조사는 어떤 순서로 진행되나요? | `ev_charging_install` |
| lay-energy-0798 | 아파트에 공용 전기차 충전기를 설치하려는데, 건물과 주차장 관련 어떤 서류를 준비해야 하나요? | `ev_charging_install` |
| lay-energy-0799 | 아파트에 공용 전기차 충전기를 설치하려는데, 전기 용량과 공사 범위는 어떻게 확인하나요? | `ev_charging_install` |
| lay-energy-0800 | 아파트에 공용 전기차 충전기를 설치하려는데, 설치비와 지원 조건은 어디서 최신 정보를 확인하나요? | `ev_charging_install` |
| lay-energy-0801 | 단독주택 주차장에 개인 충전기를 달려는데, 누구의 동의를 받고 어떤 장소 조건을 확인해야 하나요? | `ev_charging_install` |
| lay-energy-0802 | 단독주택 주차장에 개인 충전기를 달려는데, 설치 신청과 현장조사는 어떤 순서로 진행되나요? | `ev_charging_install` |
| lay-energy-0803 | 단독주택 주차장에 개인 충전기를 달려는데, 건물과 주차장 관련 어떤 서류를 준비해야 하나요? | `ev_charging_install` |
| lay-energy-0804 | 단독주택 주차장에 개인 충전기를 달려는데, 전기 용량과 공사 범위는 어떻게 확인하나요? | `ev_charging_install` |
| lay-energy-0805 | 단독주택 주차장에 개인 충전기를 달려는데, 설치비와 지원 조건은 어디서 최신 정보를 확인하나요? | `ev_charging_install` |
| lay-energy-0806 | 회사 주차장에 직원용 충전기를 설치하려는데, 누구의 동의를 받고 어떤 장소 조건을 확인해야 하나요? | `ev_charging_install` |
| lay-energy-0807 | 회사 주차장에 직원용 충전기를 설치하려는데, 설치 신청과 현장조사는 어떤 순서로 진행되나요? | `ev_charging_install` |
| lay-energy-0808 | 회사 주차장에 직원용 충전기를 설치하려는데, 건물과 주차장 관련 어떤 서류를 준비해야 하나요? | `ev_charging_install` |
| lay-energy-0809 | 회사 주차장에 직원용 충전기를 설치하려는데, 전기 용량과 공사 범위는 어떻게 확인하나요? | `ev_charging_install` |
| lay-energy-0810 | 회사 주차장에 직원용 충전기를 설치하려는데, 설치비와 지원 조건은 어디서 최신 정보를 확인하나요? | `ev_charging_install` |
| lay-energy-0811 | 상가 주차장에서 충전사업을 시작하려는데, 누구의 동의를 받고 어떤 장소 조건을 확인해야 하나요? | `ev_charging_install` |
| lay-energy-0812 | 상가 주차장에서 충전사업을 시작하려는데, 설치 신청과 현장조사는 어떤 순서로 진행되나요? | `ev_charging_install` |
| lay-energy-0813 | 상가 주차장에서 충전사업을 시작하려는데, 건물과 주차장 관련 어떤 서류를 준비해야 하나요? | `ev_charging_install` |
| lay-energy-0814 | 상가 주차장에서 충전사업을 시작하려는데, 전기 용량과 공사 범위는 어떻게 확인하나요? | `ev_charging_install` |
| lay-energy-0815 | 상가 주차장에서 충전사업을 시작하려는데, 설치비와 지원 조건은 어디서 최신 정보를 확인하나요? | `ev_charging_install` |
| lay-energy-0816 | 임차한 건물에 완속충전기를 놓으려는데, 누구의 동의를 받고 어떤 장소 조건을 확인해야 하나요? | `ev_charging_install` |
| lay-energy-0817 | 임차한 건물에 완속충전기를 놓으려는데, 설치 신청과 현장조사는 어떤 순서로 진행되나요? | `ev_charging_install` |
| lay-energy-0818 | 임차한 건물에 완속충전기를 놓으려는데, 건물과 주차장 관련 어떤 서류를 준비해야 하나요? | `ev_charging_install` |
| lay-energy-0819 | 임차한 건물에 완속충전기를 놓으려는데, 전기 용량과 공사 범위는 어떻게 확인하나요? | `ev_charging_install` |
| lay-energy-0820 | 임차한 건물에 완속충전기를 놓으려는데, 설치비와 지원 조건은 어디서 최신 정보를 확인하나요? | `ev_charging_install` |
| lay-energy-0821 | 충전기 설치 보조금을 신청하려는데, 누가 어떤 장소에 설치할 때 지원받을 수 있나요? | `ev_charging_support` |
| lay-energy-0822 | 충전기 설치 보조금을 신청하려는데, 언제 신청하고 설치 계약은 어느 시점에 해야 하나요? | `ev_charging_support` |
| lay-energy-0823 | 충전기 설치 보조금을 신청하려는데, 신청자와 설치 장소를 증명할 어떤 서류가 필요한가요? | `ev_charging_support` |
| lay-energy-0824 | 충전기 설치 보조금을 신청하려는데, 지원 범위와 본인 부담 비용은 어디서 확인하나요? | `ev_charging_support` |
| lay-energy-0825 | 충전기 설치 보조금을 신청하려는데, 올해 신청 방법과 남은 예산은 어디서 확인하나요? | `ev_charging_support` |
| lay-energy-0826 | 충전카드를 발급받고 요금을 결제하려는데, 내 계정과 충전 이용 내역은 어디서 확인하나요? | `ev_charging_payment` |
| lay-energy-0827 | 충전카드를 발급받고 요금을 결제하려는데, 사용할 수 있는 결제 방법과 요금은 어떻게 확인하나요? | `ev_charging_payment` |
| lay-energy-0828 | 충전카드를 발급받고 요금을 결제하려는데, 청구·결제·정산 금액이 맞는지 어떤 자료로 확인하나요? | `ev_charging_payment` |
| lay-energy-0829 | 충전카드를 발급받고 요금을 결제하려는데, 결제 오류나 중복 청구가 있으면 어디에 정정을 요청하나요? | `ev_charging_payment` |
| lay-energy-0830 | 충전카드를 발급받고 요금을 결제하려는데, 운영사별 요금과 이용 조건은 어디서 최신 정보를 확인하나요? | `ev_charging_payment` |
| lay-energy-0831 | 충전요금 정산이 맞지 않는 것 같은데, 이용 시간과 충전기 사용 기록은 어디서 확인하나요? | `ev_charging_payment` |
| lay-energy-0832 | 충전요금 정산이 맞지 않는 것 같은데, 이용 당시 적용된 결제 방법·요금·할인은 어떻게 확인하나요? | `ev_charging_payment` |
| lay-energy-0833 | 충전요금 정산이 맞지 않는 것 같은데, 충전 시간·적용 요금·결제 금액을 어떤 자료로 대조하나요? | `ev_charging_payment` |
| lay-energy-0834 | 충전요금 정산이 맞지 않는 것 같은데, 결제 오류나 중복 청구를 어디에 정정 요청하나요? | `ev_charging_payment` |
| lay-energy-0835 | 충전요금 정산이 맞지 않는 것 같은데, 현재 요금이 아니라 이용 당시의 요금과 약관은 어디서 확인하나요? | `ev_charging_payment` |
| lay-energy-0836 | 충전기가 자주 고장 나 이용하지 못하고 있는데, 고장 상태와 복구 예정 시간을 어디서 확인하나요? | `ev_charging_failure` |
| lay-energy-0837 | 충전기가 자주 고장 나 이용하지 못하고 있는데, 운영사나 건물 관리 주체 중 어디에 연락해야 하나요? | `ev_charging_failure` |
| lay-energy-0838 | 충전기가 자주 고장 나 이용하지 못하고 있는데, 위험해 보일 때 사용을 멈추고 어떻게 신고해야 하나요? | `ev_charging_failure` |
| lay-energy-0839 | 충전기가 자주 고장 나 이용하지 못하고 있는데, 결제됐지만 충전하지 못한 금액은 어떻게 돌려받나요? | `ev_charging_failure` |
| lay-energy-0840 | 충전기가 자주 고장 나 이용하지 못하고 있는데, 같은 고장이 반복되면 교체나 추가 조치를 누구에게 요구하나요? | `ev_charging_failure` |
| lay-energy-0841 | 기존 충전기를 다른 위치로 옮기려는데, 새 장소에서 누구의 동의와 현장 확인이 필요한가요? | `ev_charging_relocation` |
| lay-energy-0842 | 기존 충전기를 다른 위치로 옮기려는데, 기존 전기 연결은 누가 어떤 안전 절차에 따라 끊어야 하나요? | `ev_charging_relocation` |
| lay-energy-0843 | 기존 충전기를 다른 위치로 옮기려는데, 이전 설치와 전기 사용 변경은 어디에 신청하나요? | `ev_charging_relocation` |
| lay-energy-0844 | 기존 충전기를 다른 위치로 옮기려는데, 철거·운반·재설치 비용은 누가 부담하는지 어떻게 확인하나요? | `ev_charging_relocation` |
| lay-energy-0845 | 기존 충전기를 다른 위치로 옮기려는데, 충전기 등록 주소와 운영 정보, 이용자 안내는 어떻게 바꿔야 하나요? | `ev_charging_relocation` |

</details>

<details>
<summary>ESS — 35개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0846 | 태양광 발전소에 배터리 저장장치를 추가하려는데, 설치 전에 어떤 신고·검사·확인이 필요한가요? | `ess_install` |
| lay-energy-0847 | 태양광 발전소에 배터리 저장장치를 추가하려는데, 설치 장소와 주변 시설 사이의 안전거리는 어디서 확인하나요? | `ess_install` |
| lay-energy-0848 | 태양광 발전소에 배터리 저장장치를 추가하려는데, 화재 예방을 위해 어떤 감지·소화 설비를 갖춰야 하나요? | `ess_install` |
| lay-energy-0849 | 태양광 발전소에 배터리 저장장치를 추가하려는데, 설계와 시공을 맡길 업체의 자격은 어떻게 확인하나요? | `ess_install` |
| lay-energy-0850 | 태양광 발전소에 배터리 저장장치를 추가하려는데, 가동 전에 점검·비상대응 계획을 어떻게 준비해야 하나요? | `ess_install` |
| lay-energy-0851 | 공장 피크요금을 줄이려고 대형 배터리를 설치하려는데, 설치 전에 어떤 신고·검사·확인이 필요한가요? | `ess_install` |
| lay-energy-0852 | 공장 피크요금을 줄이려고 대형 배터리를 설치하려는데, 설치 장소와 주변 시설 사이의 안전거리는 어디서 확인하나요? | `ess_install` |
| lay-energy-0853 | 공장 피크요금을 줄이려고 대형 배터리를 설치하려는데, 화재 예방을 위해 어떤 감지·소화 설비를 갖춰야 하나요? | `ess_install` |
| lay-energy-0854 | 공장 피크요금을 줄이려고 대형 배터리를 설치하려는데, 설계와 시공을 맡길 업체의 자격은 어떻게 확인하나요? | `ess_install` |
| lay-energy-0855 | 공장 피크요금을 줄이려고 대형 배터리를 설치하려는데, 가동 전에 점검·비상대응 계획을 어떻게 준비해야 하나요? | `ess_install` |
| lay-energy-0856 | 컨테이너형 배터리 저장시설을 옥외에 놓으려는데, 설치 전에 어떤 신고·검사·확인이 필요한가요? | `ess_install` |
| lay-energy-0857 | 컨테이너형 배터리 저장시설을 옥외에 놓으려는데, 설치 장소와 주변 시설 사이의 안전거리는 어디서 확인하나요? | `ess_install` |
| lay-energy-0858 | 컨테이너형 배터리 저장시설을 옥외에 놓으려는데, 화재 예방을 위해 어떤 감지·소화 설비를 갖춰야 하나요? | `ess_install` |
| lay-energy-0859 | 컨테이너형 배터리 저장시설을 옥외에 놓으려는데, 설계와 시공을 맡길 업체의 자격은 어떻게 확인하나요? | `ess_install` |
| lay-energy-0860 | 컨테이너형 배터리 저장시설을 옥외에 놓으려는데, 가동 전에 점검·비상대응 계획을 어떻게 준비해야 하나요? | `ess_install` |
| lay-energy-0861 | 오래된 저장장치의 배터리를 교체하려는데, 교체가 필요한 상태인지 어떤 기록과 점검으로 판단하나요? | `ess_battery_replacement` |
| lay-energy-0862 | 오래된 저장장치의 배터리를 교체하려는데, 교체 전에 설비 정지는 누가 어떤 안전 절차에 따라 해야 하나요? | `ess_battery_replacement` |
| lay-energy-0863 | 오래된 저장장치의 배터리를 교체하려는데, 새 배터리 설치 후 어떤 검사와 확인이 필요한가요? | `ess_battery_replacement` |
| lay-energy-0864 | 오래된 저장장치의 배터리를 교체하려는데, 기존 설비와 새 배터리가 맞는지 무엇으로 확인하나요? | `ess_battery_replacement` |
| lay-energy-0865 | 오래된 저장장치의 배터리를 교체하려는데, 떼어낸 배터리는 어디에 어떤 방식으로 처리해야 하나요? | `ess_battery_replacement` |
| lay-energy-0866 | 저장시설에서 열과 냄새가 나 화재가 걱정되는데, 사람과 설비의 안전을 위해 가장 먼저 무엇을 해야 하나요? | `ess_warning_reactivation` |
| lay-energy-0867 | 저장시설에서 열과 냄새가 나 화재가 걱정되는데, 사용을 중지하고 어디에 신고하거나 점검을 요청해야 하나요? | `ess_warning_reactivation` |
| lay-energy-0868 | 저장시설에서 열과 냄새가 나 화재가 걱정되는데, 원인과 피해 범위를 확인하려면 어떤 기록과 검사가 필요한가요? | `ess_warning_reactivation` |
| lay-energy-0869 | 저장시설에서 열과 냄새가 나 화재가 걱정되는데, 화재를 막고 이상 징후가 다시 생기지 않도록 무엇을 보완해야 하나요? | `ess_warning_reactivation` |
| lay-energy-0870 | 저장시설에서 열과 냄새가 나 화재가 걱정되는데, 다시 가동해도 된다는 판단은 어떤 절차로 받아야 하나요? | `ess_warning_reactivation` |
| lay-energy-0871 | 저장장치 화재 후 설비를 다시 가동하려는데, 조사와 점검이 끝날 때까지 사람의 접근과 설비 사용을 어떻게 막아야 하나요? | `ess_warning_reactivation` |
| lay-energy-0872 | 저장장치 화재 후 설비를 다시 가동하려는데, 화재 신고·사고조사·재가동 전 점검은 어디에 요청해야 하나요? | `ess_warning_reactivation` |
| lay-energy-0873 | 저장장치 화재 후 설비를 다시 가동하려는데, 화재 원인과 피해 범위를 확인하려면 어떤 기록과 검사가 필요한가요? | `ess_warning_reactivation` |
| lay-energy-0874 | 저장장치 화재 후 설비를 다시 가동하려는데, 같은 화재가 재발하지 않도록 무엇을 보완해야 하나요? | `ess_warning_reactivation` |
| lay-energy-0875 | 저장장치 화재 후 설비를 다시 가동하려는데, 다시 가동해도 된다는 판단은 누구에게 어떤 절차로 받아야 하나요? | `ess_warning_reactivation` |
| lay-energy-0876 | 사용을 끝낸 배터리와 저장시설을 철거하려는데, 철거 전에 설비 정지는 누가 어떤 안전 절차에 따라 해야 하나요? | `ess_decommission` |
| lay-energy-0877 | 사용을 끝낸 배터리와 저장시설을 철거하려는데, 사업자와 철거업체는 각각 무엇을 책임져야 하나요? | `ess_decommission` |
| lay-energy-0878 | 사용을 끝낸 배터리와 저장시설을 철거하려는데, 배터리와 전기설비는 어디에 어떤 방식으로 처리해야 하나요? | `ess_decommission` |
| lay-energy-0879 | 사용을 끝낸 배터리와 저장시설을 철거하려는데, 운반·처리·철거 기록은 무엇을 남겨야 하나요? | `ess_decommission` |
| lay-energy-0880 | 사용을 끝낸 배터리와 저장시설을 철거하려는데, 시설과 부지의 안전조치가 끝났는지 어떻게 확인하나요? | `ess_decommission` |

</details>

<details>
<summary>분산에너지·직접거래·VPP·RE100 — 40개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0881 | 우리 지역에서 만든 전기를 지역 기업에 직접 팔고 싶은데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0882 | 우리 지역에서 만든 전기를 지역 기업에 직접 팔고 싶은데, 전기를 만드는 사람·거래를 맡는 사업자·사용자의 역할은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0883 | 우리 지역에서 만든 전기를 지역 기업에 직접 팔고 싶은데, 발전량과 사용량을 확인하려면 어떤 계량기와 사용 기록이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0884 | 우리 지역에서 만든 전기를 지역 기업에 직접 팔고 싶은데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0885 | 우리 지역에서 만든 전기를 지역 기업에 직접 팔고 싶은데, 전력망 연결 문제나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |
| lay-energy-0886 | 여러 작은 발전소를 묶어 전기를 거래하려는데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0887 | 여러 작은 발전소를 묶어 전기를 거래하려는데, 전기를 만드는 사람·거래를 맡는 사업자·사용자의 역할은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0888 | 여러 작은 발전소를 묶어 전기를 거래하려는데, 발전량과 사용량을 확인하려면 어떤 계량기와 사용 기록이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0889 | 여러 작은 발전소를 묶어 전기를 거래하려는데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0890 | 여러 작은 발전소를 묶어 전기를 거래하려는데, 전력망 연결 문제나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |
| lay-energy-0891 | 여러 공장의 전력 사용량과 발전량을 묶어 관리하고 전기를 거래하려는데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0892 | 여러 공장의 전력 사용량과 발전량을 묶어 관리하고 전기를 거래하려는데, 전기를 만드는 사람·거래를 맡는 사업자·사용자의 역할은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0893 | 여러 공장의 전력 사용량과 발전량을 묶어 관리하고 전기를 거래하려는데, 발전량과 사용량을 확인하려면 어떤 계량기와 사용 기록이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0894 | 여러 공장의 전력 사용량과 발전량을 묶어 관리하고 전기를 거래하려는데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0895 | 여러 공장의 전력 사용량과 발전량을 묶어 관리하고 전기를 거래하려는데, 전력망 연결 문제나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |
| lay-energy-0896 | 정부가 지정한 지역 안에서 발전사업자와 사용자가 전기를 직접 거래하는 사업에 참여하려는데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0897 | 정부가 지정한 지역 안에서 발전사업자와 사용자가 전기를 직접 거래하는 사업에 참여하려는데, 전기를 만드는 사람·거래를 맡는 사업자·사용자의 역할은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0898 | 정부가 지정한 지역 안에서 발전사업자와 사용자가 전기를 직접 거래하는 사업에 참여하려는데, 발전량과 사용량을 확인하려면 어떤 계량기와 사용 기록이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0899 | 정부가 지정한 지역 안에서 발전사업자와 사용자가 전기를 직접 거래하는 사업에 참여하려는데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0900 | 정부가 지정한 지역 안에서 발전사업자와 사용자가 전기를 직접 거래하는 사업에 참여하려는데, 전력망 연결 문제나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |
| lay-energy-0901 | 주민 소유 발전소와 지역 전기 사용자를 연결하려는데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0902 | 주민 소유 발전소와 지역 전기 사용자를 연결하려는데, 전기를 만드는 사람·거래를 맡는 사업자·사용자의 역할은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0903 | 주민 소유 발전소와 지역 전기 사용자를 연결하려는데, 발전량과 사용량을 확인하려면 어떤 계량기와 사용 기록이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0904 | 주민 소유 발전소와 지역 전기 사용자를 연결하려는데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0905 | 주민 소유 발전소와 지역 전기 사용자를 연결하려는데, 전력망 연결 문제나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |
| lay-energy-0906 | 여러 발전소의 재생전기를 한 사업자가 모아 대신 판매하는 방식으로 전기를 사려는데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0907 | 여러 발전소의 재생전기를 한 사업자가 모아 대신 판매하는 방식으로 전기를 사려는데, 전기를 만드는 사람·거래를 맡는 사업자·사용자의 역할은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0908 | 여러 발전소의 재생전기를 한 사업자가 모아 대신 판매하는 방식으로 전기를 사려는데, 발전량과 사용량을 확인하려면 어떤 계량기와 사용 기록이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0909 | 여러 발전소의 재생전기를 한 사업자가 모아 대신 판매하는 방식으로 전기를 사려는데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0910 | 여러 발전소의 재생전기를 한 사업자가 모아 대신 판매하는 방식으로 전기를 사려는데, 전력망 연결 문제나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |
| lay-energy-0911 | 우리 회사가 쓰는 전기를 재생에너지로 바꾸려는데, 회사 규모와 전기 계약 형태에 따라 어떤 재생전기 구매 방식과 계약을 이용할 수 있나요? | `distributed_vpp_re100` |
| lay-energy-0912 | 우리 회사가 쓰는 전기를 재생에너지로 바꾸려는데, 발전사업자·전기판매자·우리 회사의 역할과 계약은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0913 | 우리 회사가 쓰는 전기를 재생에너지로 바꾸려는데, 재생에너지로 쓴 양을 인정받으려면 어떤 계약서·사용량·인증 자료가 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0914 | 우리 회사가 쓰는 전기를 재생에너지로 바꾸려는데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0915 | 우리 회사가 쓰는 전기를 재생에너지로 바꾸려는데, 재생전기 공급 중단이나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |
| lay-energy-0916 | 전기차와 대형 배터리에 저장한 전기를 묶어 거래하려는데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0917 | 전기차와 대형 배터리에 저장한 전기를 묶어 거래하려는데, 차량·배터리 소유자, 묶어 운영하는 사업자, 전기 구매자의 역할은 어떻게 나뉘나요? | `distributed_vpp_re100` |
| lay-energy-0918 | 전기차와 대형 배터리에 저장한 전기를 묶어 거래하려는데, 충전량·방전량과 거래량을 확인하려면 어떤 계량기와 기록이 필요한가요? | `distributed_vpp_re100` |
| lay-energy-0919 | 전기차와 대형 배터리에 저장한 전기를 묶어 거래하려는데, 전기요금과 거래대금은 누구와 어떤 방식으로 정산하나요? | `distributed_vpp_re100` |
| lay-energy-0920 | 전기차와 대형 배터리에 저장한 전기를 묶어 거래하려는데, 전력망 문제나 계약 불이행이 생기면 어떤 책임과 보호장치가 있나요? | `distributed_vpp_re100` |

</details>

<details>
<summary>주민·환경·철거·폐기 — 40개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0921 | 마을 근처에 태양광 발전소를 짓겠다는 설명을 들었는데, 사업 내용과 예상 영향을 어떤 자료로 확인할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0922 | 마을 근처에 태양광 발전소를 짓겠다는 설명을 들었는데, 주민 의견은 언제 어디에 제출할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0923 | 마을 근처에 태양광 발전소를 짓겠다는 설명을 들었는데, 공사 전후 영향을 비교하려면 어떤 현장 기록을 남겨야 하나요? | `residents_planned_project_impact` |
| lay-energy-0924 | 마을 근처에 태양광 발전소를 짓겠다는 설명을 들었는데, 추가 영향 조사나 계획 보완을 요청하려면 어디에 문의해야 하나요? | `residents_planned_project_impact` |
| lay-energy-0925 | 마을 근처에 태양광 발전소를 짓겠다는 설명을 들었는데, 소음·빛·토사 같은 피해를 줄일 계획이 있는지 어떻게 확인하나요? | `residents_planned_project_impact` |
| lay-energy-0926 | 마을 근처 풍력발전기의 소음과 그림자가 걱정되는데, 사업 내용과 예상 영향을 어떤 자료로 확인할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0927 | 마을 근처 풍력발전기의 소음과 그림자가 걱정되는데, 주민 의견은 언제 어디에 제출할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0928 | 마을 근처 풍력발전기의 소음과 그림자가 걱정되는데, 설치·가동 전후 영향을 비교하려면 어떤 현장 기록을 남겨야 하나요? | `residents_planned_project_impact` |
| lay-energy-0929 | 마을 근처 풍력발전기의 소음과 그림자가 걱정되는데, 추가 영향 조사나 계획 보완을 요청하려면 어디에 문의해야 하나요? | `residents_planned_project_impact` |
| lay-energy-0930 | 마을 근처 풍력발전기의 소음과 그림자가 걱정되는데, 소음·저주파음·그림자 영향을 줄일 계획이 있는지 어떻게 확인하나요? | `residents_planned_project_impact` |
| lay-energy-0931 | 산지 태양광에서 흙이 흘러내릴까 걱정되는데, 사업 내용과 예상 영향을 어떤 자료로 확인할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0932 | 산지 태양광에서 흙이 흘러내릴까 걱정되는데, 주민 의견은 언제 어디에 제출할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0933 | 산지 태양광에서 흙이 흘러내릴까 걱정되는데, 공사 전후 영향을 비교하려면 어떤 현장 기록을 남겨야 하나요? | `residents_planned_project_impact` |
| lay-energy-0934 | 산지 태양광에서 흙이 흘러내릴까 걱정되는데, 추가 영향 조사나 계획 보완을 요청하려면 어디에 문의해야 하나요? | `residents_planned_project_impact` |
| lay-energy-0935 | 산지 태양광에서 흙이 흘러내릴까 걱정되는데, 토사 유출·산사태·배수 문제를 줄일 계획이 있는지 어떻게 확인하나요? | `residents_planned_project_impact` |
| lay-energy-0936 | 사업자가 주민 설명 없이 발전소 공사를 시작하려고 하는데, 사업 내용과 예상 영향을 어떤 자료로 확인할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0937 | 사업자가 주민 설명 없이 발전소 공사를 시작하려고 하는데, 주민 의견은 언제 어디에 제출할 수 있나요? | `residents_planned_project_impact` |
| lay-energy-0938 | 사업자가 주민 설명 없이 발전소 공사를 시작하려고 하는데, 공사 전후 영향을 비교하려면 어떤 현장 기록을 남겨야 하나요? | `residents_planned_project_impact` |
| lay-energy-0939 | 사업자가 주민 설명 없이 발전소 공사를 시작하려고 하는데, 조사나 시정 조치를 요청하려면 어디에 문의해야 하나요? | `residents_planned_project_impact` |
| lay-energy-0940 | 사업자가 주민 설명 없이 발전소 공사를 시작하려고 하는데, 예상 피해를 줄일 계획이 있는지 어떻게 확인하나요? | `residents_planned_project_impact` |
| lay-energy-0941 | 태양광 패널의 빛 반사가 생활에 불편을 주는데, 발생 시간·사진·영상·측정 기록을 어떻게 모아야 하나요? | `residents_existing_project_harm` |
| lay-energy-0942 | 태양광 패널의 빛 반사가 생활에 불편을 주는데, 허가된 설비 배치와 실제 설치·운영 상태를 어떤 자료로 비교하나요? | `residents_existing_project_harm` |
| lay-energy-0943 | 태양광 패널의 빛 반사가 생활에 불편을 주는데, 빛 반사를 줄이거나 시정 조치를 요청하려면 어디에 민원을 내야 하나요? | `residents_existing_project_harm` |
| lay-energy-0944 | 태양광 패널의 빛 반사가 생활에 불편을 주는데, 반사광의 세기와 노출 시간을 줄이기 위해 어떤 조치를 요구할 수 있나요? | `residents_existing_project_harm` |
| lay-energy-0945 | 태양광 패널의 빛 반사가 생활에 불편을 주는데, 피해 방지 비용과 손해 책임은 누가 부담하는지 어떻게 확인하나요? | `residents_existing_project_harm` |
| lay-energy-0946 | 발전소 공사로 농로와 배수로가 손상됐는데, 피해 상태를 보여 줄 사진·영상·측정 기록을 어떻게 모아야 하나요? | `residents_existing_project_harm` |
| lay-energy-0947 | 발전소 공사로 농로와 배수로가 손상됐는데, 허가된 공사 범위와 실제 훼손 상태를 어떤 자료로 비교하나요? | `residents_existing_project_harm` |
| lay-energy-0948 | 발전소 공사로 농로와 배수로가 손상됐는데, 복구나 시정 조치를 요청하려면 어디에 민원을 내야 하나요? | `residents_existing_project_harm` |
| lay-energy-0949 | 발전소 공사로 농로와 배수로가 손상됐는데, 통행·배수 차질과 추가 피해를 막기 위해 어떤 조치를 요구할 수 있나요? | `residents_existing_project_harm` |
| lay-energy-0950 | 발전소 공사로 농로와 배수로가 손상됐는데, 복구비와 손해 책임은 누가 부담하는지 어떻게 확인하나요? | `residents_existing_project_harm` |
| lay-energy-0951 | 운영이 끝난 발전소가 방치되어 있는데, 현재 소유자와 철거 책임자를 어떻게 확인하나요? | `abandoned_generation_project` |
| lay-energy-0952 | 운영이 끝난 발전소가 방치되어 있는데, 철거 전까지 사고를 막기 위해 어떤 안전조치가 필요한가요? | `abandoned_generation_project` |
| lay-energy-0953 | 운영이 끝난 발전소가 방치되어 있는데, 남은 발전설비와 구조물은 어디에 어떤 방식으로 처리해야 하나요? | `abandoned_generation_project` |
| lay-energy-0954 | 운영이 끝난 발전소가 방치되어 있는데, 부지와 주변 시설의 복구 책임은 어떻게 확인하나요? | `abandoned_generation_project` |
| lay-energy-0955 | 운영이 끝난 발전소가 방치되어 있는데, 철거·복구 계획과 실제 이행 여부를 어떻게 확인하고 시정을 요구하나요? | `abandoned_generation_project` |
| lay-energy-0956 | 수명이 끝난 태양광 패널과 설비를 철거·폐기하려는데, 설비 소유자와 철거 책임자를 어떻게 확인하나요? | `solar_panel_decommission` |
| lay-energy-0957 | 수명이 끝난 태양광 패널과 설비를 철거·폐기하려는데, 철거 전에 전기 연결은 누가 어떤 안전 절차에 따라 끊어야 하나요? | `solar_panel_decommission` |
| lay-energy-0958 | 수명이 끝난 태양광 패널과 설비를 철거·폐기하려는데, 패널·구조물과 배터리가 있다면 각각 어떻게 처리해야 하나요? | `solar_panel_decommission` |
| lay-energy-0959 | 수명이 끝난 태양광 패널과 설비를 철거·폐기하려는데, 운반·재활용·폐기 과정을 어떤 기록으로 남겨야 하나요? | `solar_panel_decommission` |
| lay-energy-0960 | 수명이 끝난 태양광 패널과 설비를 철거·폐기하려는데, 철거 뒤 설비 제거와 부지 복구가 끝났는지 어떻게 확인하나요? | `solar_panel_decommission` |

</details>

<details>
<summary>기타 재생에너지 — 40개</summary>

| ID | 질문 | 연구 주제 |
|---|---|---|
| lay-energy-0961 | 바람이 강한 지역에서 소규모 풍력사업을 해보려는데, 사업 가능성을 판단하려면 어떤 자원과 입지 조건을 확인해야 하나요? | `other_renewables_project` |
| lay-energy-0962 | 바람이 강한 지역에서 소규모 풍력사업을 해보려는데, 설치와 운영에 필요한 허가·검사 절차는 어디서 확인하나요? | `other_renewables_project` |
| lay-energy-0963 | 바람이 강한 지역에서 소규모 풍력사업을 해보려는데, 이 설비에서 생산되는 에너지를 직접 쓰거나 판매하려면 어떤 연결과 계약이 필요한가요? | `other_renewables_project` |
| lay-energy-0964 | 바람이 강한 지역에서 소규모 풍력사업을 해보려는데, 기술 특성에 따라 특히 주의해야 할 안전·환경 문제는 무엇인가요? | `other_renewables_project` |
| lay-energy-0965 | 바람이 강한 지역에서 소규모 풍력사업을 해보려는데, 인증이나 지원 대상이 되는지 어떤 기준으로 확인하나요? | `other_renewables_project` |
| lay-energy-0966 | 지열을 이용해 전기와 열을 생산하는 사업을 검토 중인데, 사업 가능성을 판단하려면 어떤 자원과 입지 조건을 확인해야 하나요? | `other_renewables_project` |
| lay-energy-0967 | 지열을 이용해 전기와 열을 생산하는 사업을 검토 중인데, 설치와 운영에 필요한 허가·검사 절차는 어디서 확인하나요? | `other_renewables_project` |
| lay-energy-0968 | 지열을 이용해 전기와 열을 생산하는 사업을 검토 중인데, 이 설비에서 생산되는 에너지를 직접 쓰거나 판매하려면 어떤 연결과 계약이 필요한가요? | `other_renewables_project` |
| lay-energy-0969 | 지열을 이용해 전기와 열을 생산하는 사업을 검토 중인데, 기술 특성에 따라 특히 주의해야 할 안전·환경 문제는 무엇인가요? | `other_renewables_project` |
| lay-energy-0970 | 지열을 이용해 전기와 열을 생산하는 사업을 검토 중인데, 인증이나 지원 대상이 되는지 어떤 기준으로 확인하나요? | `other_renewables_project` |
| lay-energy-0971 | 농업 부산물로 바이오에너지를 생산하려는데, 사업 가능성을 판단하려면 어떤 자원과 입지 조건을 확인해야 하나요? | `other_renewables_project` |
| lay-energy-0972 | 농업 부산물로 바이오에너지를 생산하려는데, 설치와 운영에 필요한 허가·검사 절차는 어디서 확인하나요? | `other_renewables_project` |
| lay-energy-0973 | 농업 부산물로 바이오에너지를 생산하려는데, 전기·열·가스·연료 중 무엇을 만들지에 따라 연결과 판매 계약이 어떻게 달라지나요? | `other_renewables_project` |
| lay-energy-0974 | 농업 부산물로 바이오에너지를 생산하려는데, 기술 특성에 따라 특히 주의해야 할 안전·환경 문제는 무엇인가요? | `other_renewables_project` |
| lay-energy-0975 | 농업 부산물로 바이오에너지를 생산하려는데, 인증이나 지원 대상이 되는지 어떤 기준으로 확인하나요? | `other_renewables_project` |
| lay-energy-0976 | 하천의 물을 이용한 작은 발전설비를 검토 중인데, 사업 가능성을 판단하려면 어떤 자원과 입지 조건을 확인해야 하나요? | `other_renewables_project` |
| lay-energy-0977 | 하천의 물을 이용한 작은 발전설비를 검토 중인데, 설치와 운영에 필요한 허가·검사 절차는 어디서 확인하나요? | `other_renewables_project` |
| lay-energy-0978 | 하천의 물을 이용한 작은 발전설비를 검토 중인데, 이 설비에서 생산되는 에너지를 직접 쓰거나 판매하려면 어떤 연결과 계약이 필요한가요? | `other_renewables_project` |
| lay-energy-0979 | 하천의 물을 이용한 작은 발전설비를 검토 중인데, 기술 특성에 따라 특히 주의해야 할 안전·환경 문제는 무엇인가요? | `other_renewables_project` |
| lay-energy-0980 | 하천의 물을 이용한 작은 발전설비를 검토 중인데, 인증이나 지원 대상이 되는지 어떤 기준으로 확인하나요? | `other_renewables_project` |
| lay-energy-0981 | 연료전지 발전소를 산업단지에 설치하려는데, 연료 공급과 전기·열 수요, 입지 조건 중 무엇을 확인해야 하나요? | `other_renewables_project` |
| lay-energy-0982 | 연료전지 발전소를 산업단지에 설치하려는데, 설치와 운영에 필요한 허가·검사 절차는 어디서 확인하나요? | `other_renewables_project` |
| lay-energy-0983 | 연료전지 발전소를 산업단지에 설치하려는데, 이 설비에서 생산되는 에너지를 직접 쓰거나 판매하려면 어떤 연결과 계약이 필요한가요? | `other_renewables_project` |
| lay-energy-0984 | 연료전지 발전소를 산업단지에 설치하려는데, 기술 특성에 따라 특히 주의해야 할 안전·환경 문제는 무엇인가요? | `other_renewables_project` |
| lay-energy-0985 | 연료전지 발전소를 산업단지에 설치하려는데, 인증이나 지원 대상이 되는지 어떤 기준으로 확인하나요? | `other_renewables_project` |
| lay-energy-0986 | 수소를 이용해 전기와 열을 함께 생산하려는데, 수소 공급과 전기·열 수요, 입지 조건 중 무엇을 확인해야 하나요? | `other_renewables_project` |
| lay-energy-0987 | 수소를 이용해 전기와 열을 함께 생산하려는데, 설치와 운영에 필요한 허가·검사 절차는 어디서 확인하나요? | `other_renewables_project` |
| lay-energy-0988 | 수소를 이용해 전기와 열을 함께 생산하려는데, 이 설비에서 생산되는 에너지를 직접 쓰거나 판매하려면 어떤 연결과 계약이 필요한가요? | `other_renewables_project` |
| lay-energy-0989 | 수소를 이용해 전기와 열을 함께 생산하려는데, 기술 특성에 따라 특히 주의해야 할 안전·환경 문제는 무엇인가요? | `other_renewables_project` |
| lay-energy-0990 | 수소를 이용해 전기와 열을 함께 생산하려는데, 인증이나 지원 대상이 되는지 어떤 기준으로 확인하나요? | `other_renewables_project` |
| lay-energy-0991 | 태양광과 풍력 설비를 한 부지에서 같이 운영하려는데, 사업 가능성을 판단하려면 어떤 자원과 입지 조건을 확인해야 하나요? | `other_renewables_project` |
| lay-energy-0992 | 태양광과 풍력 설비를 한 부지에서 같이 운영하려는데, 설치와 운영에 필요한 허가·검사 절차는 어디서 확인하나요? | `other_renewables_project` |
| lay-energy-0993 | 태양광과 풍력 설비를 한 부지에서 같이 운영하려는데, 이 설비에서 생산되는 에너지를 직접 쓰거나 판매하려면 어떤 연결과 계약이 필요한가요? | `other_renewables_project` |
| lay-energy-0994 | 태양광과 풍력 설비를 한 부지에서 같이 운영하려는데, 기술 특성에 따라 특히 주의해야 할 안전·환경 문제는 무엇인가요? | `other_renewables_project` |
| lay-energy-0995 | 태양광과 풍력 설비를 한 부지에서 같이 운영하려는데, 인증이나 지원 대상이 되는지 어떤 기준으로 확인하나요? | `other_renewables_project` |
| lay-energy-0996 | 해상풍력 사업에 지역 업체로 참여하려는데, 지역 업체가 참여할 수 있는 공사·납품 분야는 무엇인가요? | `offshore_wind_local_vendor` |
| lay-energy-0997 | 해상풍력 사업에 지역 업체로 참여하려는데, 맡으려는 업무에 필요한 등록·자격·검사 요건은 어디서 확인하나요? | `offshore_wind_local_vendor` |
| lay-energy-0998 | 해상풍력 사업에 지역 업체로 참여하려는데, 사업자와 납품이나 용역 계약을 맺을 때 무엇을 확인해야 하나요? | `offshore_wind_local_vendor` |
| lay-energy-0999 | 해상풍력 사업에 지역 업체로 참여하려는데, 해상 작업과 설비 시공에서 특히 주의할 안전·환경 문제는 무엇인가요? | `offshore_wind_local_vendor` |
| lay-energy-1000 | 해상풍력 사업에 지역 업체로 참여하려는데, 지역 업체 우대나 참여 지원이 있는지 어디서 확인하나요? | `offshore_wind_local_vendor` |

</details>
