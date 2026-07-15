# 01 런타임과 모노레포

## 개념과 선택 이유

모노레포는 웹과 API를 한 Git 저장소에서 관리하되 실행·배포 단위는 분리하는 구조다. lock 파일은 의존성 그래프를 재현한다. pnpm의 `allowBuilds`는 설치 스크립트를 실행할 의존성만 명시적으로 허용한다. Next.js와 FastAPI의 장점을 유지하면서 API 계약과 문서를 함께 검토하려고 선택했다.

Node 24.18.0, pnpm 11.12.0, uv 0.11.28과 Python 3.14 계열을 프로젝트와 CI의 기준으로 삼는다. `.python-version`도 `3.14`로 지정해 개발과 Vercel 배포가 같은 마이너 런타임 계약을 사용한다. `sharp`, `unrs-resolver` 외 설치 스크립트는 허용하지 않는다.

## 데이터 흐름

브라우저 → Next.js → FastAPI이며 비밀키는 서버 계층에만 있다. Python 쪽은 루트 uv workspace 아래 `apps/api`, `apps/collector` 실행 프로젝트와 `packages/law-rag-core` 공용 패키지로 분리한다. 공용 패키지는 법령 DTO·파서·포트만 포함하고 FastAPI, OpenAI, 데이터베이스 SDK에는 의존하지 않는다.

## 직접 실행

```powershell
pnpm.cmd install
pnpm.cmd build
cd apps/api
uv sync --python 3.14
uv run uvicorn app.main:app --reload

# 저장소 전체 검증
cd ../..
pnpm.cmd verify
```

## 다음 학습 주제

환경변수 경계, uv workspace의 editable workspace dependency, 단일 클라우드 서버에서 Web/API/collector 프로세스를 분리하는 방법을 학습한다.
