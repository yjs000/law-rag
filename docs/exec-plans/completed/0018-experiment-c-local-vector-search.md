# 실행 계획 0018: 실험 C — 기존 전체 청크 로컬 벡터 검색

상태: 완료
작성일: 2026-07-23
소유자: 주 에이전트

## 목적과 사용자 결과

사용자가 지정한 국가법령정보센터 링크 세 개를 식별 단서로 사용하고, 실제 원문은 기존 국가법령정보
공동활용 Open API client와 JSON 우선/XML 폴백 파서로 수집한다. 기존 파서가 반환한 모든 청크를 기존
NVIDIA NIM 임베더로 저장한다. 질문을 입력하면 같은 모델의 query embedding으로 전체 corpus의
코사인 유사도를 계산해 상위 3개 조문과 점수를 터미널 JSON으로 출력한다.

## 입력과 가정

- 저작권법과 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법은 prepare 시점의 현행 버전을 쓴다.
- 전기사업법 `lsiSeq=180380`은 과거 MST 180380, 시행 2016-07-28 버전으로 고정한다.
- 화면 HTML은 corpus로 사용하지 않는다. Open API 응답의 source ID, MST, 시행일, wire format, 원문
  SHA-256과 parser version을 청크에 추적한다.
- 청크 수를 10개로 제한하지 않는다. 기존 파서가 세 문서에서 반환한 결과를 선별·병합 없이 모두 쓴다.
- 실험 corpus는 MVP 운영 허용 목록을 확장하지 않고 production DB나 Supabase를 변경하지 않는다.

## 범위와 비범위

범위:

- 기존 `LawOpenApiClient.document()`와 공용 `law_json`/`law_xml` 파서 재사용
- 파서가 만든 전체 청크를 반환 순서대로 사용
- 기존 `NvidiaNimEmbedder`를 passage/query 설정으로 재사용
- 전체 청크와 512차원 벡터를 `.data/experiments/search/corpus.json`에 저장
- 질문의 exhaustive cosine top 3와 점수·법령명·MST·path·원문 출력
- 동적 청크 수, 배치, 누락·손상·실패 테스트와 학습·실행 안내 갱신

비범위:

- 새 청킹 규칙, 기존 청크 필터링·병합
- HTML/PDF 크롤링
- production corpus, PostgreSQL, pgvector, Supabase 변경
- 검색 결과를 사용한 생성 답변 또는 법률 해석
- 실험 B 사용자가 만든 미커밋 실행 이력 변경

## 완료 조건

- 준비 명령 한 번으로 세 Open API 문서를 파싱하고 기존 파서의 모든 청크를 저장한다.
- 각 저장 청크는 source ID, MST, 시행일, Open API URL, 원문 해시, path, heading, content를 가진다.
- passage embedding은 기존 NVIDIA adapter의 2048 검증→앞 512개→L2 재정규화를 그대로 사용한다.
- 전체 청크는 작은 batch로 기존 embedder에 전달하고, 결과의 개수·차원·유한값을 검증한다.
- 질문은 query embedding으로 만들고 전체 청크의 cosine을 계산해 내림차순 상위 3개만 출력한다.
- 준비 실패는 기존 corpus를 덮어쓰지 않고 질문·키·provider 오류 전문을 저장하거나 출력하지 않는다.
- 관련 테스트, Ruff, 문서 검사와 전체 검증이 통과한다.

## 단계와 TODO

### 주 에이전트

- [x] M1 — 실험 CLI와 원자적 로컬 corpus 저장
- [x] M2 — 기존 Open API 파서와 NVIDIA passage/query 임베더 연결
- [x] M3 — cosine top 3 검색과 대화형 질문 입력
- [x] M4 — 10개 선별을 제거하고 기존 파서의 전체 청크를 batch embedding하도록 교정
- [x] M5 — 동적 청크 수·빈 파서 결과·배치 경계 테스트와 문서 갱신
- [x] M6 — live Open API 전체 수집·NVIDIA 임베딩과 최종 검증

