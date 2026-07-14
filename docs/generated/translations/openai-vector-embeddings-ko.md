# Vector embeddings(벡터 임베딩)

> 생성 명령: Codex를 사용한 사용자 제공 원문의 한국어 번역
> 기준 시점: 2026-07-14
> 출처: 사용자 제공 `Vector embeddings` OpenAI 문서 캡처 · [공식 문서](https://platform.openai.com/docs/guides/embeddings)
> 번역 원칙: 코드, model ID, API 이름과 중요 전문용어는 원문 그대로 유지하고 어려운 용어에만 한국어 해석을 괄호로 덧붙였다. 내용을 생략하거나 요약하지 않았다.

텍스트를 숫자로 변환하여 search(검색) 같은 use case(사용 사례)를 활용하는 방법을 알아봅니다.

## New embedding models

가장 새롭고 성능이 뛰어난 embedding model인 `text-embedding-3-small`과 `text-embedding-3-large`를 이제 사용할 수 있습니다. 이 모델들은 더 낮은 비용, 더 높은 다국어 성능, 그리고 전체 크기를 제어하기 위한 새로운 parameter를 제공합니다.

## What are embeddings?

OpenAI의 text embeddings는 text string(텍스트 문자열) 사이의 관련성을 측정합니다. Embeddings는 일반적으로 다음 용도로 사용됩니다.

- Search: query string(질의 문자열)과의 관련성을 기준으로 결과의 순위를 매깁니다.
- Clustering(군집화): 유사성을 기준으로 text string을 그룹화합니다.
- Recommendations(추천): 관련된 text string을 가진 항목을 추천합니다.
- Anomaly detection(이상 탐지): 관련성이 거의 없는 outlier(이상치)를 식별합니다.
- Diversity measurement(다양성 측정): 유사성 분포를 분석합니다.
- Classification(분류): text string을 가장 유사한 label(레이블)에 따라 분류합니다.

Embedding은 floating point number(부동소수점 수)의 vector(벡터, 목록)입니다. 두 vector 사이의 distance(거리)는 둘의 관련성을 측정합니다. 거리가 작으면 관련성이 높다는 뜻이고, 거리가 크면 관련성이 낮다는 뜻입니다.

Embeddings 가격을 알아보려면 pricing page를 방문하십시오. 요청 요금은 input의 token 수를 기준으로 청구됩니다.

## How to get embeddings

Embedding을 얻으려면 text string과 embedding model 이름(예: `text-embedding-3-small`)을 embeddings API endpoint로 전송합니다.

예제: Embeddings 얻기

```javascript
import OpenAI from "openai";
const openai = new OpenAI();

const embedding = await openai.embeddings.create({
  model: "text-embedding-3-small",
  input: "Your text string goes here",
  encoding_format: "float",
});

console.log(embedding);
```

Response에는 embedding vector(floating point number의 목록)와 몇 가지 추가 metadata가 포함됩니다. Embedding vector를 추출하여 vector database에 저장하고 여러 use case에 사용할 수 있습니다.

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [
        -0.006929283495992422, -0.005336422007530928, -4.547132266452536e-5,
        -0.024047505110502243
      ]
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {
    "prompt_tokens": 5,
    "total_tokens": 5
  }
}
```

기본적으로 embedding vector의 길이는 `text-embedding-3-small`에서는 1536이고, `text-embedding-3-large`에서는 3072입니다. 개념을 표현하는 속성을 잃지 않으면서 embedding의 dimensions(차원)를 줄이려면 `dimensions` parameter를 전달하십시오. Embedding dimensions에 관한 자세한 내용은 embedding use case section에서 확인할 수 있습니다.

## Embedding models

OpenAI는 두 가지 강력한 3세대 embedding model을 제공합니다. Model ID의 `-3`이 이를 나타냅니다. 자세한 내용은 embedding v3 announcement blog post를 읽으십시오.

사용 요금은 input token 단위로 책정됩니다. 다음은 미국 달러 1달러당 처리할 수 있는 text page 수의 예입니다. 한 page당 약 800 token이라고 가정합니다.

| Model | 달러당 약 page 수 | MTEB eval 성능 | 최대 input |
|---|---:|---:|---:|
| `text-embedding-3-small` | 62,500 | 62.3% | 8192 |
| `text-embedding-3-large` | 9,615 | 64.6% | 8192 |
| `text-embedding-ada-002` | 12,500 | 61.0% | 8192 |

## Use cases

여기에서는 Amazon fine-food reviews dataset을 사용하여 몇 가지 대표적인 use case를 보여줍니다.

### Obtaining the embeddings

이 dataset에는 2012년 10월까지 Amazon 사용자가 남긴 총 568,454개의 food review가 포함되어 있습니다. 설명을 위해 가장 최근 review 1,000개의 subset(부분집합)을 사용합니다. Review는 영어이며 긍정적이거나 부정적인 경향이 있습니다. 각 review에는 `ProductId`, `UserId`, `Score`, review title인 `Summary`, review body인 `Text`가 있습니다. 예를 들면 다음과 같습니다.

| Product Id | User Id | Score | Summary | Text |
|---|---|---:|---|---|
| B001E4KFG0 | A3SGXH7AUHU8GW | 5 | Good Quality Dog Food | I have bought several of the Vitality canned… |
| B00813GRG4 | A1D87F6ZCVE5NK | 1 | Not as Advertised | Product arrived labeled as Jumbo Salted Peanut… |

아래에서는 review summary와 review text를 하나의 combined text로 결합합니다. Model은 이 combined text를 encode(인코딩)하고 하나의 vector embedding을 출력합니다.

```python
from openai import OpenAI
client = OpenAI()

