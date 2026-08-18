# 0036: 계정 및 모델 정책 모달의 모델명 하드코딩 문구 정리

상태: `완료 (2026-08-18)` — 공급자 중립 UI copy 구현과 로컬 검증을 마쳤고 사용자가 완료로
확인했다.

제안 출처: 2026-08-08 사용자가 "계정 및 모델 정책" 모달에 `gpt-5.6-terra 전용`이라는
문구가 있는데, 실제로 지금 쓰는 모델과 다르니 현재 사용 중인 모델로 바꾸고, 모델명 자체를
노출하기보다는 "지금 AI 모드인지 아닌지"만 보여주면 된다고 지시했다.

## 원인

`apps/web/app/page.tsx`의 `AccountModal`(위치는 [page.tsx](../../../apps/web/app/page.tsx) 부근)에 다음처럼 하드코딩돼 있다:

```jsx
<div><dt>생성 모델</dt><dd>gpt-5.6-terra 전용</dd></div>
<div><dt>현재 상태</dt><dd className={corpus?.ai_available ? "available" : "limited"}>{corpus?.ai_available ? "NVIDIA AI 사용 가능" : "검색 전용"}</dd></div>
```

- `gpt-5.6-terra`는 `OpenAIAnswerer`가 쓰는 모델 리터럴(`settings.py`의 `openai_answer_model`)이다.
  운영은 `answer_provider=nvidia_nim`이 기본값이고 OpenAI는 "운영 비교·fallback으로
  쓰지 않기로 확정"([settings.py](../../../apps/api/app/settings.py))된 상태라, 이 문구는 실제로
  지금 쓰는 모델과 다르다.
- 바로 아래 `현재 상태` 줄이 이미 AI 사용 가능/검색 전용을 보여주고 있어 두 줄이 사실상
  중복된 정보를 다른 정확도로 보여주는 상태다.

## 확정 설계

- `생성 모델` 줄을 없애거나, "현재 상태" 줄 하나로 합쳐서 AI 모드 사용 가능/불가만
  보여주도록 정리한다 - 구체적 모델명(nemotron-3-ultra 등)은 노출하지 않는다는 게 사용자
  요청이므로 백엔드가 어떤 provider/모델을 쓰는지와 무관하게 프론트는 그대로 둘 수 있다.
- `corpus?.ai_available`는 이미 프론트에 있는 신호이므로 새 API 호출 없이 문구만 바꾸면
  된다.
- 계정 화면만 보지 않고 사용자에게 렌더링되는 전체 UI 문구를 검사한다. 내부 API 호환
  식별자 `terra`는 이번 변경에서 유지하되 화면에는 노출하지 않는다.
- 화면 표기는 공급자 중립적으로 통일한다: 계정 제목 `계정 및 AI 설정`, 상태 `AI 사용 가능`
  또는 `검색 전용`, 생성 결과 배지 `AI 답변 · 인용 검증`.

## 비범위

- 실제 사용 모델을 프론트에 노출하는 방향(반대 결정)은 이번 항목이 아니다.
- `장애 시 동작`, `질문 보존` 등 다른 정책 줄은 건드리지 않는다.

## 승격 조건

- 사용자가 착수를 명시한다.

## 완료 조건

- 모달에 특정 생성 모델명이 하드코딩돼 있지 않다.
- AI 모드 사용 가능/불가 상태만 명확히 표시된다.
- 계정 모달과 답변 결과를 포함한 사용자 노출 UI에 `terra`, `NVIDIA`, 구체 모델명이 없다.
- UI copy를 생성하는 실제 함수를 대상으로 한 회귀 테스트가 공급자 중립 문구를 검증한다.
- production 계정 화면과 AI 답변 결과 화면을 직접 확인한다.

## 구현 결과 (2026-08-09)

- `AccountDialog`의 `생성 모델` 줄(`gpt-5.6-terra 전용`)을 제거하고 `현재 상태` 줄을
  `AI 모드` 줄 하나로 정리했다(`corpus?.ai_available` 기반 "사용 가능"/"검색 전용",
  구체 모델명 노출 없음). [page.tsx](../../../apps/web/app/page.tsx).
- `gpt-5.6-terra` 문자열이 `page.tsx`에 더 이상 없음을 grep으로 확인. `tsc --noEmit`,
  `npm test` 통과. 이 저장소는 JSX 마크업 자체를 단위 테스트하지 않는 관례(RTL 미사용)를
  따라 별도 컴포넌트 테스트는 추가하지 않았다.

## 재개 사유와 진행 기록 (2026-08-09)

- 사용자가 production 계정 화면에서 이전 `gpt-5.6-terra 전용`, `NVIDIA AI 사용 가능`
  문구가 계속 보이는 스크린샷을 제공했다. 로컬 계정 모달은 이미 중립화됐지만 답변 결과
  배지에는 `NVIDIA Nemotron · 인용 검증`이 남아 있었고, 기존 완료 검증은 계정 모달의
  production 화면 및 전체 사용자 노출 copy를 검사하지 않았다.
- 공급자 중립 UI copy를 실제 함수로 분리하고 TDD로 계정 제목·상태·답변 배지를 함께
  검증한 뒤 production을 재확인한다.
- `provider-neutral-copy.test.ts`를 먼저 추가해 모듈 부재 실패를 확인한 뒤, 계정 제목·AI
  상태·답변 결과 배지를 만드는 `provider-neutral-copy.ts`를 구현했다.
  `AccountDialog`, 사이드바 계정 버튼과 `AnswerView`가 이 중립 copy를
  사용한다. 제품 명세의 현재 사용자 여정과 완료 기준도 같은 용어로 갱신했다.
- 로컬 검증: Web 15개 파일·70개 테스트, ESLint, TypeScript, production build 및 126개
  문서 링크 검사 통과. 남은 완료 조건은 branch 통합·production 배포 후 계정 화면과 AI
  답변 결과 화면의 실제 문구 확인이다.
