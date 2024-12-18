# function_calling.py

from typing import Optional, List
from sqlalchemy.orm import Session
from db import get_db, Menu
import difflib

def get_closest_menu_name(query: str, db: Session) -> Optional[str]:
    menus = db.query(Menu).all()
    menu_names = [m.name for m in menus]
    matches = difflib.get_close_matches(query, menu_names, n=1, cutoff=0.6)
    if matches:
        return matches[0]
    return None

def get_all_menus(db: Session) -> List[str]:
    menus = db.query(Menu).all()
    return [m.name for m in menus]

def get_menu_info_from_db(menu_name: str, db: Session):
    menu = db.query(Menu).filter(Menu.name == menu_name).first()
    if menu:
        return {
            "name": menu.name,
            "ingredients": menu.ingredients,
            "allergies": menu.allergies,
            "is_halal": menu.is_halal
        }
    closest = get_closest_menu_name(menu_name, db)
    if closest:
        menu = db.query(Menu).filter(Menu.name == closest).first()
        return {
            "name": menu.name,
            "ingredients": menu.ingredients,
            "allergies": menu.allergies,
            "is_halal": menu.is_halal
        }
    return None

def get_all_menu_details(db: Session):
    menus = db.query(Menu).all()
    menu_list = []
    for m in menus:
        menu_list.append({
            "name": m.name,
            "ingredients": m.ingredients,
            "allergies": m.allergies,
            "is_halal": m.is_halal
        })
    return menu_list
