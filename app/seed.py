"""Create a realistic local demonstration dataset.

Run: python -m app.seed
The command is idempotent and never removes user data.
"""
from .database import Base, SessionLocal, engine
from .models import Item, ItemHistory, ItemPhoto, PublicationStatus, Role, User
from .security import hash_password


ITEMS = [
    ("Камзол эпохи Возрождения", "Костюмы", "Бордовый", "Бархат", "M", "Грудь 102 см; талия 88 см; длина 72 см; рост 176–182 см", "Возрождение", "Отличное", "Аренда", 4200, "1578632767115-351597cf2477"),
    ("Платье ампир с вышивкой", "Костюмы", "Кремовый", "Шёлк", "S", "Грудь 88 см; талия 68 см; длина 142 см; рост 164–170 см", "Ампир", "Отличное", "Аренда", 5800, "1539109136881-3be0616acf4b"),
    ("Мужской сюртук XIX века", "Костюмы", "Тёмно-синий", "Шерсть", "L", "Грудь 108 см; плечи 48 см; рукав 64 см; рост 180–188 см", "XIX век", "Хорошее", "Продажа", 12500, "1548883354-7622d03aca27"),
    ("Венецианская маска Коломбина", "Аксессуары", "Золотой", "Папье-маше", "Универсальный", "Ширина 19 см; высота 11 см", "Барокко", "Отличное", "Продажа", 3200, "1509631179647-0177331693ae"),
    ("Цилиндр театральный", "Головные уборы", "Чёрный", "Фетр", "57", "Обхват головы 57 см; высота 15 см", "XIX век", "Хорошее", "Аренда", 1600, "1521572163474-6864f9cf17ab"),
    ("Кафтан стрельца", "Костюмы", "Алый", "Сукно", "XL", "Грудь 116 см; талия 102 см; длина 108 см; рост 178–186 см", "Русское XVII века", "Хорошее", "Аренда", 4600, "1538805060517-1fee11a0b49c"),
    ("Туфли бальные", "Обувь", "Серебряный", "Кожа", "38", "Стелька 24,5 см; каблук 5 см", "Современность", "Отличное", "Продажа", 3900, "1543163521-1bf539c55dd2"),
    ("Мундир гусарский", "Костюмы", "Синий", "Сукно и галун", "M", "Грудь 100 см; талия 84 см; длина 68 см; рост 172–180 см", "XIX век", "Отличное", "Аренда", 6500, "1593032465175-481ac7f401a0"),
    ("Шаль цыганская", "Аксессуары", "Красный", "Шерсть", "Универсальный", "Ширина 150 см; длина 150 см", "XIX век", "Отличное", "Продажа", 2400, "1529139574466-a303027c1d8b"),
    ("Корона королевская", "Головные уборы", "Золотой", "Латунь и стразы", "Универсальный", "Диаметр 18 см; высота 12 см", "Барокко", "Хорошее", "Аренда", 2800, "1523170335258-f5ed11844a49"),
    ("Накидка мушкетёра", "Костюмы", "Синий", "Габардин", "L", "Плечи 50 см; длина 92 см; рост 176–184 см", "XVII век", "Хорошее", "Аренда", 3300, "1516822003754-cca485356ecb"),
    ("Веер кружевной", "Аксессуары", "Белый", "Кружево и дерево", "Универсальный", "Размах 42 см; длина 23 см", "XIX век", "Отличное", "Продажа", 1800, "1490481651871-ab68de25d43d"),
    ("Жилет викторианский", "Костюмы", "Изумрудный", "Парча", "M", "Грудь 100 см; талия 86 см; длина 58 см", "Викторианская эпоха", "Отличное", "Продажа", 7600, "1485230895905-ec40ba36b9bc"),
    ("Палаш бутафорский", "Бутафория", "Стальной", "Дерево и пластик", "Универсальный", "Длина 94 см; вес 0,6 кг", "XVIII век", "Хорошее", "Аренда", 1100, "1514894786522-189a8e6e68e7"),
    ("Плащ придворный", "Костюмы", "Фиолетовый", "Бархат", "XL", "Плечи 52 см; длина 138 см; рост 180–190 см", "Барокко", "Отличное", "Аренда", 7200, "1506629905607-d405b7a30db6"),
]


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(Item).first():
            print("В базе уже есть карточки; сидер ничего не изменил.")
            return
        admin = User(email="admin@costumes.local", name="Администратор", password_hash=hash_password("admin12345"), role=Role.ADMIN)
        owner = User(email="alina@example.local", name="Алина Театрова", password_hash=hash_password("user12345"), role=Role.USER)
        db.add_all([admin, owner]); db.flush()
        for index, (title, category, color, material, size, measurements, style, condition, transfer_type, price, photo_id) in enumerate(ITEMS):
            item = Item(owner_id=owner.id, title=title, category=category, color=color, material=material, size=size, measurements=measurements, style=style, condition=condition, defects="Следы сценического использования отсутствуют", transfer_type=transfer_type, price=price, publication_status=PublicationStatus.PENDING if index >= 13 else PublicationStatus.PUBLISHED)
            db.add(item); db.flush()
            url = f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w=900&q=85"
            db.add(ItemPhoto(item_id=item.id, path=url, position=0))
            db.add(ItemHistory(item_id=item.id, author_id=owner.id, action="seeded", description="Карточка добавлена демонстрационным наполнением"))
        db.commit()
        print("Добавлены 15 карточек. Админ: admin@costumes.local / admin12345")


if __name__ == "__main__":
    main()
