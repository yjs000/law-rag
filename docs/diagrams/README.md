# 파이프라인 다이어그램

현재 구현 그림의 첫 진입점이다. 그림에 확인 날짜·코드 기준·근거 파일을 표시하고 설계와 실제 구현을 구분한다.

- [현재 law-rag 파이프라인](law-rag-current-pipeline.html): v1/v2 경계, v2 prepare/core/finalize,
  라우팅, clarification 상태 흐름, 설계와 구현 차이, v3 제거 상태.
  확인: 2026-10-27, 파이프라인 코드 기준: `5b274002`; v3 제거는 사용자 후속 요청 반영.
- [과거 v1 → v2 → v3 비교](../learning/diagrams/v1-v2-v3-pipeline-evolution.html): 역사 자료.
  tier1/tier2와 v3 표현을 현재 구현으로 해석하지 않는다.

HTML은 외부 라이브러리나 서버 없이 브라우저에서 연다. 설명용 문서이며 런타임 동작을 변경하지 않는다.
