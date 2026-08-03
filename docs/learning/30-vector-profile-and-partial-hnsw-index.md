# 벡터 프로필과 partial HNSW 인덱스

확인일: 2026-08-03

## 왜 모델 이름만 저장하면 부족한가

같은 임베딩 모델도 입력을 query로 보냈는지 passage로 보냈는지, 몇 차원을 유지했는지, 다시 정규화했는지에 따라 벡터가 달라진다. 모델 이름만 같은 벡터를 한 공간처럼 비교하면 검색 결과를 재현할 수 없다.

그래서 벡터 프로필은 provider, model, 원본·저장 차원, query/passage 입력 유형, 축약, 정규화, 임베딩 입력 문장 형식과 버전을 하나의 계약으로 묶는다. 프로필 키가 같아야 질문과 문서 벡터를 비교한다.

## source text hash가 하는 일

문서 벡터를 만들 때 실제 입력 문자열의 SHA-256을 함께 저장한다. 다음 실행에서 현재 입력의 해시가 저장값과 같으면 API 호출을 생략한다. 본문·표제·경로·법령명 중 하나라도 바뀌면 해시가 바뀌어 다시 생성한다.

이 해시는 내용을 복원하는 암호화가 아니라 변경 여부를 확인하는 지문이다.

## `vector(512)`와 `vector`의 차이

- `vector(512)`: 그 열의 모든 행이 반드시 512차원이다.
- `vector`: 행마다 차원이 달라도 저장할 수 있다.

차원 가변 열은 미래 모델 추가 때 편하지만 서로 다른 차원을 하나의 HNSW 인덱스에 넣을 수는 없다. 그래서 프로필과 차원이 같은 행만 대상으로 partial index를 만든다.

## partial expression index

partial은 조건에 맞는 행만 인덱싱한다는 뜻이고, expression은 원래 열을 특정 형태로 변환한 값을 인덱싱한다는 뜻이다.

```sql
USING hnsw ((embedding::vector(512)) vector_cosine_ops)
WHERE profile_key='nvidia-nemotron-3-embed-1b-512-v1'
```

다른 모델이 768차원을 쓴다면 같은 테이블에 저장하되 별도의 768차원 partial index를 만든다.

## HNSW가 하는 일

HNSW는 가까운 벡터를 빠르게 찾는 근사 최근접 이웃 인덱스다. 전체를 매번 비교하는 exact search보다 빠른 대신 일부 정답 후보를 놓칠 수 있으므로, 인덱스 도입 후 exact 결과와 비교해 recall을 측정해야 한다.

## BM25와 무슨 관계인가

BM25는 단어가 문서에 얼마나 중요하게 나타나는지를 계산하는 lexical 검색 방식이다. 벡터 인덱스가 아니므로 임베딩 테이블에 넣지 않는다.

확장 가능한 구조는 모든 검색을 한 DB 함수에 미리 섞는 구조가 아니다. dense와 BM25가 각각 독립 결과를 만들고, 같은 평가셋으로 비교한 뒤 필요할 때만 별도 fusion 단계에서 결합하는 구조다.

상세 구현 계약은 [검색 인덱스와 임베딩 계보 설계](../design-docs/retrieval-index-storage.md)에 있다. 차원 가변 저장과 partial expression index 예시는 [pgvector 공식 저장소](https://github.com/pgvector/pgvector)에 설명되어 있다.
