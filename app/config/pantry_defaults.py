DEFAULT_PANTRY_LABELS = [
    "간장",
    "참기름",
    "소금",
    "고춧가루",
    "고추가루",
    "김치",
    "된장",
    "고추장",
    "식용유",
    "올리브오일",
    "카놀라유",
    "포도씨유",
    "해바라기유",
    "마늘",
    "다진마늘",
    "설탕",
    "후추",
    "식초",
    "맛술",
    "청주",
    "물",
    "올리고당",
    "국간장",
    "진간장",
    "양념간장",
    "식빵",
    "버터",
    "참깨",
    "통깨",
    "깨",
    "들기름",
    "새우젓",
    "멸치액젓",
    "후춧가루",
    "다시다",
    "참치액",
    "굴소스",
]

PANTRY_ASSUMPTION_NOTE = (
    "간장·참기름·소금·고춧가루·김치 등 기본 양념·조미료는 집에 있다고 가정해 "
    "장보기 비용에서 제외했습니다. 없는 재료가 있으면 missing_pantry에 넣어 "
    "다시 요청하세요."
)


def is_cooking_oil(ingredient_name: str) -> bool:
    compact = ingredient_name.replace(" ", "").strip().lower()
    if not compact:
        return False
    excludes = {"우유", "두유", "콩유", "요구르트", "밀크"}
    if compact in excludes or compact.endswith("우유"):
        return False
    return compact.endswith("유") or compact.endswith("오일") or "기름" in compact


def is_pantry_ingredient(
    ingredient_name: str,
    *,
    missing_pantry: set[str] | None = None,
) -> bool:

    missing_pantry = missing_pantry or set()
    compact = ingredient_name.replace(" ", "").strip().lower()

    for missing in missing_pantry:
        if ingredients_overlap(compact, missing):
            return False

    for label in DEFAULT_PANTRY_LABELS:
        if ingredients_overlap(compact, label):
            return True

    if is_cooking_oil(ingredient_name):
        return True

    return False


def ingredients_overlap(left: str, right: str) -> bool:

    a = left.replace(" ", "").strip().lower()
    b = right.replace(" ", "").strip().lower()
    if not a or not b:
        return False
    return a == b or a in b or b in a


def normalize_missing_pantry(items: list[str] | None) -> set[str]:

    if not items:
        return set()
    return {item.strip() for item in items if item and item.strip()}
