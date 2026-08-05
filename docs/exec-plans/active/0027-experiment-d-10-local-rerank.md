# 실행 계획 0027: 실험 D-10-R1 로컬 재정렬

상태: 구현 중
작성일: 2026-08-05
소유자: 주 에이전트

## 목적과 사용자 결과

확정 D-10의 동일 raw top 10을 부모 조문 표제와 일반 직접성 규칙으로 무호출 재정렬하고,
`lay-energy-0346`의 직접 근거 순위와 top 5 잡음 변화를 재현 가능한 artifact로 비교한다.

## 범위와 비범위

범위는 입력 결박, 후보 집합 보존, versioned 로컬 점수, JSON·Markdown 원자 기록, 확정 라벨 기반 전후
진단, 테스트와 학습 문서다. DB/NVIDIA/Open API, 새 embedding, corpus 변경, keyword/hybrid/RRF/HNSW,
모델 reranker, 운영 반영과 AI 답변 생성은 범위 밖이다.

## 완료 조건

- result와 confirmed review 결박 및 10×10 후보 계약을 검증한다.
- 점수 계산이 질문·부모 표제·raw 본문·raw cosine만 읽고 확인 라벨에는 의존하지 않는다.
- 재정렬 전후 candidate ID와 raw 값이 완전히 같다.
- `lay-energy-0346`의 첫 직접 근거 top 3 여부와 confirmed known irrelevant@5 변화를 기록한다.
- focused/전체 pytest, Ruff, 문서 검사와 diff 검토가 통과한다.

## 작업 TODO

| 상태 | 담당 | 작업 | 검증 |
|---|---|---|---|
| 진행 중 | 주 에이전트 | 설계·계획·평가 경계 | 문서 검사 |
| 대기 | 주 에이전트 | 입력 검증·직접성 profile·재정렬 runner | 단위·경계 테스트 |
| 대기 | 주 에이전트 | 저장 run 오프라인 실행·비교 artifact | SHA·후보 보존·목표 비교 |
| 대기 | 주 에이전트 | 학습·결과 기록·전체 검증 | 전체 pytest·Ruff·docs |

공유 result/review와 단일 scoring contract가 순차 의존하므로 하위 에이전트 없이 주 에이전트가 구현한다.

## 검증과 롤백

새 script·tests·문서와 `.data`의 별도 rerank artifact만 제거하면 원본 D-10으로 복귀한다. 원본 artifact는
수정하지 않는다.

## 결정 로그

- 2026-08-05: 같은 10문항 라벨은 scoring이 아니라 calibration 평가에만 사용한다.
- 2026-08-05: 새 top 5에 진입한 과거 6~10위 미판정 후보는 자동 관련 판정하지 않는다.

## 진행 기록

- 2026-08-05: D-10 사용자 10/10 승인과 confirmed diagnostics 생성을 완료했다.

## 미결정과 차단 요소

차단 요소는 없다. 운영 채택은 이 계획의 완료 조건이 아니다.
