> 작업 ID: `B-023`
> 상태: `Todo`
> 우선순위: `P1`
> 유형: `Bug`
> 보조 라벨: `UX`, `Evaluation`
> 선행 조건: 문형 변경 범위의 설계 승인.
> 다음 행동: V2 공개 요약 전체의 쉬운 말 회귀를 추가하고 인용·근거 검사를 유지한 채 확인된 변경을 적용한다.
> 참고 범위:
> - `docs/design-docs/2026-11-06-v2-plain-summary.md` L1-L27 — 변경 범위, 실제 출력, 권한
> - `apps/api/app/adapters/openai_answerer.py` L343-L369 — 공개 요약 생성 지침
> - `apps/api/app/adapters/nvidia_nim_answerer.py` L100-L113 — 근거 검사 이전 요약 출력

# V2 공개 요약 전체를 쉬운 말로 표현하기

같은 허가 질문을 실제 V2로 세 차례 실행해 쉬운 표현과 기존 인용을 확인했다. [설계와 관찰 결과](../../design-docs/2026-11-06-v2-plain-summary.md)를 기준으로 적용 범위를 검토한다.
