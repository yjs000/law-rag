# 01 런타임과 모노레포

## 개념과 선택 이유

모노레포는 웹과 API를 한 Git 저장소에서 관리하되 실행·배포 단위는 분리하는 구조다. lock 파일은 의존성 그래프를 재현한다. pnpm의 `allowBuilds`는 설치 스크립트를 실행할 의존성만 명시적으로 허용한다. Next.js와 FastAPI의 장점을 유지하면서 API 계약과 문서를 함께 검토하려고 선택했다.

사용자가 설치한 Node 24.18.0, pnpm 11.12.0, Python 3.14.6, uv 0.11.28을 프로젝트와 CI에 고정했다. `sharp`, `unrs-resolver` 외 설치 스크립트는 허용하지 않는다.

## 데이터 흐름

브라우저 → Next.js → FastAPI이며 비밀키는 서버 계층에만 있다.

## 직접 실행

```powershell
pnpm.cmd install
pnpm.cmd build
cd apps/api
uv sync --python 3.14
uv run uvicorn app.main:app --reload
```

## 다음 학습 주제

환경변수 경계, Vercel 두 프로젝트 root 설정, Supavisor transaction pooler를 학습한다.
