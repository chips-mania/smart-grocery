PREFERENCE_WEIGHTS: dict[str, dict[str, float]] = {
    "minimize_waste": {
        "waste": 0.50,
        "cost": 0.20,
        "discount": 0.10,
        "nutrition": 0.05,
        "sharing": 0.10,
        "diversity": 0.05,
    },
    "minimize_cost": {
        "waste": 0.20,
        "cost": 0.50,
        "discount": 0.15,
        "nutrition": 0.05,
        "sharing": 0.05,
        "diversity": 0.05,
    },
    "maximize_discount": {
        "waste": 0.15,
        "cost": 0.25,
        "discount": 0.45,
        "nutrition": 0.05,
        "sharing": 0.05,
        "diversity": 0.05,
    },
    "high_protein": {
        "waste": 0.20,
        "cost": 0.15,
        "discount": 0.10,
        "nutrition": 0.40,
        "sharing": 0.10,
        "diversity": 0.05,
    },
    "low_calorie": {
        "waste": 0.25,
        "cost": 0.15,
        "discount": 0.05,
        "nutrition": 0.40,
        "sharing": 0.10,
        "diversity": 0.05,
    },
    "balanced": {
        "waste": 0.30,
        "cost": 0.25,
        "discount": 0.15,
        "nutrition": 0.10,
        "sharing": 0.10,
        "diversity": 0.10,
    },
}

DEFAULT_PREFERENCE = "minimize_waste"


def get_weights(preference: str | None) -> dict[str, float]:
    key = preference or DEFAULT_PREFERENCE
    return PREFERENCE_WEIGHTS.get(key, PREFERENCE_WEIGHTS[DEFAULT_PREFERENCE])
