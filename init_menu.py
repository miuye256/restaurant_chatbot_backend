from db import get_db, Menu, Base, engine
Base.metadata.create_all(bind=engine)

db = next(get_db())

menu_data = [
    {"name": "チキンカレー", "ingredients": "鶏肉,玉ねぎ,スパイス", "allergies": "なし", "is_halal": True},
    {"name": "ビーフカレー", "ingredients": "牛肉,玉ねぎ,スパイス", "allergies": "牛肉アレルギー", "is_halal": False},
    {"name": "野菜カレー", "ingredients": "ジャガイモ,ニンジン,玉ねぎ,スパイス", "allergies": "なし", "is_halal": True},
]

for m in menu_data:
    menu = Menu(**m)
    db.add(menu)
db.commit()
db.close()
