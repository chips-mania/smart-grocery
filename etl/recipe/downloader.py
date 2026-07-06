import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ============================
# 환경변수
# ============================

load_dotenv()

API_KEY = os.getenv("FOOD_API_KEY")

if not API_KEY:
    raise RuntimeError("FOOD_API_KEY가 .env에 없습니다.")

SERVICE = "COOKRCP01"

BASE_URL = (
    f"http://openapi.foodsafetykorea.go.kr/api/"
    f"{API_KEY}/{SERVICE}/json"
)

SAVE_PATH = Path("data/raw/recipes_raw.json")

TOTAL = 100      # 개발용
STEP = 20        # 20개씩 호출


def fetch(start: int, end: int):
    url = f"{BASE_URL}/{start}/{end}"

    print(f"GET {url}")

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    return data.get("COOKRCP01", {}).get("row", [])


def main():
    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

    recipes = []

    for start in range(1, TOTAL + 1, STEP):
        end = min(start + STEP - 1, TOTAL)

        print(f"\nDownloading {start} ~ {end}")

        rows = fetch(start, end)

        print(f"Received : {len(rows)}")

        recipes.extend(rows)

        time.sleep(0.3)

    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(recipes)} recipes -> {SAVE_PATH}")


if __name__ == "__main__":
    main()