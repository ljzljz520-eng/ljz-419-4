from typing import List

from pydantic import BaseModel, ConfigDict, Field


class RegisterIn(BaseModel):
    """Public self-registration. Role is NOT accepted from the client:
    every account created here gets the default customer role."""

    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class UserCreateIn(BaseModel):
    """Admin-only account provisioning; the role is chosen by the admin."""

    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = "customer"


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserListOut(BaseModel):
    users: List[UserOut]
