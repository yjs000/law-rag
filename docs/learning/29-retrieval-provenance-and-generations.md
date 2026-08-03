# 검색 계보와 세대 관리

확인일: 2026-08-03

## 한 문장 결론

검색 결과를 비교하려면 알고리즘 이름만 기록해서는 부족하다. 어떤 corpus, 어떤 검색 계약, 어떤 물리 산출물, 어떤 조합을 사용했는지를 하나의 세대로 묶어야 두 실행이 정말 같은 조건인지 확인할 수 있다.

## 계보란 무엇인가

`Provenance`(프로비넌스, 계보)는 결과가 어디에서 왔는지 되짚을 수 있게 하는 기록이다. 이 프로젝트의 검색 결과에는 적어도 다음 질문에 답할 수 있어야 한다.

- 어떤 법령 corpus를 검색했는가?
- 어떤 dense 또는 lexical 검색 계약을 사용했는가?
- 별도 인덱스가 필요한 방식이라면 어떤 빌드를 사용했는가?
- 여러 검색기를 어떤 순서와 역할로 연결했는가?
- 그 조합 중 실제 운영 대상으로 지정된 것은 무엇이었는가?
- 평가 결과는 위 조건 중 어느 조합을 측정했는가?

이 기록이 없으면 같은 `Recall@10` 두 값이 corpus 차이 때문인지, 검색 방식 차이 때문인지 구분하기 어렵다.

## 세대란 무엇인가

`Generation`(세대)은 함께 검증하고 함께 전환해야 하는 검색 자산의 묶음이다. 법령 본문이 바뀌면 이전 corpus에 맞춘 벡터나 lexical 인덱스를 새 corpus의 산출물처럼 사용할 수 없다. 반대로 알고리즘 설정만 바뀌어도 같은 corpus에서 서로 다른 검색 세대가 생길 수 있다.

이 프로젝트는 세대를 하나의 거대한 테이블에 넣지 않고 다음 단위로 나눈다.

```text
corpus snapshot
  └─ 검색 대상 원문의 고정된 정체성

retrieval profile
  └─ 검색기 하나의 계산 계약

index build
  └─ 특정 snapshot과 profile로 만든 물리 산출물

configuration
  └─ profile들을 어떤 역할과 순서로 실행할지 정한 논리 조합

release
  └─ snapshot + configuration + 필요한 build를 함께 묶은 배포 후보

active pointer
  └─ 어떤 release를 현재 대상으로 지목하는 작은 포인터
```

## 각 단위의 차이

### Corpus snapshot

`Corpus`는 검색 대상 문서 전체이고, `snapshot`은 그 corpus를 특정 시점의 고정된 대상으로 식별한 기록이다. 파서 버전, 지원 기준일, 문서·조문 수와 고유 SHA-256 지문을 함께 기록하면 이름이 같아도 내용이 다른 corpus를 구분할 수 있다.

snapshot은 법령 원문을 복제하는 테이블이 아니다. 실제 원문은 기존 법령·버전·조문 테이블에 있고, snapshot은 그 집합의 정체성과 검증 결과를 가리키는 계보 경계다.

### Retrieval profile

`Retrieval profile`은 검색기 하나가 점수를 만드는 방법의 버전 계약이다.

예를 들어 현재 exact dense를 catalog에 등록한다면 NVIDIA 문서 벡터와 질문 벡터를 정확 코사인으로 비교하는 profile이 된다. keyword fallback도 등록 시에는 PGroonga 기반의 별도 profile이어야 한다. 둘은 점수 단위와 실행 조건이 다르므로 한 profile로 합치지 않는다. 이번 migration은 profile 행을 자동 생성하지 않는다.

임베딩 변환 계약을 저장하는 `embedding_profiles`와도 역할이 다르다.

- embedding profile: 문자열을 어떤 벡터로 바꾸는가
- retrieval profile: 질문을 어떤 후보 검색 절차와 점수로 연결하는가

### Index build

`Index build`는 특정 corpus snapshot과 retrieval profile을 바탕으로 만들어진 물리 산출물의 한 번의 구축 기록이다. 구축 설정, 상태, 대상 행 수와 산출물 식별자를 분리해 두면 같은 알고리즘의 서로 다른 구축 결과를 구분할 수 있다.

현재 schema의 build 상태는 다음 네 가지다.

- `building`: 구축 중이며 완료 시각이 아직 없음
- `ready`: 대상 수와 실제 생성 수가 같고 산출물 SHA-256이 있음
- `failed`: 완료 시각과 오류 코드가 있음
- `superseded`: 완성됐지만 더 새 세대로 대체된 산출물

모든 검색 profile이 물리 build를 필요로 하는 것은 아니다. 현재 exhaustive exact dense는 기준일에 유효한 벡터 전체를 직접 비교하므로 별도 HNSW build가 없어도 실행된다. 따라서 profile과 build를 같은 개념으로 취급하지 않는다.

### Configuration과 member

`Configuration`은 검색 profile들을 어떤 관계로 연결할지를 나타내는 논리 설정이다. 각 `member`는 configuration 안에서 profile의 순서, 역할과 필수 참여 여부를 기록한다. schema는 한 configuration 안에서 같은 profile이나 ordinal이 중복되지 않게 한다. `required`의 의미와 물리 build 필요 여부를 해석해 최종 확인하는 catalog writer는 아직 구현되지 않았으므로, 이 값만으로 release가 자동 승인되지는 않는다.

