# 0041: 법제처 API의 법종구분코드를 실제로 파싱해 저장·응답에 반영

상태: `완료 (2026-08-09)`

제안 출처: 2026-08-08 사용자가 "지금 source_kind가 law/administrative_rule 2단계뿐인데,
법제처 API가 애초에 법률/시행령/시행규칙 구분을 안 내려주는 거냐"고 물어 조사한 결과,
**API는 이미 이 구분을 내려주는데 이 저장소 파서가 안 읽고 있다**는 걸 확인했다. 사용자가
착수를 지시했고, 저장 방식(원 컬럼 그대로 vs SourceKind 4단계 확장)은 전자를 선호한다고
명시했다.

## 확인된 사실

- 법제처 Open API "현행법령(시행일) 본문 조회"(`target=eflaw`) 응답에
  **`법종구분`**(법종 구분명)과 **`법종구분코드`**(그 코드값) 필드가 있다
  ([공식 가이드](https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdInfoGuide)).
- 이 저장소의 파서(`packages/law-rag-core/src/law_rag_core/parsers/law_json.py`,
  `law_xml.py`)는 법령명·법령ID·시행일자·공포번호·소관부처는 뽑아내면서 이 두 필드는
  **한 번도 요청·추출하지 않는다** — 파싱 중 버린 게 아니라 애초에 코드가 없다.
- 지금 법률/시행령/시행규칙 구분은 API 응답이 아니라 사람이 직접 작성한 정적 카탈로그
  (`packages/law-rag-core/src/law_rag_core/domain/catalog.py`의 `MVP_CATALOG`, 제목 문자열
  매핑)로만 이뤄진다. `전기사업법`/`전기사업법 시행령`/`전기사업법 시행규칙`이 전부
  `SourceKind.LAW` 하나로 뭉쳐 있다.
- `admrul`(행정규칙) 타겟 조회 응답에도 대응하는 분류 필드가 있는지는 아직 확인 안 됨 -
  착수 시 같이 확인 필요.

## 결정 사항 (사용자, 2026-08-08)

1. **파싱**: `법종구분`/`법종구분코드`를 실제로 API 응답에서 읽어온다.
2. **저장 방식**: `SourceKind` enum을 4단계(법률/시행령/시행규칙/행정규칙)로 확장하는
   대신, **API 원 컬럼(법종구분코드)을 있는 그대로 저장하는 쪽을 선호**한다 - enum을
   이 저장소가 새로 정의·유지보수하지 않고, 법제처가 정의한 코드값을 그대로 신뢰한다.
   (완전히 확정은 아님 - "검토"라고 명시했으니 착수 시 두 방식의 실제 트레이드오프를
   한 번 더 짚고 확정한다: 원 컬럼 그대로 저장 시 이 코드값의 안정성·문서화 수준을
   확인해야 하고, enum 확장 시 API 쪽 코드 체계 변경에 이 저장소가 다시 노출된다.)
3. **API 응답에 실어 보내기**: 최종적으로 결정된 값(`source_kind` 또는
   `법종구분코드` 원값)을 `Citation` 스키마에 새 필드로 추가해 `/v1/questions` 응답에
   포함시킨다 - 지금은 `SearchHit`까지만 오고 `Citation`엔 필드 자체가 없어서 프론트가
   못 받는다([main.py](../../../apps/api/app/main.py) 참고).
4. **검색 쿼리 필터는 만들지 않는다**: "법률만 검색"류 `WHERE d.source_kind='law'` 필터는
   착수 대상이 아니다 - 사용자가 명시: 지금 MVP 코퍼스 범위에서 이 구분으로 걸러야 할
   실사용 요구가 없다는 판단.
5. **생성용 근거 선정 우선순위는 별도 작업 아님**: `select_generation_hits`가
   source_kind를 고려해 우선순위를 매기는 건 별도로 안 한다 - [0033](../todo/0033-traffic-based-routing-calibration-review.md)류
   재순위가 붙으면 검색 순서 자체가 이미 우선순위를 반영하게 돼 자동으로 해결될
   것으로 본다(사용자 판단, 근거 실측은 재순위 작업 때 확인).

## 비범위

- 검색 쿼리 필터(`WHERE source_kind=...`)는 이번 항목에 포함하지 않는다(위 4번).
- 재순위 신호로 source_kind를 쓰는 것은 이 항목이 아니라 [0042](../todo/0042-wire-reranking-into-live-search-path.md)의
  세부 항목으로 다룬다.
