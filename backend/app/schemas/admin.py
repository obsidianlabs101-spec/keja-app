from pydantic import BaseModel
from pydantic import EmailStr


class AdminRegister(BaseModel):

    username: str
    full_name: str
    email: EmailStr
    password: str
    admin_secret: str


class AdminLogin(BaseModel):

    email: EmailStr
    password: str


class AdminProfile(BaseModel):

    id: str
    email: EmailStr
    username: str
    full_name: str
    is_active: bool

    class Config:
        from_attributes = True


from typing import Optional


class HostVerificationActionRequest(BaseModel):

    approve: bool
    note: Optional[str] = None


class TokenResponse(BaseModel):

    access_token: str
    token_type: str
