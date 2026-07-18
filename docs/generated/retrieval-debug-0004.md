# Production 검색 디버깅 결과: DB revision 0004

생성 명령: `cmd /d /c ..\..\.venv\Scripts\python.exe -m scripts.debug_retrieval_pipeline --output ..\..\.data\retrieval-debug-after-0004.json` (`apps/api` 기준)  
요약 방식: 위 JSON에서 질문·단계별 시간·후보 메타데이터만 고정하고 법률 원문 전문은 제외  
기준 시점: 2026-07-18  
애플리케이션 commit: `ba9ebcf`  
DB revision: `0004`

## 환경

- 문서 9개
- 버전 9개
- 조항 3,066개
- parser schema 2
- 임베딩 0개
- evaluation run 0개
- 검색 모드: 키워드 전용, 생성 미실행

## 질문별 결과

| ID | 기대 계약 | 결과 | 주요 실행 단계 | 전체 시간 |
|---|---|---|---|---:|
| `natural-storage-standard` | NFPC 607 포함 | 통과 | 모든 핵심어 | 1,211.211ms |
| `natural-business-permit` | 전기사업법 Top 5 포함 | 통과 | 모든 핵심어 | 1,031.311ms |
| `invalid-article-parsing` | 존재하지 않는 직접 경로 근거 부족 | 통과 | 직접 조문 경로 | 93.035ms |
| `ambiguous-filler` | 근거 부족 | 통과 | 모든 핵심어 1회, 중복/앵커 없음 skip | 870.078ms |
| `exact-article-reference` | 전기사업법 제7조 제1항 | 통과 | 직접 조문 경로 | 90.980ms |
| `permit-application-documents` | 전기사업법 시행규칙 포함 | 통과 | 모든 핵심어 | 1,201.232ms |
| `storage-technical-standard` | NFTC 607 포함 | 통과 | 모든 핵심어 | 1,839.442ms |
| `distributed-energy-registration` | 분산에너지 활성화 특별법 포함 | 통과 | 모든 핵심어 1,090.381ms, 최소 2개 4,296.774ms, 앵커 필터 0.015ms | 5,462.805ms |

집계는 8/8 계약 통과, min 90.980ms, p50 1,031.311ms, p95/max 5,462.805ms, 1초 이내 3/8이다. p95는 8개 질문 각 1회의 소표본에서 최댓값과 같으므로 정식 성능 베이스라인으로 사용하지 않는다.

`ambiguous-filler` 10회 반복은 min 864.666ms, p50 872.739ms, p95/max 942.486ms, 1초 이내 10/10이었다. 이 결과는 단일어 근거 부족 경로만 설명하며 복합 검색 전체를 대표하지 않는다.

## 해석 제한

- 통과는 기대 문서 포함 또는 근거 부족 상태 계약이다. Recall@k, MRR/nDCG와 법률 답변 정확성이 아니다.
- `natural-business-permit`의 기대 문서는 5위여서 상위 노이즈가 남아 있다.
- `distributed-energy-registration`은 기대 문서를 찾았지만 정의 조항 등 부분 관련 청크가 섞여 있다.
- AI가 비활성이고 임베딩이 0개라 semantic 검색, RRF 순위 변화와 Terra generation은 검증하지 않았다.
- 상위 5개 청크의 `relevant/partial/noise` 수동 판정은 아직 완료하지 않았다.
- 계획한 30회 예열, 질문별 30회, 전체 300회, cold 10회와 EXPLAIN은 아직 실행하지 않았다.