- `admrul`(행정규칙) 쪽에 동등한 분류 필드가 있는지, 있다면 어떻게 다룰지는 착수 시 조사
  범위에 포함한다(미확인 상태).

## 승격 조건

- 사용자가 착수를 명시한다.

## 완료 조건

- 신규 수집·재수집되는 법령 문서에 법종구분(코드) 값이 DB에 저장된다.
- `/v1/questions` 응답의 `Citation`에 이 값이 실려서 나간다.
- 프론트가 (착수한다면) 이 실제 값 기반으로 문서 종류를 구분할 수 있는 상태가 된다 -
  다만 프론트 반영 자체는 이 항목의 범위인지 별도 결정 필요.

## 구현 결과 (2026-08-09)

- 확인: `admrul`(행정규칙) 응답에는 `법종구분`/`법종구분코드`가 아니라 별도 필드
  `행정규칙종류`/`행정규칙종류코드`가 쓰인다(법제처 Open API 가이드 페이지 확인).
- **파싱**: `law_json.py`/`law_xml.py`가 `source_kind`에 따라 `(법종구분, 법종구분코드)`
  또는 `(행정규칙종류, 행정규칙종류코드)`를 읽어 `LegalDocumentRecord.law_type_name`/
  `.law_type_code`에 채운다.
- **저장 방식**: 결정대로 `SourceKind` enum은 2단계로 유지하고, API 원 컬럼 값을
  `legal_documents.law_type_name`/`law_type_code`(신규 마이그레이션 `0012`)에 그대로
  저장한다. 이 값은 corpus 발행 drift 감지 계약(`corpus-publish-base-v1` /
  `_PUBLISH_BASE_FIELDS`)에는 포함하지 않기로 결정했다 - 이 계약은 여러 파일에 걸친
  content-addressed 해시 계약이라 확장 시 blast radius가 크고, 법종구분은 사실상
  불변에 가까운 값이라 매 upsert마다 최신 파싱값으로 덮어쓰는 것으로 충분하다고 판단했다
  (collector `SupabaseCurrentCorpusRepository.upsert`의 `INSERT ... ON CONFLICT DO UPDATE`).
- **API 응답 반영**: `Citation`/`SearchHit` 스키마에 `law_type_code: str | None`을
  추가하고, `postgres_repository.py`의 검색·조문조회 SQL 4곳(직접경로/단일조문/dense
  검색/키워드검색)과 `_hit()`, `memory_repository.py`의 두 `SearchHit(...)` 생성 지점,
  `answering.py`/`main.py`의 두 `Citation(...)` 생성 지점을 모두 연결했다. `_hit()`는
  `row.get("law_type_code")`로 방어적으로 읽어 아직 이 컬럼을 선택하지 않는 SQL 경로가
  있어도 깨지지 않게 했다.
- **검증**: law-rag-core(26), api(588+2 skipped), collector(95+5 skipped) 테스트 전체
  통과, ruff 통과. 신규/확장 테스트: 파서 법종구분 추출(JSON/XML, LAW/ADMIN_RULE, 부재
  시 None), `PreparedDocumentRecord` round-trip, `0012` 마이그레이션 계약, collector
  upsert INSERT 파라미터, `MemoryLegalRepository` search hit, `search_only_answer`
  Citation.
- **운영 DB 검증 (2026-08-09, 사용자 승인)**: Supabase MCP로 운영 프로젝트(`law-rag`,
  `ijoqcauleoobbxdbdhxg`)에 `0012` 마이그레이션을 직접 적용(`ALTER TABLE legal_documents
  ADD COLUMN law_type_name text, ADD COLUMN law_type_code text`)하고 `alembic_version`을
  `0012`로 갱신했다. `postgres_repository.py`에서 수정한 SQL 4곳(직접경로 검색·단일조문
  조회·dense 검색 CTE·키워드검색 CTE)을 실제 운영 데이터(전기사업법 등 9개 문서,
  3066개 조문)에 대해 그대로 실행해 문법 오류 없이 `law_type_code` 컬럼까지 반환됨을
  확인했다. `get_advisors(security)`로 이 변경이 새 보안 advisory를 만들지 않았음도
  확인(기존 RLS 미설정 등은 이 변경과 무관한 기존 상태). 운영 데이터 자체는 수정하지
  않았다 - 신규·재수집 문서부터 실제 값이 채워진다.
- `docs/generated/db-schema.md`를 `0012` 반영해 갱신했다.
