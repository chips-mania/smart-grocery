from app.services.menu_replacer import MenuReplacer

_replacer = MenuReplacer()


def replace_menu(
    current_menus: list[str],
    menu_to_replace: str,
    people: int = 1,
    preference: str = "minimize_waste",
) -> dict:

    return _replacer.replace(
        current_menus=current_menus,
        menu_to_replace=menu_to_replace,
        people=people,
        preference=preference,
    )
