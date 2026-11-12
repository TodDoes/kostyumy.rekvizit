from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import Availability, PublicationStatus, RequestStatus, Role


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    name: str
    role: Role


class ItemCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=5000)
    color: str = Field(min_length=2, max_length=80)
    material: str = Field(min_length=2, max_length=120)
    size: str = Field(min_length=1, max_length=80)
    measurements: str = Field(min_length=3, max_length=1000)
    style: str = Field(min_length=2, max_length=100)
    condition: str = Field(min_length=2, max_length=80)
    defects: str = Field(default="", max_length=3000)
    transfer_type: str = Field(pattern="^(Аренда|Продажа|Передача)$")
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    availability: Availability = Availability.AVAILABLE
    publish: bool = False


class ItemOut(BaseModel):
    id: str
    title: str
    category: str
    description: str
    material: str
    size: str
    color: str
    measurements: str
    style: str
    condition: str
    defects: str
    transfer_type: str
    price: Decimal
    availability: Availability
    publication_status: PublicationStatus
    owner: UserOut
    photos: list[str]
    created_at: datetime


class RequestCreate(BaseModel):
    message: str = Field(default="", max_length=3000)


class RequestStatusUpdate(BaseModel):
    status: RequestStatus


class RequestOut(BaseModel):
    id: int
    item_id: str
    requester_id: int
    owner_id: int
    message: str
    status: RequestStatus
    created_at: datetime


class ModerationIn(BaseModel):
    status: PublicationStatus
    reason: str = Field(default="", max_length=1000)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


class MessageOut(BaseModel):
    id: int
    sender_id: int
    body: str
    created_at: datetime
