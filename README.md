# law-rag

국가법령정보 공동활용 Open API 원문만 사용하는 에너지 법령 RAG 웹 워크벤치입니다. 질문 기준일의 유효 조문을 하이브리드 검색하고, 생성 답변의 주장과 체크리스트를 원문 인용 ID로 검증합니다. AI를 사용할 수 없으면 검색 전용 모드가 유지됩니다.

## 로컬 경로와 원격 저장소

- 로컬: `C:\Users\Family\Documents\law-rag`
- 원격: `https://github.com/yjs000/law-rag.git`

## 시작

```powershell
pnpm.cmd install
pnpm.cmd build

uv sync --all-packages --python 3.14
uv run --directory apps/api python -m pytest
uv run --directory apps/api python -m uvicorn app.main:app --reload
```

다른 터미널에서 `pnpm.cmd dev:web`을 실행한다. 환경변수는 `.env.example`, API는 `apps/api/.env.example`을 참고하되 실제 `.env`는 커밋하지 않는다.

웹의 Google 로그인은 개발용 목업이며 실제 Google OAuth는 아직 연결하지 않는다. 익명 질문은 저장하지 않고, 목업 로그인 질문은 프로세스 메모리에만 저장한다. 이력은 1년 후 만료되고 계정 삭제 시 관련 목업 데이터가 함께 삭제된다.

법령 수집은 API와 분리된 `apps/collector`가 담당하며 `LAW_OPEN_API_OC`가 필요하다. 현재는 `.collector-state/` 파일 목업 저장소를 사용한다.

```powershell
uv run --project apps/collector law-rag-collector sync-current
uv run --project apps/collector law-rag-collector sync-history
uv run --project apps/collector law-rag-collector status
```

Windows 작업 스케줄러의 수동 실행·등록·해제 방법은 [collector 운영 문서](apps/collector/README.md)를 참고한다. 설치나 테스트가 스케줄러를 자동 등록하지 않는다.

전체 검증은 `pnpm.cmd verify`로 실행한다.

두 문장의 NVIDIA NIM 임베딩과 코사인 유사도를 직접 확인하는 방법은
[실험 B 실행 안내](experiments/embeddings/README.md)를 참고한다. 성공한 터미널 JSON은
`docs/generated/`의 실제 결과 문서에 기록되어 반복 실행 차이를 비교할 수 있다.

Open API 세 법령의 지정 장·조 청크를 로컬에 저장하고 raw 청크·조 단위 후보 10개와 고정 평가를 확인하는 방법은
[실험 C 실행 안내](experiments/search/README.md)를 참고한다.

현재 실험 D는 사용자 확인이 끝난 D-10 10문항을 소표본 calibration 계약으로 동결해 진행한다. 승인된
1,000문항 질문은행은 보존하되 전체 Gold 승격은 일반화·운영 회귀가 실제로 필요할 때만 다시 검토한다.
D-10 계약은 질문·판정·직접 근거·corpus/profile과 원본 artifact 해시를 검사하며 정식 Evidence Recall이나
release gate가 아니다.

```powershell
uv run --directory apps/api python -m scripts.experiment_d_10_frozen_contract preflight
```

M3에서는 저장된 동일 raw top 10과 R1을 비교하며 새 embedding·DB 검색·AI 답변 생성은 하지 않는다.
[D-10 M2/M3 설계](docs/design-docs/experiment-d-10-m3-calibration.md)에 허용 지표, 사용자 확인사항과
Codex 확인사항을 정리한다.

D-10을 전수 qrel calibration Gold로 만드는 별도 workflow는 10문항×3,066개 판정을 생성했고 현재 사용자
adjudication 대기 상태다. 승인 전에는 Gold 지표를 계산하지 않는다. 검토 항목과 seal 방법은
[D-10 Gold adjudication 설계](docs/design-docs/experiment-d-10-gold-adjudication.md)를 따른다.

## 문서 시작점

- [작업 계약](AGENTS.md)
- [아키텍처](ARCHITECTURE.md)
- [제품 명세](docs/product-specs/index.md)
- [설계 문서](docs/design-docs/index.md)
- [학습 노트](docs/learning/index.md)
- [사용자가 제안한 예정 작업](docs/exec-plans/todo/README.md)
- [현재 실행 계획](docs/exec-plans/active/0002-production-connections.md)
- [완료된 MVP 계획](docs/exec-plans/completed/0001-mvp-foundation.md)
- [GitHub 이슈와 PR 운영](docs/GITHUB_WORKFLOW.md)

법률 자문을 대체하지 않으며 HTML 크롤링, PDF 기본 청킹, 다른 법률 사이트나 모델 기억을 근거로 사용하지 않습니다.
