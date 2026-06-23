from pydantic import BaseModel, Field

from lms.platform.auth.roles import Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class UserResponse(BaseModel):
    id: str
    username: str
    role: Role
    display_name: str | None = None
    tenant_id: str | None = None
