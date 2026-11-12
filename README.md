# Костюмы Реквизит

Бэкенд информационно-справочной C2C-платформы театрального реквизита. Приложение предоставляет REST API и отдаёт переданную HTML/CSS-вёрстку по адресу `http://localhost:8000`.

## Запуск

1. Скопируйте `.env.example` в `.env` и замените `JWT_SECRET` на длинное случайное значение.
2. Выполните `docker compose up --build`.
3. Откройте `http://localhost:8000/docs` для интерактивной документации API.

PostgreSQL доступен на `localhost:5432`, приложение — на `localhost:8000`. При первом запуске таблицы создаются автоматически.

Для запуска без Docker установите зависимости из `requirements.txt`, задайте `DATABASE_URL` и выполните:

```powershell
uvicorn app.main:app --reload
```

## Основные сценарии API

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/me` — учётные записи и JWT-авторизация. Пароли хэшируются Argon2; после пяти неверных попыток вход блокируется на 15 минут.
- `GET /api/items` — публичный каталог с фильтрами `q`, `category`, `size`, `material`, `style`, `condition`, `transfer_type` и постраничной выдачей 12–20 карточек.
- `POST /api/items`, `POST /api/items/{id}/photos`, `POST /api/items/{id}/publish` — черновик карточки, загрузка до 8 JPG/PNG/WebP-фотографий по 10 МБ и отправка на модерацию. Заголовок `idempotency_key` предотвращает дубли при повторной отправке.
- `GET /api/items/{id}/qr?format=svg|png` — постоянный QR-код карточки. `GET /api/items/{id}/history` возвращает только добавляемую историю.
- `PUT|DELETE /api/items/{id}/favorite`, `GET /api/me/favorites` — избранное.
- `POST /api/items/{id}/requests`, `GET /api/me/requests`, `PATCH /api/requests/{id}/status` — заявки. Допустимые переходы: новая → обсуждение → согласована → завершена, с отменой до завершения.
- `PATCH /api/admin/items/{id}/moderation` и `GET /api/admin/reports/deals.csv` — модерация и CSV-отчёт администратора.

Все защищённые методы принимают `Authorization: Bearer <JWT>`. Роль администратора хранится в базе; её следует назначать через администрирование базы до появления отдельного интерфейса управления ролями.

## Соответствие ТЗ

В модели есть роли, объявления со статусами, отдельное файловое хранилище фото, поиск с индексами, неизменяемые журналы действий и истории изделий, QR-коды с постоянным `public_id`, избранное, сделки с проверкой прав/переходов и административный аудит. Docker Compose поднимает PostgreSQL отдельно от API; секреты и URL базы не фиксируются в репозитории.
