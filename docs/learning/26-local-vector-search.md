# 법률 구조 범위를 보존하는 로컬 벡터 검색

## 결론

실험용 corpus를 줄일 때 임의의 개별 청크를 고르면 조문 본문 일부만 남을 수 있다. 장이나 조를 먼저
선택하고, 그 구조에 속한 기존 조·항·호·목 청크를 전부 포함해야 선택 범위 안의 본문이 보존된다.

```text
Open API JSON/XML
-> 파서
-> 정규화 문서와 조·항·호·목 청크
-> 지정 장·조에 속하는 청크 필터
-> 기존 NVIDIA passage embedding
-> 로컬 corpus
-> query embedding과 cosine top 3
```

## 파서와 범위 선택의 역할

현재 파서는 JSON/XML을 `LegalDocumentRecord`로 정규화하면서 조·항·호·목을 `ProvisionRecord`로 만든다.
장 자체를 별도 필드로 저장하지는 않지만, Open API가 각 장의 첫 조 본문 앞에 넣은 `제N장` 표제를
보존한다. 실험 C는 최상위 조를 순서대로 읽어 장 표제부터 다음 장 표제 직전까지를 한 장의 범위로
판정한다. 파서나 청크 내용은 변경하지 않는다.

현재 선택은 다음과 같다.

- 저작권법: 제1장과 제5장
- 전기사업법: 제1장과 제6장
- 신재생에너지법: 장 구분이 없어 제1조부터 제5조

`제5장의2`는 제5장과 별도 구조이므로 제외한다. 제1조부터 제5조라는 숫자 범위에는 제2조의2 같은
가지조문을 포함한다. 선택된 모든 조의 항·호·목도 포함한다.

## “본문이 빠지지 않는다”의 정확한 의미

선택한 장·조 내부에서는 파서가 만든 모든 하위 청크를 남기므로 일부 항이나 호만 빠지지 않는다.
하지만 선택하지 않은 장과 조는 corpus에서 의도적으로 제거된다. 따라서 이것은 전체 법률을 대표하는
corpus가 아니라 검색 연결을 관찰하기 위한 제한된 실험 데이터다.

지정한 장 표제나 조가 원문에서 발견되지 않으면 비슷한 범위를 추측하지 않고 준비를 실패시킨다. 모든
embedding이 성공한 후 원자 교체하므로 실패 중간 상태가 기존 corpus를 덮어쓰지 않는다.

## 저장 계보와 검색

`.data/experiments/search/corpus.json`에는 source ID, MST, 시행일, 원문 해시, parser version과 함께
선택 정책 및 실제 포함된 조 경로가 기록된다. 질문은 같은 모델의 `input_type=query`, 문서는
`input_type=passage`를 사용한다. 두 벡터 모두 기존 adapter가 native 2048차원의 앞 512개를 선택하고
L2 재정규화한다.

질문 벡터 `q`와 각 청크 벡터 `dᵢ`의 점수는 다음과 같다.

```text
scoreᵢ = (q · dᵢ) / (||q||₂ * ||dᵢ||₂)
```

저장 청크를 전부 비교해 상위 3개를 출력한다. 점수는 확률이나 법률적 동일성 판정이 아니며, 선택 범위
밖 조문은 검색 후보에 존재하지 않는다.

## 실행

```powershell
uv run --directory apps/api python -m scripts.experiment_search prepare
uv run --directory apps/api python -m scripts.experiment_search ask
```

상세 저장 필드와 실패 동작은 [실험 C 실행 안내](../../experiments/search/README.md)를 참고한다.