def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    return client.embeddings.create(input = [text], model=model).data[0].embedding

df['ada_embedding'] = df.combined.apply(lambda x: get_embedding(x, model='text-embedding-3-small'))
df.to_csv('output/embedded_1k_reviews.csv', index=False)
```

저장된 파일에서 데이터를 불러오려면 다음을 실행할 수 있습니다.

```python
import pandas as pd

df = pd.read_csv('output/embedded_1k_reviews.csv')
df['ada_embedding'] = df.ada_embedding.apply(eval).apply(np.array)
```

### Reducing embedding dimensions

### Question answering using embeddings-based search

### Text search using embeddings

### Code search using embeddings

### Recommendations using embeddings

### Data visualization in 2D

### Embedding as a text feature encoder for ML algorithms

### Classification using the embedding features

### Zero-shot classification

### Obtaining user and product embeddings for cold-start recommendation

### Clustering

## FAQ

### How can I tell how many tokens a string has before I embed it?

Python에서는 OpenAI의 tokenizer인 `tiktoken`을 사용하여 string을 token으로 분할할 수 있습니다.

예제 코드:

```python
import tiktoken

def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

num_tokens_from_string("tiktoken is great!", "cl100k_base")
```

`text-embedding-3-small` 같은 3세대 embedding model에서는 `cl100k_base` encoding을 사용하십시오.

더 자세한 내용과 예제 코드는 OpenAI Cookbook의 `how to count tokens with tiktoken` guide에 있습니다.

### How can I retrieve K nearest embedding vectors quickly?

많은 vector를 빠르게 검색하려면 vector database를 사용하는 것을 권장합니다. GitHub의 Cookbook에서 vector database와 OpenAI API를 함께 사용하는 예제를 찾을 수 있습니다.

### Which distance function should I use?

Cosine similarity를 권장합니다. 일반적으로 distance function의 선택은 큰 차이를 만들지 않습니다.

OpenAI embeddings는 길이가 1이 되도록 normalized(정규화)되어 있습니다. 이는 다음을 의미합니다.

- Cosine similarity는 dot product(내적)만 사용하여 조금 더 빠르게 계산할 수 있습니다.
- Cosine similarity와 Euclidean distance는 동일한 순위를 만듭니다.

### Can I share my embeddings online?

예. Embeddings의 경우를 포함하여 고객은 model에 넣은 input과 model에서 받은 output을 소유합니다. API에 입력하는 content가 적용 가능한 법률 또는 OpenAI Terms of Use를 위반하지 않도록 보장할 책임은 고객에게 있습니다.

### Do V3 embedding models know about recent events?

아니요. `text-embedding-3-large`와 `text-embedding-3-small` model에는 2021년 9월 이후 발생한 사건에 관한 지식이 없습니다. 일반적으로 이는 text generation model에서만큼 큰 제약은 아니지만, 특정 edge case(경계 사례)에서는 성능을 낮출 수 있습니다.
