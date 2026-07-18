"""계정 질문 이력의 검색 단계별 진단을 읽기 전용 JSON으로 출력한다."""

import argparse
import asyncio
import json
import sys

from sqlalchemy import text

from app.adapters.postgres_repository import PostgresLegalRepository
from app.settings import get_settings


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


async def _run(email: str, limit: int) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    repository = PostgresLegalRepository(settings.database_url)
    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """SELECT q.id,q.created_at,q.request,q.response,q.diagnostics
                        FROM question_history q
                        JOIN user_profiles u ON u.id=q.user_id
                        WHERE lower(u.email)=lower(:email)
                        ORDER BY q.created_at DESC LIMIT :limit"""
                    ),
                    {"email": email, "limit": max(1, min(limit, 100))},
                )
            )
            .mappings()
            .all()
        )
    await repository.engine.dispose()
    output = {
        "schema_version": "1",
        "email": email,
        "count": len(rows),
        "questions": [
            {
                "id": str(row["id"]),
                "created_at": row["created_at"].isoformat(),
                "question": row["request"].get("question"),
                "result_status": row["response"].get("result_status"),
                "diagnostics": row["diagnostics"] or {},
            }
            for row in rows
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = _arguments()
    asyncio.run(_run(arguments.email, arguments.limit))
