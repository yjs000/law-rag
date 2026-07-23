# 실행 계획 0018: 실험 C — 로컬 10청크 벡터 검색

상태: 완료
작성일: 2026-07-23
소유자: 주 에이전트

## 목적과 사용자 결과

사용자가 지정한 국가법령정보센터 링크 세 개를 법령 식별 단서로만 사용하고, 실제 원문은 기존
국가법령정보 공동활용 Open API client와 JSON 우선/XML 폴백 파서로 수집한다. 기존 조문 구조 청킹과
NVIDIA NIM 임베더를 재사용해 문서 조각 10개를 로컬에 저장한다. 이후 사용자가 질문을 입력하면 같은
모델의 query embedding으로 코사인 유사도를 계산해 상위 3개 조문과 점수를 터미널 JSON으로 출력한다.

## 입력과 가정

- 현재 저작권법: 사용자가 제공한 법령명 링크를 현재 Open API 검색으로 해석한다.
- 전기사업법: `lsiSeq=180380`을 과거 MST 180380, 시행 2016-07-28 버전으로 해석한다.
- 현재 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법: 법령명 링크를 현재 Open API 검색으로 해석한다.
- HTML 페이지 본문은 코퍼스로 사용하지 않는다. Open API 응답 URL, wire format, 원문 SHA-256,
  source ID, MST와 시행일을 청크에 추적한다.
- 10개 제한에서 세 법을 비교할 수 있도록 저작권법 3개, 전기사업법 4개, 신재생에너지법 3개 조문을
  선택한다. 선택 경로는 코드 상수와 생성 데이터에 명시한다.
- 실험 코퍼스는 MVP 운영 허용 목록을 확장하지 않으며 production DB나 Supabase를 변경하지 않는다.

## 범위와 비범위

범위:

- 기존 `LawOpenApiClient.document()`와 공용 `law_json`/`law_xml` 파서 재사용
- 파서가 만든 조문 청크 중 지정 경로 10개 선택
- 기존 `NvidiaNimEmbedder`를 passage/query 설정으로 각각 재사용
- `.data/experiments/search/corpus.json`에 10개 청크와 512차원 벡터 저장
- 질문 한 개의 cosine top 3와 점수·법령명·MST·조문 경로·원문 출력
- 정상·실패·경계 테스트와 학습·실행 안내 문서

비범위:

- HTML/PDF 크롤링
- production corpus, PostgreSQL, pgvector, Supabase 변경
- 검색 결과를 사용한 생성 답변 또는 법률 해석
- 실험 결과를 검색 임계값이나 품질 보장으로 확정
- 실험 B 사용자가 만든 미커밋 실행 이력 변경

## 완료 조건

- 준비 명령 한 번으로 정확히 3개 Open API 문서를 파싱하고 지정 조문 10개를 저장한다.
- 각 저장 청크는 source ID, MST, 시행일, Open API URL, 원문 해시, path, heading, content를 가진다.
- passage embedding은 기존 NVIDIA adapter의 2048 검증→앞 512개→L2 재정규화를 그대로 사용한다.
- 질문은 query embedding으로 만들고 10개 청크에 cosine을 계산해 내림차순 상위 3개만 출력한다.
- 점수는 유한한 `[-1, 1]` 값이며 순위 동률은 안정적인 chunk ID로 결정한다.
- 준비 실패는 기존 corpus를 덮어쓰지 않고, 질문·키·provider 오류 전문을 저장하거나 출력하지 않는다.
- 관련 테스트, Ruff, 문서 검사와 전체 검증이 통과한다.

## 단계와 TODO

### 주 에이전트

- [x] M1 — 새 실험 CLI와 원자적 로컬 corpus 저장
- [x] M2 — 기존 Open API 파서·청커와 NVIDIA passage/query 임베더 연결
- [x] M3 — cosine top 3 검색과 대화형 질문 입력
- [x] M4 — 정상·누락·손상·실패 테스트
- [x] M5 — live Open API 수집과 10청크 NVIDIA 임베딩 생성
- [x] M6 — 실행 안내·학습 문서·최종 검증

