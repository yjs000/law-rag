# 일반 사용자형 에너지 질문 주제 참고 자료

확인일: 2026-08-03

## 사용 목적과 한계

이 자료는 일반 사용자가 에너지 분야에서 궁금해할 **질문 의도와 생활 맥락을 발견하기 위한 참고 목록**이다. 아래 페이지의 주제 범주와 업무 흐름만 참고해 별도의 질문을 합성한다.

- 공개 FAQ의 질문 문구나 답변을 복사하지 않는다.
- 이용자 게시물, 신청 정보, 연락처 등 개인정보를 수집하거나 저장하지 않는다.
- 이 목록은 검색량·문의량·질문 빈도를 보여 주는 통계 자료가 아니다. 따라서 어떤 질문이 더 흔하다는 근거로 사용하지 않는다.
- 아래 페이지를 법률 답변의 정답, 인용 근거 또는 평가용 정답 문서로 사용하지 않는다. 법률 답변의 근거는 프로젝트가 허용한 국가법령정보 공동활용 Open API 코퍼스에서 별도로 검증한다.
- 지원금, 요금, 신청 기간, 지역별 조건처럼 바뀔 수 있는 내용은 고정 정답으로 만들지 않는다.
- 생성된 질문은 정답·qrels가 없는 검토 초안이다. `evaluation_annotation_status=not_annotated`는 평가용 정답 라벨이 아직 없다는 뜻이다. 출처 ID는 질문별 근거가 아니라 연구 주제 수준의 참고 목록이며, 해당 페이지가 각 질문에 답한다는 표시가 아니다.
- 이 초안만으로는 Recall·MRR 같은 검색 정확도를 계산할 수 없다. 질문 승인 후 허용된 법률 corpus에서 answerability와 직접 근거 qrels를 독립적으로 주석해야 한다.

## 공식 공개 자료와 참고 주제

| 출처 ID | 운영 기관·자료 | 질문 의도 설계에 참고한 주제 |
| --- | --- | --- |
| `knrec_general_faq` | [한국에너지공단 신·재생에너지센터 일반 FAQ](https://www.knrec.or.kr/biz/faq/faq_list02.do?depth_1=&depth_2=&page=2) | 신재생에너지 사업 시작, 설비·인증, 보급 지원, 주택용 설비, 민원과 일반 절차 |
| `knrec_rps_faq` | [한국에너지공단 신·재생에너지센터 RPS FAQ](https://www.knrec.or.kr/biz/faq/faq_list02.do?depth_1=A030000&depth_2=A030300&depth_3=&page=2) | 발전사업자의 RPS 참여, 공급인증서, 설비 확인, 거래 전 준비사항 |
| `knrec_rec_process` | [한국에너지공단 공급인증서 발급 및 거래 절차](https://www.knrec.or.kr/biz/introduce/new_rps/intro_cert_submit.do?gubun=C) | REC 발급 신청, 처리 흐름, 거래 전후 단계와 필요한 확인사항 |
| `kepco_distributed_steps` | [한국전력공사 분산형 전원 계통연계 절차](https://cyber.kepco.co.kr/ckepco/mobile/resources/resources_step.jsp) | 계통 접속 가능 여부, 접속 신청, 공사·검토 순서, 발전설비 연계 지연 |
| `kepco_service_application` | [한국전력공사 전기사용 신청 및 계약 안내](https://home.kepco.co.kr/kepco/front/html/CY/D/C/CYDCHP00102.html) | 전기사용 신청, 계약 변경, 명의·용도·용량 변경, 준비 서류와 처리 절차 |
| `kepco_service_charter` | [한국전력공사 전력서비스 헌장](https://home.kepco.co.kr/kepco/front/html/CY/H/A/CYHAHP001.html) | 정전·고장 대응, 고객 서비스, 처리 기준과 이용자 문의 맥락 |
| `kpx_faq` | [전력거래소 고객지원 FAQ](https://kpx.or.kr/board.es?bid=0047&mid=a10504020000) | 전력시장 참여, 전력 거래, SMP·REC, 소규모 전력중개와 정산 문의 |
| `kesco_preuse_inspection` | [한국전기안전공사 사용전검사 안내](https://safety.kesco.or.kr/cyber/cr/ubi/moveUseBfeInspctStep01.do) | 설비 가동 전 검사, 신청 시점, 준비 자료, 검사 불합격과 보완 |
| `knrec_safety` | [한국에너지공단 재생에너지 설비 안전관리 안내](https://www.knrec.or.kr/biz/introduce/new_policy/intro_energysafety.do?gubun=D) | 태풍·화재·침수 대비, 정기 점검, 사고 예방, 피해 발생 후 대응 |
| `knrec_fraud_relief` | [한국에너지공단 태양광 피해 예방·지원 안내](https://www.knrec.or.kr/biz/pds/notice/view.do?no=2581) | 허위·과장 계약, 시공업체 확인, 계약 해지·분쟁, 피해 상담과 예방 |
| `ev_portal` | [무공해차 통합누리집](https://ev.or.kr/nportal/main.do) | 전기차 충전기 설치, 이용, 보조사업, 고장·공동주택 갈등과 운영 문의 |
| `ev_charger_guide_2026` | [2026년 공용 완속충전시설 설치 안내서](https://www.ev.or.kr/nportal/file/pdf/guideDownload.pdf) | 공용 완속충전기 신청 주체, 설치 장소, 현장 조건, 신청·시공 흐름 |
| `energy_voucher_faq` | [에너지바우처 FAQ](https://www.energyv.or.kr/board/boardList.do?mstBoardId=44) | 지원 대상·신청·사용, 이사·가구 변경, 잔액과 이용 문제 |
| `motie_distributed_zone` | [산업통상자원부 분산에너지 특화지역 가이드라인](https://www.motie.go.kr/kor/article/ATCLf724eb567/211968/view) | 지역 전력사업, 분산에너지 특화지역, 지역 내 거래와 사업 참여 가능성 |
| `law_solar_permit_interpretation` | [국가법령정보센터 태양광 복합 인허가 관련 법령해석례](https://www.law.go.kr/DRF/lawService.do?ID=328431&OC=unicpla&mobileYn=Y&target=expc&type=HTML) | 태양광 부지와 복수 인허가가 얽히는 생활 질문, 담당 기관과 확인 순서 |

## 질문은행에 적용하는 원칙

1. 기관별 FAQ 분류와 절차에서 `사업 시작`, `부지`, `인허가`, `계통연계`, `검사·안전`, `수익·거래`, `지원`, `전기요금`, `주택용 태양광`, `전기차 충전`, `ESS`, `분산에너지`, `주민·환경`, `철거`, `기타 재생에너지` 같은 의도를 추출한다.
2. 법률명이나 조문 번호를 아는 사람의 표현 대신 “태양광 사업을 시작하려면 무엇부터 준비하나요?”처럼 상황과 목적을 말하는 일반 사용자 표현으로 새로 작성한다.
3. 하나의 출처가 하나의 정답을 뜻하지 않도록 여러 출처의 업무 흐름을 교차 참고한다.
4. 향후 사람이 질문을 검토하고 근거를 붙이기 전까지 모든 질문은 `not_annotated` 상태로 유지한다.
5. 질문은행 승인 전에는 검색·임베딩 평가를 실행하지 않는다.
6. 승인된 질문을 평가에 쓰려면 검색기의 현재 상위 결과를 정답으로 복사하지 않고, 별도 gold 파일에 근거 조문과 필수 답변 요소를 사람 검토로 확정한다.
