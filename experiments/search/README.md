# 실험 C — 지정 장·조 범위 NVIDIA 벡터 검색

국가법령정보 공동활용 Open API에서 받은 원문을 기존 파서로 처리한 뒤, 사용자가 지정한 장·조 범위에
속하는 기존 청크만 `NvidiaNimEmbedder`의 `passage` 모드로 임베딩해 로컬 JSON에 저장한다. 질문은
같은 모델의 `query` 모드로 임베딩하고 저장 청크 전체의 코사인 유사도 상위 3개를 출력한다.

## 데이터 범위

| 법령 | 버전 | 저장 범위 | 실제 청크 수 |
| --- | --- | --- | ---: |
| 저작권법 | 현행 MST `283335`, 시행 2026-05-11 | 제1장, 제5장 | 74 |
| 전기사업법 | 과거 MST `180380`, 시행 2016-07-28 | 제1장, 제6장 | 94 |
| 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 | 현행 MST `268793`, 시행 2026-02-01 | 제1조부터 제5조 | 37 |

장 범위는 해당 장 표제가 붙은 첫 조부터 다음 장 표제가 붙은 조 직전까지다. `제5장의2`처럼 별도
가지 장은 `제5장`에 포함하지 않는다. 조 범위는 제1조부터 제5조 사이의 `제2조의2` 같은 가지조문을
포함한다. 선택된 조의 항·호·목 청크는 모두 보존하며 청크를 다시 합치거나 나누지 않는다.

## 필요한 환경변수

비밀값은 저장소에 커밋하지 않고 루트 또는 앱별 `.env.local`에 둔다.

```dotenv
LAW_OPEN_API_OC=<국가법령정보 공동활용 Open API OC>
NVIDIA_API_KEY=<NVIDIA Build API key>
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b
EMBEDDING_DIMENSIONS=512
```

## 데이터 준비와 저장

```powershell
uv run --directory apps/api python -m scripts.experiment_search prepare
```

성공하면 `.data/experiments/search/corpus.json`이 총 205개 청크의 새 corpus로 원자 교체된다. 이 파일은 Git에서
제외된 현재 PC의 로컬 파일이다. 기존에 저장돼 있던 범위 밖 2,006개 corpus는 새 파일로 교체되므로
남지 않는다. 터미널에는 전체·법령별 청크 수와 실제 선택 범위를 출력한다.

임베딩 요청은 기본 32청크씩 나눈다. 모든 원문 수집, 범위 검증, embedding과 벡터 검증이 성공한 뒤에만
파일을 교체한다. 요청 하나라도 실패하거나 지정 장·조를 찾지 못하면 기존 corpus를 유지한다.

각 청크에는 법령명, source ID, MST, 시행일, 원문 SHA-256, parser version, path, parent path, 원문,
실제 passage 입력과 512차원 벡터가 저장된다. corpus의 `selection`에는 법령별 지정 범위와 실제 포함된
조 경로가 기록된다.

## 질문과 상위 3개 출력

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask
질문> 전기위원회는 무엇을 심의하나?
```

```powershell
uv run --directory apps/api python -m scripts.experiment_search ask `
  --question "저작권법의 목적은 무엇인가?"
```

출력 JSON에는 질문, provider/model, corpus 청크 수, `top_k=3`, score 종류와 `rank`, `score`, 법령명,
MST, 시행일, path, heading, content가 포함된다. 질문과 검색 결과는 파일에 저장하지 않으며, 질문할 때
query embedding만 새로 만든다.

## 점수와 실패 동작

`score`는 코사인 유사도이며 확률·정답률·법률적 동일성 점수가 아니다. 검색 대상은 위 지정 범위로
제한된다. 범위 밖 조문을 묻더라도 이 corpus에서는 찾을 수 없다.

- corpus가 없으면 `corpus_missing`과 종료 코드 `2`
- Open API OC 또는 NVIDIA key가 없으면 해당 설정 누락 코드와 종료 코드 `2`
- 지정 장·조 누락, Open API·NVIDIA·스키마·차원 검증 실패는 `experiment_c_failed`와 종료 코드 `2`
- provider 오류 전문, API key와 Authorization header는 출력하거나 저장하지 않음
- 다른 임베딩 모델, 영벡터 또는 비슷한 다른 장·조로 자동 대체하지 않음