현재 동작은 다음과 같다.

```text
1. exact dense 실행
2. dense 결과가 0개일 때만 keyword fallback 실행
```

이는 두 점수를 합치는 hybrid나 RRF가 아니다. 첫 검색의 결과 유무에 따라 두 번째 검색을 실행하는 fallback 구성이다.

### Release와 release build

`Release`는 하나의 corpus snapshot과 하나의 configuration을 묶은 배포 후보다. 물리 build가 필요한 member가 생기면 `release build` 연결을 통해 정확히 어떤 build를 쓰는지도 함께 고정한다.

release 상태는 `draft`, `ready`, `retired`다. `ready`와 `retired`에는 준비 완료 시각이 있어야 한다. DB의 복합 외래키는 release build가 다음 세 조건을 동시에 만족하도록 한다.

- release가 지정한 configuration의 member다.
- member와 build의 retrieval profile이 같다.
- release와 build의 corpus snapshot이 같다.

configuration만 기록하면 corpus가 무엇인지 알 수 없고, build만 기록하면 그 산출물이 어떤 전체 검색 조합에 들어갔는지 알 수 없다. release가 이 두 경계를 함께 묶는다.

### Active pointer

`Active pointer`는 현재 대상으로 선택한 release를 가리킨다. release 내용을 직접 덮어쓰는 대신 포인터를 다른 검증된 release로 옮길 수 있도록 별도 경계로 둔다.

현재 테이블은 `singleton=true`인 행 하나만 허용하고, `ready` 상태 release만 가리킬 수 있다. 가리키는 release를 `retired`로 바꾸려면 먼저 포인터를 옮겨야 외래키 제약을 만족한다.

이번 catalog 추가만으로 런타임이 이 포인터를 읽도록 바뀌지는 않는다. 현재 검색 실행 경로는 기존 코드 그대로이며, catalog는 후속 전환을 안전하게 설계하고 평가 결과를 연결하기 위한 기록이다.

## 평가 계보가 필요한 이유

평가 실행은 결과 숫자뿐 아니라 dataset SHA-256, code SHA-256, corpus snapshot, retrieval release와 실행 metadata를 함께 가리킬 수 있어야 한다. release가 configuration을 포함하므로 검색 조합도 역추적할 수 있다. DB는 release를 기록한 평가 행에 snapshot도 요구하고, 평가 snapshot과 release snapshot이 같도록 복합 외래키로 검사한다. 그래야 다음 비교를 분리할 수 있다.

```text
같은 snapshot + 다른 profile/configuration
→ 검색 알고리즘 차이 비교

다른 snapshot + 같은 profile/configuration
→ corpus 변경 영향 비교

같은 release + 같은 승인 gold
→ 반복 실행 재현성 비교
```

서로 다른 snapshot과 서로 다른 알고리즘을 동시에 바꾼 결과는 어느 변화가 점수 차이를 만들었는지 단독으로 설명하지 못한다.

## Catalog와 실제 검색은 다르다

Catalog는 가능한 profile, build, configuration과 release의 계보를 기록한다. 테이블에 행이 있다는 사실만으로 해당 방식이 구현·승인·활성화되었다는 뜻은 아니다. Migration `0011`은 테이블과 capability marker만 만들고 현재 검색 자산을 자동으로 catalog 행에 넣지 않는다.

특히 이번 단계에서는 다음을 하지 않는다.

- BM25 구현 또는 실행
- dense와 lexical 결과 결합
- RRF 구현 또는 실행
- HNSW를 검색·평가 경로에 연결
- 기존 검색 런타임을 catalog 기반 동적 선택으로 변경

현재 운영 동작과 실험 D 기준선은 계속 다음과 같다.

- 기준일에 유효한 전체 population을 비교하는 exhaustive exact dense
- dense 후보가 0개일 때만 실행하는 독립 keyword fallback
- 실험 D에서 HNSW 상태나 결과를 입력·게이트·평가값으로 사용하지 않음

## 미래 검색기를 추가할 때의 순서

향후 BM25 같은 검색기를 검토한다면 먼저 독립 retrieval profile과 필요한 build를 만든다. 기존 exact dense와 동일한 승인 gold·corpus snapshot에서 각각 평가하고, 개선이 확인된 뒤에만 새 configuration과 release 후보를 만든다.

RRF도 먼저 만들어 두는 기본 구성요소가 아니다. 독립 dense와 lexical 결과를 결합할 필요가 평가로 확인될 때 별도의 fusion profile 또는 configuration 버전으로 추가해야 한다.

HNSW는 현재 DB에 역사적 물리 인덱스가 존재하지만 검색 품질 검증에는 사용하지 않는다. 질문·정답 gold와 근거 찾기 검증이 끝난 뒤, 별도 설계안과 사용자 승인을 거쳐야 새 build나 release에 연결할 수 있다.

## 관련 구현과 설계

- [검색 인덱스와 임베딩 계보 설계](../design-docs/retrieval-index-storage.md)
- [현재 데이터베이스 스키마](../generated/db-schema.md)
- [운영 벡터 구축의 역사적 실행 기록](../generated/vector-index-build-report.md)
- [현재 PostgreSQL 검색 repository](../../apps/api/app/adapters/postgres_repository.py)
- [retrieval catalog migration](../../apps/api/migrations/versions/0011_retrieval_catalog.py)
