# 실험 D 일반 사용자 질문 승인 검토표 v1

> 생성 명령: `uv run --directory apps/api python -m scripts.render_experiment_d_layperson_approval_review`
> 입력 bank: `experiment-d-lay-energy-query-bank-v1-draft` (`draft_for_human_question_review`)
> question set SHA-256: `58be922c4bd9db7bce1360565da9b97de703e3b32c956c11e6a79285ee0b6b32`
> question scope set SHA-256: `f59da0ccf5210bc0c3da527f04e24c85788c4410ddeb55f21eaf4d96369c9db7`
> 범위: 질문 문구 승인 검토만 수행 — 정답·qrels·검색 후보·점수·검색 결과를 생성하지 않음

[전체 1,000문항 읽기본](experiment-d-lay-energy-query-bank-v1.md)

## 이 문서에서 결정할 것

각 질문은 다음 중 하나로 검토한다.

- **유지**: 현재 문구를 질문은행에 남긴다.
- **수정**: 필요한 지역·용량·시점 등 사실을 넣거나 표현을 고친다.
- **제외**: 실험 D 목적과 맞지 않아 질문은행에서 뺀다.
- **대조군으로 유지**: 추가 질문이 필요한 `clarification_required`, 일부만 답할 수 있는 `partially_answerable`, 현재 corpus로 답할 수 없는 `unanswerable` 후보로 남긴다.

여기서 고르는 대조군 유형은 질문 검토 의도일 뿐 최종 정답 라벨이 아니다. 질문 승인 뒤 공식 원문을 검색 결과와 독립적으로 검토하여 answerability와 qrels를 별도 gold에 확정한다.

하나라도 수정하거나 제외하면 현재 두 SHA-256을 승인하지 말고 질문은행 새 버전·해시와 이 검토표를 다시 생성한다.

## 구조 확인

- 질문: 1000개
- scenario family: 200개 × 5문항
- intent: 15개
- 모든 질문 상태: `not_annotated`
- 현재 검토 corpus: 에너지 법령·기술기준 9종
- 현재 corpus 지원 기준일: `2026-06-03` ~ `2026-08-03` (양끝 포함)

## Intent별 대표 질문 15개

| Intent | ID | 질문 |
|---|---|---|
| 사업 시작·전체 절차 | `lay-energy-0001` | 태양광 발전사업을 처음 해보려고 하는데, 무엇부터 준비해야 하나요? |
| 부지·건물·토지 이용 | `lay-energy-0111` | 시골에 가진 땅에 태양광을 설치해도 되는지 알아보는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? |
| 허가·신고·서류 | `lay-energy-0201` | 태양광 발전소 허가를 준비하고 있는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? |
| 계통연계·한전 계약 | `lay-energy-0291` | 태양광 발전소를 전력망에 연결하려는데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? |
| 시공·설비·인증 | `lay-energy-0381` | 태양광 시공업체를 처음 고르려는데, 업체의 자격과 실적을 어떻게 확인해야 하나요? |
| 검사·안전·고장·재난 | `lay-energy-0441` | 발전설비 공사를 마치고 사용을 시작하려는데, 어떤 검사를 언제 신청해야 하나요? |
| 수익·SMP·REC·정산 | `lay-energy-0511` | 태양광으로 만든 전기를 어떤 방식으로 팔지 고민인데, 가능한 판매와 계약 방식은 어떻게 다른가요? |
| 보조금·융자·지원 | `lay-energy-0601` | 태양광 설치비 지원을 받을 수 있는지 알아보는데, 지원 대상인지 어떤 조건으로 판단하나요? |
| 전기요금·계약전력·생활민원 | `lay-energy-0671` | 본인 소유 가게를 새로 열어 전기를 신청하려는데, 어디에 신청하고 어떤 순서로 처리하나요? |
| 주택 태양광·소비자보호 | `lay-energy-0741` | 우리 집 지붕에 태양광을 달고 싶은데, 설치 가능한지와 예상 발전량을 무엇으로 확인하나요? |
| 전기차 충전 | `lay-energy-0796` | 아파트에 공용 전기차 충전기를 설치하려는데, 누구의 동의를 받고 어떤 장소 조건을 확인해야 하나요? |
| ESS | `lay-energy-0846` | 태양광 발전소에 배터리 저장장치를 추가하려는데, 설치 전에 어떤 신고·검사·확인이 필요한가요? |
| 분산에너지·직접거래·VPP·RE100 | `lay-energy-0881` | 우리 지역에서 만든 전기를 지역 기업에 직접 팔고 싶은데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? |
| 주민·환경·철거·폐기 | `lay-energy-0921` | 마을 근처에 태양광 발전소를 짓겠다는 설명을 들었는데, 사업 내용과 예상 영향을 어떤 자료로 확인할 수 있나요? |
| 기타 재생에너지 | `lay-energy-0961` | 바람이 강한 지역에서 소규모 풍력사업을 해보려는데, 사업 가능성을 판단하려면 어떤 자원과 입지 조건을 확인해야 하나요? |

