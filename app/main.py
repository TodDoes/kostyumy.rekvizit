from contextlib import asynccontextmanager
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4
import csv

import qrcode
import qrcode.image.svg
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .database import Base, engine
from .dependencies import AdminUser, CurrentUser, Db, OptionalUser
from .models import (AuditLog, Availability, DealRequest, Favorite, Item, ItemHistory,
                     ItemPhoto, Message, PublicationStatus, RequestStatus, Role, User, now)
from .schemas import (ItemCreate, ItemOut, LoginIn, MessageCreate, MessageOut, ModerationIn,
                      RegisterIn, RequestCreate, RequestOut, RequestStatusUpdate, TokenOut, UserOut)
from .security import create_access_token, hash_password, verify_password

ROOT_DIR = Path(__file__).resolve().parent.parent
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
REQUEST_TRANSITIONS = {
    RequestStatus.NEW: {RequestStatus.DISCUSSING, RequestStatus.CANCELLED},
    RequestStatus.DISCUSSING: {RequestStatus.AGREED, RequestStatus.CANCELLED},
    RequestStatus.AGREED: {RequestStatus.COMPLETED, RequestStatus.CANCELLED},
    RequestStatus.COMPLETED: set(),
    RequestStatus.CANCELLED: set(),
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Костюмы.Реквизит API", version="1.0.0", lifespan=lifespan)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


def audit(db: Session, actor_id: int | None, action: str, entity_type: str, entity_id: str, details: str = "") -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


def history(db: Session, item: Item, actor_id: int | None, action: str, description: str) -> None:
    db.add(ItemHistory(item_id=item.id, author_id=actor_id, action=action, description=description))


def item_or_404(db: Session, public_id: str) -> Item:
    item = db.scalar(select(Item).where(Item.public_id == public_id).options(selectinload(Item.owner), selectinload(Item.photos)))
    if not item:
        raise HTTPException(status_code=404, detail="Изделие не найдено")
    return item


def item_out(item: Item) -> ItemOut:
    return ItemOut(
        id=item.public_id, title=item.title, category=item.category, description=item.description,
        material=item.material, size=item.size, color=item.color, measurements=item.measurements,
        style=item.style, condition=item.condition,
        defects=item.defects, transfer_type=item.transfer_type, price=item.price,
        availability=item.availability, publication_status=item.publication_status,
        owner=UserOut.model_validate(item.owner), photos=[photo.path if photo.path.startswith(("http://", "https://")) else f"/uploads/{photo.path}" for photo in item.photos],
        created_at=item.created_at,
    )


@app.post("/api/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Db):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Этот email уже зарегистрирован")
    user = User(email=payload.email.lower(), name=payload.name, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    audit(db, user.id, "user_registered", "user", str(user.id))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role.value))


@app.post("/api/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Db):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now() + timedelta(minutes=15)
            db.commit()
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if user.locked_until and user.locked_until > now():
        raise HTTPException(status_code=423, detail="Вход временно заблокирован после пяти неудачных попыток")
    user.failed_login_attempts, user.locked_until = 0, None
    audit(db, user.id, "user_login", "user", str(user.id))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role.value))


@app.get("/api/me", response_model=UserOut)
def me(current_user: CurrentUser):
    return current_user


@app.get("/api/items", response_model=list[ItemOut])
def list_items(
    db: Db, q: str | None = None, category: str | None = None, size: str | None = None,
    material: str | None = None, color: str | None = None, measurements: str | None = None,
    style: str | None = None, condition: str | None = None,
    transfer_type: str | None = None, page: int = Query(1, ge=1), per_page: int = Query(12, ge=12, le=20),
):
    statement = select(Item).where(Item.publication_status == PublicationStatus.PUBLISHED, Item.availability == Availability.AVAILABLE)
    for field, value in ((Item.category, category), (Item.size, size), (Item.material, material), (Item.color, color), (Item.measurements, measurements), (Item.style, style), (Item.condition, condition), (Item.transfer_type, transfer_type)):
        if value:
            statement = statement.where(field.ilike(f"%{value}%"))
    if q:
        like = f"%{q}%"
        statement = statement.where(or_(Item.title.ilike(like), Item.description.ilike(like), Item.material.ilike(like), Item.color.ilike(like), Item.style.ilike(like)))
    items = db.scalars(statement.order_by(Item.created_at.desc()).offset((page - 1) * per_page).limit(per_page).options(selectinload(Item.owner), selectinload(Item.photos))).all()
    return [item_out(item) for item in items]


