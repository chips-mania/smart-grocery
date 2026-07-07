import json
import time
from pathlib import Path

import requests

from etl.common.logger import info, success, error

SEARCH_KEYWORDS = Path("data/processed/kurly/search_keywords.json")
OUTPUT_DIR = Path("data/raw/kurly")

URL = "https://api.kurly.com/search/v4/sites/market/normal-search"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


def search(keyword: str):

    params = {
        "keyword": keyword,
        "sortType": 4,
        "page": 1,
    }

    r = requests.get(
        URL,
        params=params,
        headers=HEADERS,
        timeout=20,
    )

    r.raise_for_status()

    return r.json()


def main():

    with open(SEARCH_KEYWORDS, encoding="utf-8") as f:
        keywords = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(keywords)

    info(f"Search Keywords : {total}")

    for idx, item in enumerate(keywords, start=1):

        keyword = item["search_keyword"]

        try:

            response = search(keyword)

            output = {
                "search_keyword": keyword,
                "ingredients": item.get("ingredients", []),
                "response": response,
            }

            filename = f"{idx:06d}.json"

            with open(
                OUTPUT_DIR / filename,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    output,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            success(f"[{idx}/{total}] {keyword}")

        except Exception as e:

            error(f"[{idx}/{total}] {keyword} : {e}")

        # 컬리 서버에 부담을 주지 않도록
        time.sleep(0.3)


if __name__ == "__main__":
    main()