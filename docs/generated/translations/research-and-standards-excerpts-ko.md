# MRL·FIPS 180-4·RRF 제공 원문 번역

> 생성 명령: Codex를 사용한 사용자 제공 원문의 한국어 번역
> 기준 시점: 2026-07-14
> 출처: 사용자 메시지에 제공된 arXiv, NIST FIPS 180-4, RRF 원문 발췌
> 번역 원칙: 코드와 중요 전문용어는 원문 그대로 유지하고 어려운 용어에만 한국어 해석을 괄호로 덧붙였다. 제공된 내용을 생략하거나 요약하지 않았다.

## Matryoshka Representation Learning

저자: [Aditya Kusupati](https://arxiv.org/search/cs?searchtype=author&query=Kusupati,+A), [Gantavya Bhatt](https://arxiv.org/search/cs?searchtype=author&query=Bhatt,+G), [Aniket Rege](https://arxiv.org/search/cs?searchtype=author&query=Rege,+A), [Matthew Wallingford](https://arxiv.org/search/cs?searchtype=author&query=Wallingford,+M), [Aditya Sinha](https://arxiv.org/search/cs?searchtype=author&query=Sinha,+A), [Vivek Ramanujan](https://arxiv.org/search/cs?searchtype=author&query=Ramanujan,+V), [William Howard-Snyder](https://arxiv.org/search/cs?searchtype=author&query=Howard-Snyder,+W), [Kaifeng Chen](https://arxiv.org/search/cs?searchtype=author&query=Chen,+K), [Sham Kakade](https://arxiv.org/search/cs?searchtype=author&query=Kakade,+S), [Prateek Jain](https://arxiv.org/search/cs?searchtype=author&query=Jain,+P), [Ali Farhadi](https://arxiv.org/search/cs?searchtype=author&query=Farhadi,+A)

Learned representations(학습된 표현)은 현대 ML system의 핵심 구성요소이며, 매우 다양한 downstream task(후속 작업)에 사용됩니다. 이러한 representation을 훈련할 때 각 downstream task의 computational constraint(계산 제약)와 statistical constraint(통계적 제약)를 미리 알 수 없는 경우가 많습니다. 이런 상황에서 고정된 capacity(용량)를 가진 경직된 representation은 해당 task에 필요한 수준보다 지나치게 크거나 부족할 수 있습니다. 이에 따라 우리는 다음과 같은 질문을 제기합니다. 서로 다른 computational resource(계산 자원)를 가진 여러 downstream task에 적응할 수 있는 유연한 representation을 설계할 수 있는가?

우리의 주요 기여는 Matryoshka Representation Learning(MRL)입니다. MRL은 정보를 서로 다른 granularity(세분성)로 encode하고, 하나의 embedding이 downstream task의 계산 제약에 적응할 수 있게 합니다. MRL은 기존 representation learning pipeline을 최소한으로 변경하며 inference(추론)와 deployment(배포) 시 추가 비용을 부과하지 않습니다. MRL은 coarse-to-fine representation(거친 수준에서 세밀한 수준으로 이어지는 표현)을 학습하며, 이 representation은 독립적으로 훈련된 low-dimensional representation(저차원 표현)만큼 정확하고 풍부합니다.

학습된 Matryoshka Representations의 유연성은 다음을 제공합니다. (a) ImageNet-1K classification에서 동일한 수준의 accuracy를 유지하면서 embedding 크기를 최대 14배 줄임, (b) ImageNet-1K와 ImageNet-4K의 대규모 retrieval에서 실제 환경 기준 최대 14배의 speed-up(속도 향상), (c) 기존 representation과 같은 robustness(강건성)를 유지하면서 long-tail few-shot classification에서 accuracy를 최대 2% 향상. 마지막으로 우리는 MRL이 web-scale dataset인 ImageNet과 JFT에서 vision(ViT, ResNet), vision + language(ALIGN), language(BERT)를 포함한 여러 modality(양식)에 매끄럽게 확장됨을 보여줍니다. MRL code와 pretrained model은 [이 HTTPS URL](https://github.com/RAIVNLab/MRL)에 open source로 공개되어 있습니다.

Comments: intrinsic dimensionality(내재 차원성) 연구를 포함하도록 related work를 수정함
Subjects: **Machine Learning (cs.LG)**; Computer Vision and Pattern Recognition (cs.CV)
Cite as: [**arXiv:2205.13147**](https://arxiv.org/abs/2205.13147) **[cs.LG]**
또는 이 version은 [**arXiv:2205.13147v4**](https://arxiv.org/abs/2205.13147v4) **[cs.LG]**
[https://doi.org/10.48550/arXiv.2205.13147](https://doi.org/10.48550/arXiv.2205.13147)

### Focus to learn more

### Submission history

From: Aditya Kusupati ([view email](https://arxiv.org/show-email/7ddd865c/2205.13147))

- [[v1]](https://arxiv.org/abs/2205.13147v1) 2022년 5월 26일 목요일 04:33:56 UTC (9,795 KB)
- [[v2]](https://arxiv.org/abs/2205.13147v2) 2022년 6월 1일 수요일 00:03:14 UTC (9,794 KB)
- [[v3]](https://arxiv.org/abs/2205.13147v3) 2022년 10월 1일 토요일 00:40:52 UTC (7,558 KB)
- **[v4]** 2024년 2월 8일 목요일 03:21:26 UTC (7,558 KB)

## FIPS 180-4 — Secure Hash Standard (SHS)

[Facebook에 공유](https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fcsrc.nist.gov%2Fpubs%2Ffips%2F180-4%2Fupd1%2Ffinal) · [X에 공유](https://x.com/share?url=https%3A%2F%2Fcsrc.nist.gov%2Fpubs%2Ffips%2F180-4%2Fupd1%2Ffinal) · [LinkedIn에 공유](https://www.linkedin.com/shareArticle?mini=true&url=https%3A%2F%2Fcsrc.nist.gov%2Fpubs%2Ffips%2F180-4%2Fupd1%2Ffinal&source=csrc.nist.gov) · 이메일로 공유

**Date Published:** 2015년 8월
**Supersedes:** [FIPS 180-4 (2012-03-06)](https://csrc.nist.gov/pubs/fips/180-4/final)

**Planning Note (2023-03-07):** 두 차례의 public comment를 거친 뒤, [NIST는 FIPS 180-4를 개정하기로 결정했습니다](https://csrc.nist.gov/news/2023/decision-to-revise-fips-180-4).

**Author(s)**
National Institute of Standards and Technology

### Abstract

이 standard는 message의 digest를 생성하는 데 사용할 수 있는 hash algorithm을 규정합니다. Digest는 digest가 생성된 뒤 message가 변경되었는지 탐지하는 데 사용됩니다.

**Keywords**
computer security; cryptography(암호학); message digest; hash function; hash algorithm; Federal Information Processing Standards; Secure Hash Standard

**Control Families**
System and Communications Protection; System and Information Integrity

### 1. INTRODUCTION

이 Standard는 secure hash algorithm인 SHA-1, SHA-224, SHA-256, SHA-384, SHA-512, SHA-512/224 및 SHA-512/256을 규정합니다. 모든 algorithm은 message를 처리하여 message digest라고 하는 압축된 representation을 생성할 수 있는 iterative(반복형), one-way hash function(단방향 hash function)입니다. 이 algorithm을 사용하면 message의 integrity(무결성)를 확인할 수 있습니다. Message가 변경되면 매우 높은 확률로 서로 다른 message digest가 생성됩니다. 이 속성은 digital signature와 message authentication code의 생성 및 검증, 그리고 random number 또는 bit의 생성에 유용합니다.

각 algorithm은 preprocessing(전처리)과 hash computation이라는 두 단계로 설명할 수 있습니다. Preprocessing에는 message를 padding하고, padding된 message를 `m`-bit block으로 나누며, hash computation에 사용할 initialization value를 설정하는 과정이 포함됩니다. Hash computation은 padding된 message에서 message schedule을 생성하고, 그 schedule을 function, constant, word operation과 함께 사용하여 일련의 hash value를 반복적으로 생성합니다. Hash computation이 생성한 최종 hash value가 message digest를 결정하는 데 사용됩니다.

이 algorithm들의 가장 중요한 차이는 hash 처리되는 data에 제공하는 security strength(보안 강도)입니다. 각 hash function을 digital signature algorithm과 keyed-hash message authentication code 같은 다른 cryptographic algorithm과 함께 사용할 때 해당 hash function과 전체 system의 security strength는 [SP 800-57]과 [SP 800-107]에서 확인할 수 있습니다. 또한 algorithm들은 hashing 중 사용하는 data block과 word의 크기 또는 message digest 크기에서도 차이가 있습니다. Figure 1은 이 hash algorithm의 기본 속성을 제시합니다.

| Algorithm | Message Size (bits) | Block Size (bits) | Word Size (bits) | Message Digest Size (bits) |
|---|---:|---:|---:|---:|
| SHA-1 | < 2^64 | 512 | 32 | 160 |
| SHA-224 | < 2^64 | 512 | 32 | 224 |
| SHA-256 | < 2^64 | 512 | 32 | 256 |
| SHA-384 | < 2^128 | 1024 | 64 | 384 |
| SHA-512 | < 2^128 | 1024 | 64 | 512 |
| SHA-512/224 | < 2^128 | 1024 | 64 | 224 |
| SHA-512/256 | < 2^128 | 1024 | 64 | 256 |

Figure 1: Secure Hash Algorithm Properties

## Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods

G. V. Cormack — University of Waterloo, Waterloo, Ontario, Canada
C. L. A. Clarke — University of Waterloo, Waterloo, Ontario, Canada
Stefan Büttcher — Google, Redmond, WA, USA

### ABSTRACT

Reciprocal Rank Fusion(RRF)은 여러 IR system(정보 검색 시스템)이 만든 document ranking을 결합하는 간단한 방법입니다. RRF는 일관되게 개별 system보다 더 나은 결과를 만들며, 표준 방법인 Condorcet Fuse보다도 더 나은 결과를 만듭니다. 이 결과는 여러 TREC experiment의 결과를 RRF로 결합하고, 이전에 보고된 모든 방법보다 LETOR 3 dataset의 순위를 더 잘 매기는 meta-learner(메타 학습기)를 구축함으로써 입증됩니다.

**Categories and Subject Descriptors:** H.3.3 [Information Search and Retrieval]: retrieval models
**General Terms:** Experimentation, Measurement
**Keywords:** fusion, aggregation, ranking