### 하위 에이전트

- 사용하지 않는다. 수집 결과 스키마, embedding 저장 계약과 CLI가 한 파일 경계를 공유해 주 에이전트가
  순차 구현·검증한다.

## 검증과 롤백

```powershell
uv run --directory apps/api python -m pytest tests/test_search_experiment.py -q
uv run --directory apps/api ruff check app scripts tests
uv run python scripts/check_docs.py
pnpm.cmd verify
```

로컬 corpus는 `.data/experiments/search/` 아래에만 생성한다. 세 원문과 모든 embedding이 완성된 후
임시 파일을 원자 교체하므로, 중간 실패 시 이전 corpus가 유지된다. 롤백은 실험 스크립트·테스트·문서
변경을 되돌리는 것이며 production 데이터에는 영향이 없다.

## 결정 로그

- 2026-07-23: 사용자 링크는 식별 단서로만 쓰고 corpus 본문은 Open API로 제한한다.
- 2026-07-23: 저장은 로컬 JSON, 검색은 exhaustive cosine으로 구현하고 기존 parser와 embedder를
  그대로 재사용한다.
- 2026-07-23: 질문은 저장하지 않고 터미널에서만 처리한다.
- 2026-07-23: 처음에는 요구를 “10개를 골라 저장”으로 해석했으나, 사용자가 “정확히 10개가 아니며
  기존 방식으로 그냥 청크하고 임베딩”하라고 교정했다. 따라서 경로 선택 상수와 10개 검증을 제거하고
  parser 반환값 전체를 저장한다.
- 2026-07-23: 청킹 의미를 바꾸지 않으면서 큰 단일 API 요청을 피하려고 embedding 호출만 기본 32개
  batch로 나눈다.

## 진행 기록

- 2026-07-23: 기존 미커밋 실험 B 결과와 active README를 보존 대상으로 확인했다.
- 2026-07-23: 첫 구현과 10개 corpus는 별도 커밋으로 남았으며 이번 교정을 별도 커밋으로 분리한다.
- 2026-07-23: 전체 parser 출력 사용과 batch embedding 단위 테스트 9개, Ruff 대상 검사를 통과했다.
- 2026-07-23: live prepare로 저작권법 950개, 전기사업법 703개, 신재생에너지법 353개, 합계
  2,006개 청크를 저장했다. 모든 벡터는 512차원이고 최대 L2 norm 오차는 `2.22e-16`이며 비밀 필드는
  저장되지 않았다.
- 2026-07-23: 2,006개 전체 corpus에서 실제 질문의 query embedding과 cosine top 3 출력을 확인했다.
- 2026-07-23: 전체 검증에서 core 4개, API 235개 통과·환경 의존 2개 skip, collector 34개, web 46개
  테스트와 Ruff, 문서 검사, TypeScript, Next.js build가 통과했다.

## 잔여 한계

- 전체 청크를 대상으로 한 소수 질문은 검색 품질 평가셋이 아니다. score 임계값과 production 품질은
  별도 관련·비관련 질문셋으로 평가해야 한다.
- 기존 parser가 만든 제목·장·절 전용 청크도 의도적으로 검색 후보에 포함된다.
- 로컬 corpus는 현재 PC의 `.data`에만 있고 Git clone이나 다른 PC에는 자동 복제되지 않는다.

## 완료 결과

기존 Open API client, 공용 parser와 NVIDIA embedder의 핵심 동작을 바꾸지 않고 실험 C로 연결했다.
로컬에는 세 법령의 기존 파서 청크 전체 2,006개와 passage embedding이 준비돼 있다. 사용자는 `ask`
명령에서 질문을 입력하면 query embedding과 전체 cosine 전수 계산 결과의 상위 3개를 원문·점수와
함께 볼 수 있다. production DB와 기존 미커밋 실험 B 결과는 변경하지 않았다.
