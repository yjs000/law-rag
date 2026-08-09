# 0036: 계정 및 모델 정책 모달의 모델명 하드코딩 문구 정리

상태: `완료 (2026-08-09)`

제안 출처: 2026-08-08 사용자가 "계정 및 모델 정책" 모달에 `gpt-5.6-terra 전용`이라는
문구가 있는데, 실제로 지금 쓰는 모델과 다르니 현재 사용 중인 모델로 바꾸고, 모델명 자체를
노출하기보다는 "지금 AI 모드인지 아닌지"만 보여주면 된다고 지시했다.

## 원인

`apps/web/app/page.tsx`의 `AccountModal`(위치는 [page.tsx:222](../../../apps/web/app/page.tsx:222) 부근)에 다음처럼 하드코딩돼 있다:

```jsx
<div><dt>생성 모델</dt><dd>gpt-5.6-terra 전용</dd></div>
<div><dt>현재 상태</dt><dd className={corpus?.ai_available ? "available" : "limited"}>{corpus?.ai_available ? "NVIDIA AI 사용 가능" : "검색 전용"}</dd></div>
```

- `gpt-5.6-terra`는 `OpenAIAnswerer`가 쓰는 모델 리터럴(`settings.py`의 `openai_answer_model`)이다.
  운영은 `answer_provider=nvidia_nim`이 기본값이고 OpenAI는 "운영 비교·fallback으로
  쓰지 않기로 확정"([settings.py:29-31](../../../apps/api/app/settings.py:29))된 상태라, 이 문구는 실제로
  지금 쓰는 모델과 다르다.
- 바로 아래 `현재 상태` 줄이 이미 AI 사용 가능/검색 전용을 보여주고 있어 두 줄이 사실상
  중복된 정보를 다른 정확도로 보여주는 상태다.

## 설계 (미착수, 방향만)

- `생성 모델` 줄을 없애거나, "현재 상태" 줄 하나로 합쳐서 AI 모드 사용 가능/불가만
  보여주도록 정리한다 - 구체적 모델명(nemotron-3-ultra 등)은 노출하지 않는다는 게 사용자
  요청이므로 백엔드가 어떤 provider/모델을 쓰는지와 무관하게 프론트는 그대로 둘 수 있다.
- `corpus?.ai_available`는 이미 프론트에 있는 신호이므로 새 API 호출 없이 문구만 바꾸면
  된다.

## 비범위

- 실제 사용 모델을 프론트에 노출하는 방향(반대 결정)은 이번 항목이 아니다.
- `장애 시 동작`, `질문 보존` 등 다른 정책 줄은 건드리지 않는다.

## 승격 조건

- 사용자가 착수를 명시한다.

## 완료 조건

- 모달에 특정 생성 모델명이 하드코딩돼 있지 않다.
- AI 모드 사용 가능/불가 상태만 명확히 표시된다.

## 구현 결과 (2026-08-09)

- `AccountDialog`의 `생성 모델` 줄(`gpt-5.6-terra 전용`)을 제거하고 `현재 상태` 줄을
  `AI 모드` 줄 하나로 정리했다(`corpus?.ai_available` 기반 "사용 가능"/"검색 전용",
  구체 모델명 노출 없음). [page.tsx](../../../apps/web/app/page.tsx).
- `gpt-5.6-terra` 문자열이 `page.tsx`에 더 이상 없음을 grep으로 확인. `tsc --noEmit`,
  `npm test` 통과. 이 저장소는 JSX 마크업 자체를 단위 테스트하지 않는 관례(RTL 미사용)를
  따라 별도 컴포넌트 테스트는 추가하지 않았다.
