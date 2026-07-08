"""Common culinary unit conversions.

Used when recipe units (e.g. 개/큰술/단/마리) must match package units (g/ml/count).
"""

from __future__ import annotations

_COUNT_TO_GRAMS: dict[str, dict[str, float]] = {
    "감자": {"개": 150, "알": 150, "덩이": 150},
    "양파": {"개": 200, "알": 200},
    "대파": {"대": 80, "줄기": 80, "줌": 50, "개": 80},
    "실파": {"대": 30, "줄기": 30},
    "계란": {"개": 55, "알": 55, "구": 55},
    "달걀": {"개": 55, "알": 55, "구": 55},
    "청양고추": {"개": 15, "알": 15},
    "홍고추": {"개": 20, "알": 20},
    "꽈리고추": {"개": 5, "알": 5},
    "당근": {"개": 100, "송이": 80, "대": 80},
    "호박": {"개": 300, "입": 300, "덩이": 300},
    "애호박": {"개": 300, "입": 300},
    "쥬키니": {"개": 200},
    "브로콜리": {"송이": 300, "개": 300},
    "배추": {"포기": 2000, "장": 1000, "개": 2000},
    "얼갈이": {"단": 400},
    "얼갈이배추": {"단": 400},
    "무": {"개": 400, "덩이": 400},
    "단무지": {"개": 30},
    "두부": {"모": 300, "팩": 300},
    "콩나물": {"줌": 100, "봉": 200},
    "시금치": {"줌": 100},
    "깻잎": {"장": 1, "줌": 30, "개": 2},
    "마늘": {"쪽": 3, "개": 5, "알": 5},
    "통마늘": {"개": 50, "알": 50, "쪽": 3},
    "생강": {"개": 20, "쪽": 5},
    "표고버섯": {"개": 20, "송이": 30},
    "팽이버섯": {"봉": 150, "팩": 150},
    "새송이버섯": {"개": 80},
    "사과": {"개": 200},
    "배": {"개": 250},
    "레몬": {"개": 80},
    "토마토": {"개": 150},
    "가지": {"개": 200},
    "오이": {"개": 150, "알": 150},
    "파프리카": {"개": 150},
    "고등어": {"마리": 350, "토막": 200},
    "닭고기": {"마리": 1000},
    "닭": {"마리": 1000},
    "삼겹살": {"인분": 200},
    "돼지고기": {"인분": 150},
}

_ALIASES: dict[str, str] = {
    "국산감자": "감자",
    "수미감자": "감자",
    "찰감자": "감자",
    "노랑파": "양파",
    "적양파": "양파",
    "쪽파": "대파",
    "알타리": "무",
}

_COUNT_UNITS = {
    "개",
    "구",
    "모",
    "대",
    "줄기",
    "알",
    "마리",
    "컵",
    "봉",
    "팩",
    "입",
    "송이",
    "쪽",
    "줌",
    "포기",
    "장",
    "덩이",
    "인분",
    "토막",
    "단",
}

_AMOUNT_UNITS_TO_ML: dict[str, float] = {
    "큰술": 15.0,
    "숟가락": 15.0,
    "큰스푼": 15.0,
    "작은술": 5.0,
    "티스푼": 5.0,
    "tsp": 5.0,
    "컵": 200.0,
    "종이컵": 180.0,
}

_DENSITY_G_PER_ML: dict[str, float] = {
    "물": 1.0,
    "간장": 1.15,
    "국간장": 1.15,
    "진간장": 1.15,
    "고추장": 1.2,
    "된장": 1.1,
    "고춧가루": 0.45,
    "소금": 1.2,
    "설탕": 0.85,
    "맛술": 1.0,
    "식초": 1.0,
    "올리고당": 1.4,
    "물엿": 1.4,
    "다진마늘": 0.8,
    "다진생강": 0.8,
    "참기름": 0.92,
    "들기름": 0.92,
    "식용유": 0.92,
    "올리브오일": 0.92,
    "카놀라유": 0.92,
    "참치액": 1.1,
    "멸치액젓": 1.1,
    "참치액젓": 1.1,
}


def _compact(name: str) -> str:
    return (name or "").replace(" ", "").strip().lower()


def resolve_ingredient_key(ingredient: str) -> str | None:
    compact = _compact(ingredient)
    if not compact:
        return None
    if compact in _ALIASES:
        return _ALIASES[compact]
    for key in _COUNT_TO_GRAMS:
        k = key.replace(" ", "").lower()
        if compact == k or k in compact or compact in k:
            return key
    return None


def grams_per_count_unit(ingredient: str, count_unit: str) -> float | None:
    key = resolve_ingredient_key(ingredient)
    if not key:
        return None
    unit = (count_unit or "").strip()
    table = _COUNT_TO_GRAMS.get(key, {})
    if unit in table:
        return table[unit]
    for u, grams in table.items():
        if u in unit or unit in u:
            return grams
    return None


def count_need_to_grams(ingredient: str, count: float, count_unit: str) -> float | None:
    gpc = grams_per_count_unit(ingredient, count_unit)
    if gpc is None or count <= 0:
        return None
    return round(float(count) * gpc, 2)


def _density_for_ingredient(ingredient: str) -> float | None:
    compact = _compact(ingredient)
    if not compact:
        return None
    for key, density in _DENSITY_G_PER_ML.items():
        k = _compact(key)
        if compact == k or k in compact or compact in k:
            return density
    return None


def normalize_need_to_mass(need: dict) -> dict:
    out = dict(need)
    ingredient = need.get("ingredient") or ""
    amount = need.get("required_amount") or 0.0
    unit = (need.get("required_unit") or "").strip()
    count = need.get("required_count") or 0.0
    count_unit = need.get("required_count_unit") or ""

    if amount and unit in _AMOUNT_UNITS_TO_ML:
        ml = float(amount) * _AMOUNT_UNITS_TO_ML[unit]
        density = _density_for_ingredient(ingredient)
        if density is not None:
            grams = round(ml * density, 2)
            out["required_amount"] = grams
            out["required_unit"] = "g"
            out["conversion_note"] = f"{amount:g}{unit} -> {grams:g}g (일반 밀도 환산)"
            return out
        out["required_amount"] = round(ml, 2)
        out["required_unit"] = "ml"
        out["conversion_note"] = f"{amount:g}{unit} -> {ml:g}ml (부피 환산)"
        return out

    if amount and unit.lower() in {u.lower() for u in _COUNT_UNITS}:
        grams = count_need_to_grams(ingredient, float(amount), unit)
        if grams is not None:
            out["required_amount"] = grams
            out["required_unit"] = "g"
            out["conversion_note"] = f"{amount:g}{unit} -> {grams:g}g (요리 일반 환산)"
            return out

    if amount and unit.lower() in {"g", "kg", "ml", "l"}:
        if unit.lower() == "kg":
            out["required_amount"] = float(amount) * 1000
            out["required_unit"] = "g"
        elif unit.lower() == "l":
            out["required_amount"] = float(amount) * 1000
            out["required_unit"] = "ml"
        out["conversion_note"] = None
        return out

    if count and count_unit:
        grams = count_need_to_grams(ingredient, float(count), count_unit)
        if grams is not None:
            out["required_amount"] = grams
            out["required_unit"] = "g"
            out["conversion_note"] = f"{count:g}{count_unit} -> {grams:g}g (요리 일반 환산)"
            return out

    return out