### 하위 에이전트

- 사용하지 않는다. 수집 결과 스키마, 임베딩 저장 계약과 검색 CLI가 한 파일 경계를 공유하므로 주
  에이전트가 순차 구현·검증한다.

## 검증과 롤백

```powershell
uv run --directory apps/api python -m pytest tests/test_search_experiment.py -q
uv run --directory apps/api ruff check app scripts tests
uv run python scripts/check_docs.py
pnpm.cmd verify
```

로컬 corpus는 `.data/experiments/search/` 아래에만 생성한다. 준비가 실패하면 임시 파일을 제거하고 기존
corpus를 유지한다. 롤백은 새 실험 스크립트·테스트·문서를 되돌리고 로컬 생성 디렉터리를 삭제하는
것이며 production 데이터에는 영향이 없다.

## 결정 로그

- 2026-07-23: 사용자 링크는 식별 단서로만 사용하고 코퍼스 본문은 Open API로 제한한다.
- 2026-07-23: 10청크를 세 법에 3/4/3으로 배분해 단일 법령 편중을 피한다.
- 2026-07-23: 저장은 로컬 JSON, 검색은 exhaustive cosine으로 구현하되 기존 parser와 embedder를
  그대로 재사용한다. 10개 규모에서는 별도 DB·ANN 색인이 필요하지 않다.
- 2026-07-23: 질문은 저장하지 않고 터미널에서만 처리한다.
- 2026-07-23: live 파서 점검에서 일부 최상위 조문 레코드가 장·절 표제 또는 조문 제목만 담는 것을
  확인했다. 청커를 변경하거나 내용을 합치지 않고, 기존 파서가 만든 의미 있는 항·호 경로를 10개
  선택하도록 수정한다.

## 진행 기록

- 2026-07-23: 기존 미커밋 실험 B 결과와 active README를 보존 대상으로 확인했다.
- 2026-07-23: 제공 URL이 저작권법, 전기사업법 과거 MST 180380, 신재생에너지법임을 공식 화면에서
  확인했으며 본문 수집에는 사용하지 않기로 했다.
- 2026-07-23: 첫 live 준비와 smoke 검색에서 `제7조`가 허가 본문이 아닌 장·절 표제임을 발견했다.
  실제 허가 본문인 `제7조/항①` 등 기존 하위 청크 경로로 선택을 교정한다.
- 2026-07-23: 교정한 10개 경로를 Open API에서 다시 수집하고 passage embedding을 생성해
  `.data/experiments/search/corpus.json`에 저장했다. 10개 모두 512차원이며 최대 norm 오차는
  `1.11e-16`이었다.
- 2026-07-23: `전기사업을 하려면 누구의 허가를 받아야 하나?` smoke 질문에서 제7조제1항,
  제10조제1항, 제8조 순으로 상위 3개가 출력돼 query→cosine→top 3 경로를 확인했다.
- 2026-07-23: 전체 검증에서 core 4개, API 233개 통과·환경 의존 2개 skip, collector 34개,
  web 46개 테스트와 Ruff, 문서 검사, TypeScript, Next.js build가 통과했다.

## 잔여 한계

- 10개 청크와 한 smoke 질문은 검색 품질 평가셋이 아니다. score 임계값과 production 검색 품질은
  별도 관련·비관련 질문셋으로 평가해야 한다.
- 로컬 corpus는 현재 PC의 `.data`에만 있으며 Git clone이나 다른 PC에는 자동 복제되지 않는다.

## 완료 결과

기존 Open API client, 공용 parser와 NVIDIA embedder를 바꾸지 않고 실험 C로 연결했다. 현재 로컬에는
세 법령에서 선택한 기존 조·항·호 청크 10개와 passage embedding이 준비돼 있다. 사용자는 `ask`
명령에서 질문을 입력하면 query embedding과 10개 cosine 전수 계산 결과의 상위 3개를 원문·점수와
함께 볼 수 있다. production DB와 기존 미커밋 실험 B 결과는 변경하지 않았다.
