# auth_schemas.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# -------------------------------
# ✅ User Registration Input
# -------------------------------
class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


# -------------------------------
# 🔐 Login Input
# -------------------------------
class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


# -------------------------------
# 🧑 Public User Profile
# -------------------------------
class UserPublicProfile(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime


# -------------------------------
# 🪪 JWT or Auth Response
# -------------------------------
class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublicProfile


# -------------------------------
# ⚠️ Generic Error Response
# -------------------------------
class ErrorResponse(BaseModel):
    success: bool = False
    message: str
