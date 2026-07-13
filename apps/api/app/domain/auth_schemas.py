from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.domain.schemas import MockUser


class MockGoogleLoginRequest(BaseModel):
    email: Annotated[
        str,
        Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    ]
    display_name: Annotated[str, Field(min_length=1, max_length=80)]


class MockLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: MockUser