## 고위험 질문 35개

아래 분류는 삭제 결론이나 gold 정답이 아니다. 현재 문구를 그대로 승인하기 전에 사람이 읽어야 할 이유를 고정한 검토 목록이다.

### 질문이 넓거나 추가 사실이 필요한 후보 — 14개 (`broad_or_missing_facts`)

| ID | 질문 | 검토가 필요한 이유 | 사용자 결정 |
|---|---|---|---|
| `lay-energy-0001` | 태양광 발전사업을 처음 해보려고 하는데, 무엇부터 준비해야 하나요? | 허가·부지·계통·검사·판매까지 여러 필수 답변 요소를 포함할 수 있어 답의 경계가 넓다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0002` | 태양광 발전사업을 처음 해보려고 하는데, 부지 확인부터 전기 판매까지 어떤 순서로 진행하나요? | 부지 확인부터 전기 판매까지 사업 생애주기 전체를 한 질문에서 요구한다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0084` | 제가 쓸 전기만 만들지 남는 전기를 판매할지 고민인데, 비용·절감액·판매수익은 어떤 기준으로 비교해야 하나요? | 비용·절감액·판매수익 비교에는 설비 규모, 사용량, 가격과 금융조건이 더 필요하다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0101` | 사업계획은 있지만 어느 기관부터 찾아가야 할지 모르겠는데, 첫 상담은 어디에 요청하는 것이 좋나요? | 첫 상담기관은 지역, 용량, 자가사용·판매 여부와 사업 단계에 따라 달라질 수 있다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0111` | 시골에 가진 땅에 태양광을 설치해도 되는지 알아보는데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | 소재지, 지목, 용도지역과 면적이 없어 특정 부지의 가능 여부를 확정할 수 없다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0116` | 농사를 짓는 땅 일부를 발전사업에 활용하고 싶은데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | 농지 종류, 농업인 여부, 소재지와 용도지역이 없어 토지 이용 판단이 달라질 수 있다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0171` | 문화재나 보호구역과 가까운 부지를 검토 중인데, 이 장소에서 사업이 가능한지 무엇을 확인해야 하나요? | 보호구역의 종류, 정확한 위치와 이격거리가 없어 적용 절차를 특정하기 어렵다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0201` | 태양광 발전소 허가를 준비하고 있는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요? | 발전원, 용량, 자가사용·판매 방식과 신청 주체에 따라 허가·신고가 달라질 수 있다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0251` | 소규모 설비는 용량이나 전기 사용 방식에 따라 허가와 신고가 어떻게 달라지나요? | ‘소규모’의 실제 용량과 전기 사용 방식이 제시되지 않았다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0291` | 태양광 발전소를 전력망에 연결하려는데, 연결 가능 여부를 언제 어떻게 확인해야 하나요? | 연결 가능성은 발전소 위치, 출력, 접속점과 현재 계통 여유 정보가 필요하다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0441` | 발전설비 공사를 마치고 사용을 시작하려는데, 어떤 검사를 언제 신청해야 하나요? | 검사 종류와 시점은 설비 종류, 전압·용량과 공사 범위에 따라 달라질 수 있다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0741` | 우리 집 지붕에 태양광을 달고 싶은데, 설치 가능한지와 예상 발전량을 무엇으로 확인하나요? | 지붕 구조·면적·방향·그늘, 지역과 전기사용량이 없어 가능성과 발전량을 판단하기 어렵다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0846` | 태양광 발전소에 배터리 저장장치를 추가하려는데, 설치 전에 어떤 신고·검사·확인이 필요한가요? | 배터리 종류·용량, 실내외 설치와 기존 설비 변경 범위가 제시되지 않았다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0961` | 바람이 강한 지역에서 소규모 풍력사업을 해보려는데, 사업 가능성을 판단하려면 어떤 자원과 입지 조건을 확인해야 하나요? | 풍황 실측, 필지, 설비 규모, 계통과 환경 조건이 없어 사업 가능성을 확정할 수 없다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |

### 시점·실시간·개인 데이터가 필요한 후보 — 8개 (`time_or_live_data`)

| ID | 질문 | 검토가 필요한 이유 | 사용자 결정 |
|---|---|---|---|
| `lay-energy-0351` | 전력망 연결 신청 후 오랫동안 순서를 기다리고 있는데, 현재 대기 순서와 예상 연결 시점을 어디서 확인하나요? | 현재 대기 순서와 예상 연결 시점은 법령 원문이 아니라 전력회사의 실시간 사업 데이터다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0550` | 고정가격 계약과 시장가격에 따라 파는 방식 중 무엇이 나은지 궁금한데, 최신 시장가격과 계약 조건은 어디서 확인하나요? | 최신 시장가격과 계약조건은 기준일 및 당시 시장·계약 자료가 필요하다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0605` | 태양광 설치비 지원을 받을 수 있는지 알아보는데, 올해 예산과 세부 조건은 어디서 최신 정보를 확인하나요? | 올해 예산과 세부 조건은 법률보다 해당 연도의 지원사업 공고가 직접 근거다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0641` | 지원사업 예산이 소진됐다는 안내를 받았는데, 접수가 끝난 것인지 대기 신청이 가능한지 어디서 확인하나요? | 예산 소진과 대기접수 가능 여부는 해당 사업의 현재 운영 상태다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0646` | 지난해와 올해 지원 조건이 달라졌는데, 제 신청에는 어느 연도의 조건이 적용되나요? | 신청일, 적용 공고와 경과규정이 없어 어느 연도 조건인지 확정하기 어렵다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0731` | 에너지바우처 잔액과 사용기한이 궁금한데, 남은 금액은 어디서 확인하나요? | 바우처 잔액과 사용기한은 기준일과 본인 인증이 필요한 개인 계정 데이터다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0800` | 아파트에 공용 전기차 충전기를 설치하려는데, 설치비와 지원 조건은 어디서 최신 정보를 확인하나요? | 충전기 설치비와 지원조건은 연도, 지자체와 사업 공고에 따라 바뀐다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0836` | 충전기가 자주 고장 나 이용하지 못하고 있는데, 고장 상태와 복구 예정 시간을 어디서 확인하나요? | 고장 상태와 복구 예정 시간은 충전기 운영사의 실시간 운영 데이터다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |

