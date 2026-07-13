from urllib.parse import quote

import httpx


class SupabaseRawStorage:
    def __init__(self, *, url: str, service_role_key: str, bucket: str) -> None:
        self.url = url.rstrip("/")
        self.key = service_role_key
        self.bucket = bucket

    async def put(self, path: str, body: str, wire_format: str) -> str:
        target = f"{self.url}/storage/v1/object/{quote(self.bucket)}/{quote(path)}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                target,
                content=body.encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.key}",
                    "apikey": self.key,
                    "x-upsert": "true",
                    "Content-Type": "application/json"
                    if wire_format == "JSON"
                    else "application/xml",
                },
            )
        response.raise_for_status()
        return f"{self.bucket}/{path}"
