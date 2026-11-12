from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


class PublicationStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    BLOCKED = "blocked"


class Availability(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    UNAVAILABLE = "unavailable"


class RequestStatus(str, Enum):
    NEW = "new"
    DISCUSSING = "discussing"
    AGREED = "agreed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(SqlEnum(Role), default=Role.USER)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    items: Mapped[list["Item"]] = relationship(back_populates="owner")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_catalog", "publication_status", "availability", "category", "condition", "color"),
        Index("ix_items_search", "category", "style", "material", "color", "size"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_item_idempotency"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid4()), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(180), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(80), index=True)
    material: Mapped[str] = mapped_column(String(120), index=True)
    size: Mapped[str] = mapped_column(String(80), index=True)
    measurements: Mapped[str] = mapped_column(Text)
    style: Mapped[str] = mapped_column(String(100), index=True)
    condition: Mapped[str] = mapped_column(String(80), index=True)
    defects: Mapped[str] = mapped_column(Text, default="")
    transfer_type: Mapped[str] = mapped_column(String(40), index=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    availability: Mapped[Availability] = mapped_column(SqlEnum(Availability), default=Availability.AVAILABLE)
    publication_status: Mapped[PublicationStatus] = mapped_column(SqlEnum(PublicationStatus), default=PublicationStatus.DRAFT, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    owner: Mapped[User] = relationship(back_populates="items")
    photos: Mapped[list["ItemPhoto"]] = relationship(back_populates="item", cascade="all, delete-orphan", order_by="ItemPhoto.position")
    history: Mapped[list["ItemHistory"]] = relationship(back_populates="item", order_by="ItemHistory.created_at")


class ItemPhoto(Base):
    __tablename__ = "item_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    item: Mapped[Item] = relationship(back_populates="photos")


class ItemHistory(Base):
    __tablename__ = "item_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    item: Mapped[Item] = relationship(back_populates="history")


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DealRequest(Base):
    __tablename__ = "deal_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[RequestStatus] = mapped_column(SqlEnum(RequestStatus), default=RequestStatus.NEW, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("deal_requests.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