### 현재 9종 corpus 밖 근거가 핵심일 가능성이 큰 후보 — 13개 (`outside_corpus`)

| ID | 질문 | 검토가 필요한 이유 | 사용자 결정 |
|---|---|---|---|
| `lay-energy-0381` | 태양광 시공업체를 처음 고르려는데, 업체의 자격과 실적을 어떻게 확인해야 하나요? | 시공업체 자격은 전기공사업 관련 법령, 실적은 업체 등록·실적 자료가 핵심이다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0671` | 본인 소유 가게를 새로 열어 전기를 신청하려는데, 어디에 신청하고 어떤 순서로 처리하나요? | 신규 전기사용 신청 순서는 전력회사 공급약관과 업무 절차에 주로 의존한다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0726` | 에너지바우처를 처음 신청하려는데, 지원 대상과 이용 조건을 어디서 확인하나요? | 에너지바우처 대상과 이용조건은 현재 9종 corpus 밖의 사업 법령·공고가 필요하다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0756` | 무료 설치라는 태양광 영업 전화를 받았는데, 무료나 절감 보장이 사실인지 어떤 자료로 확인하나요? | 무료 설치와 절감 보장은 소비자계약 및 실제 제안서 검토가 핵심이다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0766` | 설치업체가 계약금을 받은 뒤 연락이 되지 않는데, 계약과 입금 사실을 증명하려면 어떤 자료를 모아야 하나요? | 계약금 편취 대응은 민사·소비자·형사 영역이며 현재 9종 corpus에 직접 근거가 없다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0796` | 아파트에 공용 전기차 충전기를 설치하려는데, 누구의 동의를 받고 어떤 장소 조건을 확인해야 하나요? | 공동주택 동의와 주차장·건축·충전시설 규정은 현재 9종 corpus 밖 근거가 필요하다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0826` | 충전카드를 발급받고 요금을 결제하려는데, 내 계정과 충전 이용 내역은 어디서 확인하나요? | 충전카드 계정과 사용내역은 충전사업자 시스템의 개인 데이터다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0881` | 우리 지역에서 만든 전기를 지역 기업에 직접 팔고 싶은데, 누가 참여할 수 있고 어떤 등록이나 계약이 필요한가요? | 분산에너지법 일부 외에도 지역 지정 여부와 실제 등록·거래계약 정보가 필요할 수 있다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0911` | 우리 회사가 쓰는 전기를 재생에너지로 바꾸려는데, 회사 규모와 전기 계약 형태에 따라 어떤 재생전기 구매 방식과 계약을 이용할 수 있나요? | 재생전기 구매상품과 계약은 시장 운영규칙 및 현재 상품정보가 필요할 수 있다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0921` | 마을 근처에 태양광 발전소를 짓겠다는 설명을 들었는데, 사업 내용과 예상 영향을 어떤 자료로 확인할 수 있나요? | 특정 발전소의 사업 내용과 예상 영향은 해당 사업계획·영향 자료가 필요하다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0926` | 마을 근처 풍력발전기의 소음과 그림자가 걱정되는데, 사업 내용과 예상 영향을 어떤 자료로 확인할 수 있나요? | 풍력 소음·그림자는 환경·입지 규정과 해당 사업의 영향자료가 핵심이다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0956` | 수명이 끝난 태양광 패널과 설비를 철거·폐기하려는데, 설비 소유자와 철거 책임자를 어떻게 확인하나요? | 패널과 발전설비의 철거·폐기는 폐기물 관련 법령이 핵심이지만 현재 corpus에 없다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |
| `lay-energy-0996` | 해상풍력 사업에 지역 업체로 참여하려는데, 지역 업체가 참여할 수 있는 공사·납품 분야는 무엇인가요? | 해상풍력 공사·납품 분야는 발주·조달·산업정책 자료가 핵심이다. | 유지 / 수정 / 제외 / clarification_required / partially_answerable / unanswerable 대조군 |

## 승인 전 최종 확인

- [ ] 대표 15문항을 모두 읽었다.
- [ ] 고위험 35문항 각각에 유지·수정·제외 또는 대조군 의도를 정했다.
- [ ] 범위 밖 질문을 의도적인 안전성 대조군으로 둘 비율을 확인했다.
- [ ] `최신`·`올해`·`현재` 질문의 기준일 또는 동적 데이터 취급을 정했다.
- [ ] 수정·제외가 있으면 현재 해시를 승인하지 않고 새 버전을 만들기로 했다.
- [ ] 수정이 없다면 전체 1,000문항 읽기본과 두 SHA-256이 같은지 확인했다.

## 고정 식별자

- bank version: `experiment-d-lay-energy-query-bank-v1-draft`
- bank status: `draft_for_human_question_review`
- question count: `1000`
- question set SHA-256: `58be922c4bd9db7bce1360565da9b97de703e3b32c956c11e6a79285ee0b6b32`
- question scope set SHA-256: `f59da0ccf5210bc0c3da527f04e24c85788c4410ddeb55f21eaf4d96369c9db7`
- [전체 1,000문항 읽기본](experiment-d-lay-energy-query-bank-v1.md)
