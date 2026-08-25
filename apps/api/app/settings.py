from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Process environment still has the highest priority. The second file
        # overrides the first one, matching Vercel/Next.js local conventions.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "에너지 법령 RAG"
    environment: Literal["development", "test", "production"] = "development"
    collector_state_dir: Path = Path(".collector-state")
    database_url: str | None = None
    direct_url: str | None = None
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_raw_bucket: str = "law-raw"
    ai_mode: Literal["auto", "off"] = "auto"
    # 검색 전용 응답과 AI 실패 시 그 응답으로 전환하는 fallback을 함께 제어한다.
    search_only_enabled: bool = False
    # 2026-08-25: OpenAI 생성 설정과 선택 분기를 제거했다. 답변·임베딩·질문 라우팅은
    # 단일 NVIDIA NIM 경로를 사용한다. 라우터 provider 실패·시간 초과는 검색 없는
    # routing_unavailable AI 응답이며, NVIDIA_API_KEY 부재가 search_only 자동 전환을 뜻하지는
    # 않는다(기본 search_only_enabled=false에서는 fail-closed).
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_answer_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    # D-010: 단일 QuestionRouter가 사용하는 NVIDIA 호환 모델 설정이다. tier 조합이나
    # embedding hint를 전달하지 않으며, 라우팅 실패 판단은 애플리케이션이
    # routing_unavailable 안전 응답으로 만든다.
    nvidia_route_classifier_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    question_request_timeout_seconds: float = Field(default=52, gt=0, le=55)
    response_reserve_seconds: float = Field(default=3, ge=1, le=10)
    route_classifier_timeout_seconds: float = Field(default=8, gt=0, le=20)
    question_embedding_timeout_seconds: float = Field(default=5, gt=0, le=30)
    retrieval_timeout_seconds: float = Field(default=8, gt=0, le=20)
    answer_timeout_seconds: float = Field(default=40, gt=0, le=52)
    # 배치/오프라인 스크립트가 32개 passage를 한 번에 임베딩할 때 쓰는 HTTP 타임아웃
    # (원래 값). 질문 하나를 라이브 요청 예산 안에서 임베딩할 때는
    # question_embedding_timeout_seconds(5초)를 대신 쓴다 - 두 용도가 다른 시간
    # 예산이 필요해서 분리했다(Finding 1, 0045 최종 리뷰).
    embedding_timeout_seconds: float = Field(default=30, gt=0, le=120)
    answer_max_output_tokens: int = Field(default=4096, ge=256, le=16384)
    answer_evidence_max_characters: int = Field(default=60000, ge=4000, le=250000)
    answer_generation_max_attempts: int = Field(default=3, ge=1, le=5)
    nvidia_embedding_model: Literal["nvidia/nemotron-3-embed-1b"] = (
        "nvidia/nemotron-3-embed-1b"
    )
    embedding_dimensions: int = Field(default=512, ge=512, le=512)
    rate_limit_secret: str = Field(default="development-only-secret", min_length=16)
    authenticated_ai_daily_limit: int = Field(default=10, ge=1)
    authenticated_search_daily_limit: int = Field(default=100, ge=1)
    # 계정 quota 로직은 보존하되 현재는 끈다. 운영에서 다시 필요해지면 환경 변수
    # ACCOUNT_QUOTA_ENABLED=true만으로 기존 일일 한도를 복구할 수 있다(0037).
    account_quota_enabled: bool = False
    terms_version: str = "beta-2026-07-15"
    privacy_version: str = "beta-2026-07-15"
    # 2026-08-08: 콤마로 구분된 정확한 origin 목록을 지원한다(예: prod + 특정 preview
    # 배포). 여전히 정확한 origin만 받고 와일드카드(*.vercel.app 등)는 지원하지 않는다 -
    # CORS는 정확히 알고 승인한 origin만 열어야 한다는 원칙을 유지한다.
    web_origin: str = "http://localhost:3000"
    request_timeout_seconds: float = 30

    @property
    def web_origins(self) -> list[str]:
        return [origin.strip() for origin in self.web_origin.split(",") if origin.strip()]

    @field_validator("supabase_secret_key", mode="before")
    @classmethod
    def validate_supabase_secret_key(cls, value: object) -> object:
        if value in {None, ""}:
            return None
        if not isinstance(value, str) or not value.startswith("sb_secret_"):
            raise ValueError("SUPABASE_SECRET_KEY must start with sb_secret_")
        return value

    @model_validator(mode="after")
    def validate_production_dependencies(self) -> Settings:
        if self.response_reserve_seconds >= self.question_request_timeout_seconds:
            raise ValueError("response reserve must be smaller than question request timeout")
        if self.answer_timeout_seconds > (
            self.question_request_timeout_seconds - self.response_reserve_seconds
        ):
            raise ValueError("answer timeout must fit before the response reserve")
        if self.environment != "production":
            return self
        missing = [
            name
            for name, value in (
                ("DATABASE_URL", self.database_url),
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_SECRET_KEY", self.supabase_secret_key),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"production requires {', '.join(missing)}")
        if self.rate_limit_secret == "development-only-secret":
            raise ValueError("production requires a non-default RATE_LIMIT_SECRET")
        return self

    @property
    def ai_enabled(self) -> bool:
        return self.ai_mode == "auto" and bool(self.nvidia_api_key)

    @property
    def embedding_enabled(self) -> bool:
        return self.ai_mode == "auto" and bool(self.nvidia_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