@app.get("/api/me/items", response_model=list[ItemOut])
def my_items(current_user: CurrentUser, db: Db):
    items = db.scalars(select(Item).where(Item.owner_id == current_user.id).order_by(Item.created_at.desc()).options(selectinload(Item.owner), selectinload(Item.photos))).all()
    return [item_out(item) for item in items]


@app.post("/api/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, current_user: CurrentUser, db: Db, idempotency_key: str | None = Header(None, max_length=100)):
    if idempotency_key:
        existing = db.scalar(select(Item).where(Item.owner_id == current_user.id, Item.idempotency_key == idempotency_key).options(selectinload(Item.owner), selectinload(Item.photos)))
        if existing:
            return item_out(existing)
    data = payload.model_dump()
    data["publication_status"] = PublicationStatus.DRAFT
    data.pop("publish")
    item = Item(owner_id=current_user.id, idempotency_key=idempotency_key, **data)
    db.add(item)
    db.flush()
    history(db, item, current_user.id, "created", "Карточка изделия создана")
    audit(db, current_user.id, "item_created", "item", item.public_id)
    db.commit()
    return item_out(item_or_404(db, item.public_id))


@app.get("/api/items/{public_id}", response_model=ItemOut)
def get_item(public_id: str, db: Db, current_user: OptionalUser):
    item = item_or_404(db, public_id)
    if item.publication_status != PublicationStatus.PUBLISHED and (not current_user or current_user.id != item.owner_id):
        raise HTTPException(status_code=404, detail="Изделие не найдено")
    return item_out(item)


@app.post("/api/items/{public_id}/photos", response_model=ItemOut)
async def upload_photos(public_id: str, current_user: CurrentUser, db: Db, files: list[UploadFile] = File(...)):
    item = item_or_404(db, public_id)
    if item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Редактировать карточку может только её владелец")
    if len(item.photos) + len(files) > 8:
        raise HTTPException(status_code=422, detail="К карточке можно добавить не более 8 фотографий")
    for position, file in enumerate(files, start=len(item.photos)):
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=415, detail="Допустимы только JPG, PNG и WebP")
        content = await file.read()
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Размер фотографии не должен превышать 10 МБ")
        filename = f"{uuid4()}{ALLOWED_IMAGE_TYPES[file.content_type]}"
        (settings.upload_dir / filename).write_bytes(content)
        db.add(ItemPhoto(item_id=item.id, path=filename, position=position))
    history(db, item, current_user.id, "photos_added", f"Добавлено фотографий: {len(files)}")
    db.commit()
    return item_out(item_or_404(db, public_id))


@app.post("/api/items/{public_id}/publish", response_model=ItemOut)
def publish_item(public_id: str, current_user: CurrentUser, db: Db):
    item = item_or_404(db, public_id)
    if item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Публиковать карточку может только её владелец")
    if not item.photos:
        raise HTTPException(status_code=422, detail="Для публикации нужна хотя бы одна фотография")
    item.publication_status = PublicationStatus.PENDING
    history(db, item, current_user.id, "submitted_for_moderation", "Объявление отправлено на модерацию")
    audit(db, current_user.id, "item_submitted", "item", item.public_id)
    db.commit()
    return item_out(item_or_404(db, public_id))


@app.get("/api/items/{public_id}/history")
def get_history(public_id: str, db: Db):
    item = item_or_404(db, public_id)
    rows = db.scalars(select(ItemHistory).where(ItemHistory.item_id == item.id).order_by(ItemHistory.created_at)).all()
    return [{"action": row.action, "description": row.description, "author_id": row.author_id, "created_at": row.created_at} for row in rows]


