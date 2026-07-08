"""Recipe nutrition helpers: outlier correction and protein-density scoring."""

from __future__ import annotations

MACRO_TOLERANCE = 1.15
MAX_PROTEIN_G = 80.0
FALLBACK_PROTEIN_CALORIE_SHARE = 0.12


def _macro_kcal(protein: float, carb: float, fat: float) -> float:
    return protein * 4 + carb * 4 + fat * 9


def get_effective_protein(recipe: dict) -> float:
    """Return a sane protein value for ranking and summaries."""

    protein = float(recipe.get("protein") or 0)
    kcal = float(recipe.get("kcal") or 0)
    carb = float(recipe.get("carb") or 0)
    fat = float(recipe.get("fat") or 0)

    if protein <= 0:
        return 0.0

    if kcal <= 0:
        return min(protein, MAX_PROTEIN_G)

    macro_total = _macro_kcal(protein, carb, fat)
    if macro_total > kcal * MACRO_TOLERANCE:
        residual = kcal - carb * 4 - fat * 9
        if residual > 0:
            return round(min(protein, residual / 4), 1)
        return round(min(protein, kcal * FALLBACK_PROTEIN_CALORIE_SHARE / 4), 1)

    if protein > MAX_PROTEIN_G:
        return MAX_PROTEIN_G

    return round(protein, 1)


def is_nutrition_adjusted(recipe: dict) -> bool:
    raw = float(recipe.get("protein") or 0)
    return raw > 0 and get_effective_protein(recipe) != round(raw, 1)


def get_protein_density(recipe: dict) -> float:
    """Grams of effective protein per 100 kcal."""

    kcal = float(recipe.get("kcal") or 0)
    if kcal <= 0:
        return 0.0
    return round(get_effective_protein(recipe) / kcal * 100, 2)


def enrich_recipe_nutrition(recipe: dict) -> dict:
    """Attach effective nutrition fields to a recipe dict (mutates copy)."""

    enriched = dict(recipe)
    effective = get_effective_protein(recipe)
    enriched["protein_g"] = effective
    enriched["protein_raw"] = recipe.get("protein")
    enriched["protein_density"] = get_protein_density(recipe)
    enriched["nutrition_adjusted"] = is_nutrition_adjusted(recipe)
    return enriched


def high_protein_sort_key(recipe: dict) -> tuple[float, float]:
    """Sort key for high-protein selection: density first, then absolute protein."""

    return (get_protein_density(recipe), get_effective_protein(recipe))


def get_effective_kcal(recipe: dict) -> float:
    return float(recipe.get("kcal") or 0)


def low_calorie_sort_key(recipe: dict) -> tuple[float, float]:
    """Sort key for low-calorie selection: kcal ascending, protein descending tiebreaker."""

    kcal = get_effective_kcal(recipe)
    if kcal <= 0:
        return (float("inf"), 0.0)
    return (kcal, -get_effective_protein(recipe))
