from app.services.cart_analyzer import CartAnalyzer

_analyzer = CartAnalyzer()


def analyze_cart(
    menus: list[str],
    people: int = 1,
    missing_pantry: list[str] | None = None,
    preference: str = "minimize_waste",
) -> dict:

    return _analyzer.analyze(
        menus=menus,
        people=people,
        missing_pantry=missing_pantry,
        preference=preference,
    )