@app.get("/api/items/{public_id}/qr")
def get_qr(public_id: str, db: Db, format: str = Query("svg", pattern="^(svg|png)$")):
    item_or_404(db, public_id)
    url = f"{settings.app_url.rstrip('/')}/item/{public_id}"
    if format == "svg":
        image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, error_correction=qrcode.constants.ERROR_CORRECT_M)
        output = BytesIO(); image.save(output)
        return Response(output.getvalue(), media_type="image/svg+xml")
    image = qrcode.make(url, error_correction=qrcode.constants.ERROR_CORRECT_M)
    output = BytesIO(); image.save(output, format="PNG")
    return Response(output.getvalue(), media_type="image/png")


@app.put("/api/items/{public_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(public_id: str, current_user: CurrentUser, db: Db):
    item = item_or_404(db, public_id)
    if not db.get(Favorite, {"user_id": current_user.id, "item_id": item.id}):
        db.add(Favorite(user_id=current_user.id, item_id=item.id)); db.commit()
    return Response(status_code=204)


@app.delete("/api/items/{public_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(public_id: str, current_user: CurrentUser, db: Db):
    item = item_or_404(db, public_id)
    favorite = db.get(Favorite, {"user_id": current_user.id, "item_id": item.id})
    if favorite:
        db.delete(favorite); db.commit()
    return Response(status_code=204)


@app.get("/api/me/favorites", response_model=list[ItemOut])
def favorites(current_user: CurrentUser, db: Db):
    items = db.scalars(select(Item).join(Favorite).where(Favorite.user_id == current_user.id).options(selectinload(Item.owner), selectinload(Item.photos))).all()
    return [item_out(item) for item in items]


@app.post("/api/items/{public_id}/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(public_id: str, payload: RequestCreate, current_user: CurrentUser, db: Db):
    item = item_or_404(db, public_id)
    if item.owner_id == current_user.id:
        raise HTTPException(status_code=422, detail="Нельзя создать заявку на собственное изделие")
    if item.publication_status != PublicationStatus.PUBLISHED or item.availability != Availability.AVAILABLE:
        raise HTTPException(status_code=422, detail="Изделие недоступно для заявки")
    request = DealRequest(item_id=item.id, requester_id=current_user.id, owner_id=item.owner_id, message=payload.message)
    db.add(request); db.flush()
    history(db, item, current_user.id, "request_created", "Создана заявка на передачу изделия")
    audit(db, current_user.id, "request_created", "request", str(request.id)); db.commit()
    return RequestOut(id=request.id, item_id=item.public_id, requester_id=request.requester_id, owner_id=request.owner_id, message=request.message, status=request.status, created_at=request.created_at)


@app.get("/api/me/requests", response_model=list[RequestOut])
def my_requests(current_user: CurrentUser, db: Db):
    requests = db.scalars(select(DealRequest).where(or_(DealRequest.requester_id == current_user.id, DealRequest.owner_id == current_user.id)).order_by(DealRequest.created_at.desc())).all()
    item_ids = {request.item_id for request in requests}; items = {item.id: item.public_id for item in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()} if item_ids else {}
    return [RequestOut(id=row.id, item_id=items[row.item_id], requester_id=row.requester_id, owner_id=row.owner_id, message=row.message, status=row.status, created_at=row.created_at) for row in requests]


@app.patch("/api/requests/{request_id}/status", response_model=RequestOut)
def change_request_status(request_id: int, payload: RequestStatusUpdate, current_user: CurrentUser, db: Db):
    request = db.get(DealRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if current_user.id not in {request.requester_id, request.owner_id}:
        raise HTTPException(status_code=403, detail="Менять статус могут только участники сделки")
    if payload.status not in REQUEST_TRANSITIONS[request.status]:
        raise HTTPException(status_code=422, detail="Недопустимый переход статуса")
    if payload.status in {RequestStatus.AGREED, RequestStatus.COMPLETED} and current_user.id != request.owner_id:
        raise HTTPException(status_code=403, detail="Подтверждать и завершать сделку может владелец изделия")
    request.status = payload.status
    item = db.get(Item, request.item_id)
    history(db, item, current_user.id, "request_status_changed", f"Статус заявки изменён на {payload.status.value}")
    audit(db, current_user.id, "request_status_changed", "request", str(request.id), payload.status.value)
    db.commit()
    return RequestOut(id=request.id, item_id=item.public_id, requester_id=request.requester_id, owner_id=request.owner_id, message=request.message, status=request.status, created_at=request.created_at)


def request_or_403(request_id: int, current_user: User, db: Session) -> DealRequest:
    request = db.get(DealRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if current_user.id not in {request.requester_id, request.owner_id}:
        raise HTTPException(status_code=403, detail="Переписка доступна только участникам сделки")
    return request


@app.get("/api/requests/{request_id}/messages", response_model=list[MessageOut])
def get_messages(request_id: int, current_user: CurrentUser, db: Db):
    request_or_403(request_id, current_user, db)
    rows = db.scalars(select(Message).where(Message.request_id == request_id).order_by(Message.created_at)).all()
    return [MessageOut(id=row.id, sender_id=row.sender_id, body=row.body, created_at=row.created_at) for row in rows]


@app.post("/api/requests/{request_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(request_id: int, payload: MessageCreate, current_user: CurrentUser, db: Db):
    request = request_or_403(request_id, current_user, db)
    if request.status in {RequestStatus.COMPLETED, RequestStatus.CANCELLED}:
        raise HTTPException(status_code=422, detail="Переписка по закрытой сделке недоступна")
    message = Message(request_id=request.id, sender_id=current_user.id, body=payload.body.strip())
    db.add(message)
    if request.status == RequestStatus.NEW:
        request.status = RequestStatus.DISCUSSING
    audit(db, current_user.id, "message_sent", "request", str(request.id))
    db.commit()
    return MessageOut(id=message.id, sender_id=message.sender_id, body=message.body, created_at=message.created_at)


@app.get("/api/admin/items/pending", response_model=list[ItemOut])
def pending_items(admin: AdminUser, db: Db):
    items = db.scalars(select(Item).where(Item.publication_status == PublicationStatus.PENDING).order_by(Item.created_at).options(selectinload(Item.owner), selectinload(Item.photos))).all()
    return [item_out(item) for item in items]


@app.patch("/api/admin/items/{public_id}/moderation", response_model=ItemOut)
def moderate_item(public_id: str, payload: ModerationIn, admin: AdminUser, db: Db):
    if payload.status not in {PublicationStatus.PUBLISHED, PublicationStatus.BLOCKED}:
        raise HTTPException(status_code=422, detail="Модератор может только опубликовать или заблокировать объявление")
    item = item_or_404(db, public_id)
    item.publication_status = payload.status
    history(db, item, admin.id, "moderated", payload.reason or f"Статус: {payload.status.value}")
    audit(db, admin.id, "item_moderated", "item", item.public_id, payload.status.value)
    db.commit()
    return item_out(item_or_404(db, public_id))


@app.get("/api/admin/reports/deals.csv")
def deals_report(admin: AdminUser, db: Db):
    output = StringIO(); writer = csv.writer(output); writer.writerow(["request_id", "item_id", "requester_id", "owner_id", "status", "created_at"])
    for row in db.scalars(select(DealRequest).order_by(DealRequest.created_at)).all():
        writer.writerow([row.id, row.item_id, row.requester_id, row.owner_id, row.status.value, row.created_at.isoformat()])
    return StreamingResponse(iter(["\ufeff" + output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=deals.csv"})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(ROOT_DIR / "index.html")


@app.get("/styles.css", include_in_schema=False)
def frontend_styles():
    return FileResponse(ROOT_DIR / "styles.css", media_type="text/css")
