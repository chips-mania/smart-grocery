from playwright.sync_api import sync_playwright
import json


def fetch_products():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        page = browser.new_page()

        responses = []

        def handle_response(response):
            if "/products?" in response.url:
                try:
                    data = response.json()
                    responses.append(data)
                    print(f"Captured: {response.url}")
                except Exception:
                    pass

        page.on("response", handle_response)

        page.goto("https://www.kurly.com/categories/907?page=1")

        page.wait_for_timeout(8000)

        browser.close()

        return responses


if __name__ == "__main__":
    products = fetch_products()

    print(f"Captured {len(products)} responses")

    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)