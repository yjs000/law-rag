---
name: roadmap-operator
description: Use when starting, resuming, or transitioning a law-rag execution-plan milestone and context must stay limited to authoritative metadata and declared ranges.
---

# Roadmap Operator

## 개요

이 프로젝트 범위 skill은 실행계획의 상태를 찾고 전이할 때 읽는 문맥을 최소화한다. 실행계획 파일의
상단 메타데이터가 유일한 정본이고, 생성된 로드맵은 그 메타데이터에서 나온 색인이다.
로드맵의 상태·제목·다음 행동을 직접 고치지 말고 원본 헤더를 고친 뒤 renderer를 실행한다.

## 네 가지 읽기 범위 (순서 고정)

1. `docs/CURRENT_STATE.md L1-L28`과 생성된 `docs/ROADMAP.md`를 시작부터 마지막 비완료 행까지 읽는다.
2. 선택한 실행계획 파일의 시작부터 첫 `##` 직전까지만 읽는다.
3. 그 헤더의 `참고 범위`에 적힌 각 파일의 명시된 `L시작-L끝`만 읽는다.
4. 범위 밖 문맥이 반드시 필요하면 읽기 전에 확장을 선언한다. 선언에는 경로, 시작줄, 끝줄, 이유를
   모두 쓰고, 사용자에게 알리거나 작업 기록에 남긴 뒤에만 읽는다.

다른 실행계획의 본문, 완료 계획, `ARCHITECTURE.md` 전체는 위 네 범위만으로 부족하다는 근거가 있을
때만 확장한다. 따라서 이 자료들은 기본적으로 읽지 않는다. 계획 본문을 미리 훑거나 전체 문서를
출력·복사해 컨텍스트를 채우지 않는다.

## 빠른 참조

| 목적 | 기준 또는 명령 |
| --- | --- |
| 시작·재개 | roadmap의 `Picked Up` 또는 첫 `Todo` 행과 선택한 헤더 |
| 헤더 변경 후 생성 | `python scripts/render_roadmap.py` |
| 작업 트리 검증 | `python scripts/check_roadmap.py` |
| staged 검증 | `python scripts/check_roadmap.py --staged` |
| 범위 확장 | path, 시작줄, 끝줄, 이유를 먼저 기록 |

## 상태 전이

- `todo/`에는 `Todo`만 둔다. 착수하면 헤더를 `Picked Up`으로 바꾸고 같은 파일명으로 `active/`로
  이동한다. 저장소 전체의 `Picked Up`은 하나 이하여야 한다.
- `active/`에서는 `Todo`, `Picked Up`, `Blocked`를 사용한다. 막힌 경우 차단 사유와 재개 조건을
  계획 기록에 남긴다.
- 검증을 마친 계획은 헤더를 `Done`으로 바꾸고 같은 파일명으로 `completed/`로 이동한다. 결과와
  잔여 작업을 본문에 기록한다.
- 각 전이는 먼저 헤더와 선언된 범위를 읽고, 메타데이터·파일 위치를 함께 바꾼 다음 renderer와
  checker를 실행한다. `docs/ROADMAP.md`를 손으로 수정하지 않는다.

상태 전이 전후에는 짧은 읽은 범위 보고를 남긴다. 최소 형식은 다음과 같다.

```text
전이 전 읽은 범위: path=docs/exec-plans/todo/0000-example.md, 시작줄=1, 끝줄=10, 이유=현재 상태 확인
전이 후 읽은 범위: path=docs/exec-plans/active/0000-example.md, 시작줄=1, 끝줄=10, 이유=Picked Up 검증
```

파일을 이동하지 않은 전이는 같은 path를 반복하고, 범위 밖 자료를 읽었다면 그 항목도 같은 형식으로
추가한다. 보고는 읽은 파일·범위·이유만 담아 간결하게 유지한다.

## 검증 명령

메타데이터를 변경한 뒤 다음 명령을 순서대로 실행한다.

```powershell
uv run --project apps/api python scripts/render_roadmap.py
uv run --project apps/api python scripts/check_roadmap.py
```

staged 상태를 확인할 때는 `python scripts/check_roadmap.py --staged`를 사용한다. renderer만
`docs/ROADMAP.md`를 쓰며 checker는 읽기 전용이다. 실패하면 원본 헤더를 고치고 renderer를 다시
실행한다.

## 흔한 오류

- roadmap 행이나 상태를 직접 편집하는 것 — 헤더를 바꾸고 `python scripts/render_roadmap.py`를 실행한다.
- 계획 본문·완료 계획·전체 아키텍처를 먼저 읽는 것 — 선택한 헤더와 `참고 범위`부터 확인한다.
- 범위 확장 선언 없이 파일을 여는 것 — path, 시작줄, 끝줄, 이유를 먼저 기록한다.
- 전이 전후에 읽은 범위를 보고하지 않는 것 — 위의 두 줄 형식을 사용한다.
