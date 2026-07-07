# 알뜰장보기 Smart Grocery 개발계획서

## 1. 프로젝트 개요

### 1.1 프로젝트명

- 서비스명: 알뜰장보기
- 영문명/레포명: `smart-grocery`
- 제출 목적: 카카오 Agentic Player 10 공모전 제출용 MCP 서버
- 배포 형태: PlayMCP in KC에 MCP 서버 등록 후 PlayMCP 개발자 콘솔에서 임시 등록, 테스트, 심사 요청

### 1.2 한 줄 설명

사용자가 먹고 싶은 메뉴, 기간, 인원수, 하루 끼니 수, 예산 등을 입력하면 레시피에 필요한 식재료를 계산하고, 온라인 쇼핑몰 상품의 실제 판매 단위와 가격을 반영해 남는 재료와 비용을 최소화하는 장보기·식단 최적화 MCP 서비스.

### 1.3 핵심 문제의식

일반적인 레시피 서비스는 메뉴와 조리법을 알려주지만, 실제 장보기에서는 다음 문제가 발생한다.

1. 레시피는 양파 100g, 오이 2개처럼 필요한 양을 말한다.
2. 쇼핑몰은 양파 1kg, 오이 3입, 두부 300g처럼 더 큰 단위로 판매한다.
3. 사용자는 필요한 양보다 많이 사게 되고 재료가 남는다.
4. 남은 재료를 활용하지 못하면 낭비가 생긴다.
5. 메뉴를 바꿔도 완전히 엉뚱한 메뉴가 추천되면 사용자 의도와 맞지 않는다.

이 프로젝트는 단순히 “싼 상품”을 고르는 것이 아니라, **사용자가 먹고 싶은 식단을 최대한 유지하면서, 판매 단위·할인·남는 재료·메뉴 유사도까지 고려해 더 현명한 장보기 플랜을 제안**하는 것을 목표로 한다.

---

## 2. 최종적으로 구현되어야 하는 사용자 경험

### 2.1 사용자가 하는 질문 예시

사용자는 PlayMCP 채팅에서 다음과 같이 자연어로 질문한다.

#### 예시 1: 식단 계획

> 2명이 3일 동안 저녁만 집에서 먹을 건데, 예산 5만원 안에서 장보기 추천해줘. 김치찌개랑 카레는 먹고 싶어.

#### 예시 2: 메뉴 교체 제안

> 김치찌개를 빼면 더 저렴해질까? 비슷한 메뉴로 바꿔줘.

#### 예시 3: 장바구니 분석

> 내가 고른 메뉴는 김치찌개, 제육볶음, 계란말이야. 장보기 비용과 남는 재료를 알려줘.

#### 예시 4: 냉장고 재료 반영

> 집에 양파 반 개랑 계란 4개 있어. 이걸 반영해서 3끼 추천해줘.

#### 예시 5: 하루 끼니 수 반영

> 혼자 5일 동안 하루 2끼를 집에서 먹어. 같은 메뉴를 너무 반복하지 않게 추천해줘.

---

## 3. 사용자가 받아야 하는 응답 형태

최종 응답은 단순한 텍스트가 아니라, 다음 정보를 포함해야 한다.

### 3.1 추천 식단

예시:

```text
3일 저녁 식단 추천

1일차 저녁: 김치찌개
2일차 저녁: 카레
3일차 저녁: 계란말이 + 된장국
```

하루 끼니 수가 2끼 이상이면 다음처럼 표현한다.

```text
3일 / 하루 2끼 식단

1일차 점심: 김치찌개
1일차 저녁: 김치찌개 남은 분량 활용
2일차 점심: 카레
2일차 저녁: 계란말이
3일차 점심: 된장국
3일차 저녁: 제육볶음
```

### 3.2 필요한 식재료 합산

예시:

```text
필요 식재료 합산

양파: 1.5개 / 약 300g
대파: 0.7대 / 약 70g
돼지고기: 600g
두부: 1모
계란: 4개
```

### 3.3 추천 상품

식재료마다 실제 쇼핑몰 상품을 연결해 보여준다.

```text
추천 장보기 상품

양파
- 추천 상품: [컬리] 국내산 양파 3입
- 가격: 3,490원
- 필요한 양: 1.5개
- 예상 잔여: 1.5개
- 선택 이유: 1kg 상품보다 총 구매비가 낮고, 다른 메뉴에서 일부 활용 가능

두부
- 추천 상품: [컬리] 국산콩 두부 300g
- 가격: 1,980원
- 필요한 양: 1모
- 예상 잔여: 없음
```

### 3.4 절약·잔여 재료 설명

```text
절약 포인트

- 김치찌개와 제육볶음을 함께 선택하면 양파와 대파를 같이 사용할 수 있어 별도 구매가 줄어듭니다.
- 카레 대신 된장국을 선택하면 두부와 대파를 재사용할 수 있어 약 3,200원을 줄일 수 있습니다.
- 오이 3입 상품은 1개가 남지만, 다음 메뉴로 오이무침을 추가하면 잔여량을 줄일 수 있습니다.
```

### 3.5 메뉴 교체 제안

사용자가 이미 고른 메뉴가 있을 때, 메뉴를 바꾸는 경우는 반드시 유사 메뉴 위주로 제안한다.

잘못된 예:

```text
김치찌개 → 가지볶음
```

올바른 예:

```text
김치찌개 → 된장찌개
김치찌개 → 순두부찌개
김치찌개 → 부대찌개
```

교체 기준은 다음을 반영한다.

- 같은 카테고리인지: 국&찌개, 반찬, 밥, 일품, 후식 등
- 조리 방식이 유사한지: 끓이기, 볶기, 굽기, 찌기 등
- 공통 식재료가 많은지
- 추가 구매가 적은지
- 남는 재료를 줄이는지
- 사용자가 원래 고른 메뉴 의도를 보존하는지

---

## 4. 핵심 기능 정의

### 4.1 optimize_meal_plan

가장 중요한 MCP Tool.

사용자의 조건을 받아 식단과 장보기 상품 조합을 추천한다.

입력 예시:

```json
{
  "duration_days": 3,
  "meals_per_day": 1,
  "people": 2,
  "budget": 50000,
  "preferred_menus": ["김치찌개", "카레"],
  "fridge_items": [
    {"ingredient": "양파", "amount": 0.5, "unit": "ea"},
    {"ingredient": "계란", "amount": 4, "unit": "ea"}
  ],
  "avoid_ingredients": [],
  "preference_level": "balanced"
}
```

출력 내용:

- 추천 식단
- 필요한 재료 합산
- 추천 상품 목록
- 총 예상 비용
- 예산 초과 여부
- 남는 재료
- 절약 포인트
- 메뉴 선택 이유

### 4.2 replace_menu

사용자가 선택한 메뉴 중 하나를 다른 메뉴로 바꿨을 때 비용·잔여 재료가 어떻게 바뀌는지 분석한다.

중요 원칙:

- 완전히 다른 메뉴로 바꾸면 안 된다.
- 김치찌개는 된장찌개, 순두부찌개, 부대찌개처럼 유사 메뉴로 바꾼다.
- 메뉴 유사도와 비용 절감 효과를 같이 고려한다.

입력 예시:

```json
{
  "current_menus": ["김치찌개", "카레", "계란말이"],
  "menu_to_replace": "김치찌개",
  "people": 2,
  "duration_days": 3,
  "meals_per_day": 1
}
```

출력 예시:

```text
김치찌개 대신 된장찌개를 추천합니다.

이유:
- 두부, 대파, 양파를 그대로 활용할 수 있습니다.
- 추가 구매가 된장과 애호박 정도로 제한됩니다.
- 예상 장보기 비용이 약 3,800원 감소합니다.
- 국&찌개 카테고리라 원래 식단 의도와도 비슷합니다.
```

### 4.3 analyze_cart

사용자가 직접 고른 메뉴 또는 상품 장바구니를 분석한다.

출력:

- 현재 총 비용
- 남는 재료
- 과도하게 큰 상품
- 대체 상품 추천
- 메뉴 추가 또는 교체 제안

### 4.4 explain_plan

추천 결과를 사람이 이해하기 쉽게 설명한다.

출력:

- 왜 이 메뉴 조합인지
- 왜 이 상품을 선택했는지
- 할인/특가가 어떻게 반영됐는지
- 어떤 재료가 얼마나 남는지
- 어떤 메뉴를 추가하면 남는 재료를 줄일 수 있는지

---

## 5. 데이터 소스 전략

### 5.1 레시피 데이터

사용 데이터:

- 식품안전나라 OpenAPI
- 서비스명: `COOKRCP01`
- 요청 형식:

```text
http://openapi.foodsafetykorea.go.kr/api/{API_KEY}/COOKRCP01/json/{startIdx}/{endIdx}
```

확인된 응답 구조:

```json
{
  "COOKRCP01": {
    "total_count": "1146",
    "row": [
      {
        "RCP_SEQ": "28",
        "RCP_NM": "새우 두부 계란찜",
        "RCP_PARTS_DTLS": "연두부 75g(3/4모), ...",
        "RCP_WAY2": "찌기",
        "RCP_PAT2": "반찬",
        "INFO_ENG": "220",
        "INFO_CAR": "3",
        "INFO_PRO": "14",
        "INFO_FAT": "17",
        "INFO_NA": "99",
        "ATT_FILE_NO_MAIN": "...",
        "MANUAL01": "...",
        "MANUAL_IMG01": "..."
      }
    ]
  }
}
```

현재 개발 중에는 API 일일 제한을 고려해 100개만 테스트로 다운로드한다.

확인된 안정 페이징:

```text
1~20
21~40
41~60
61~80
81~100
```

각 요청에서 20개씩 정상 반환됨.

### 5.2 상품 데이터

초기 MVP에서는 컬리 데이터를 1회 수집해 자체 데이터셋으로 사용한다.

중요 원칙:

- MCP 서버는 실시간으로 컬리 API를 호출하지 않는다.
- 컬리 API는 공모전용 데이터셋 구축을 위한 1회성 ETL에만 사용한다.
- 심사·실행 시점에는 자체 DB 또는 JSON 데이터만 조회한다.

수집 방식:

1. 식품안전나라 레시피에서 Ingredient Master 생성
2. Ingredient Master의 재료명으로 컬리 검색 API 호출
3. 검색 결과의 상품 ID 수집
4. 상세 API 호출
5. 상품명, 가격, 판매 단위, 중량/개수, 원산지, 이미지, 상세 URL 저장

확인된 컬리 검색 API:

```text
https://api.kurly.com/search/v4/sites/market/normal-search?keyword=양파&sortType=4&page=1
```

확인된 컬리 상세 API:

```text
https://api.kurly.com/showroom/v2/products/{product_id}?join_order_code=
```

상세 API에서 확인된 핵심 필드:

```json
{
  "no": 5054657,
  "name": "[KF365] 백다다기오이 3입",
  "retail_price": 3490,
  "discounted_price": 2490,
  "discount_rate": 28,
  "sales_unit": "1봉",
  "volume": "3개입 (개당 830원)",
  "product_origin": "국산",
  "unit_price_text": "1개 당 830원",
  "main_image_url": "...",
  "is_sold_out": false
}
```

이 데이터는 우리 서비스의 핵심인 “실제 판매 단위 기반 최적화”에 매우 중요하다.

---

## 6. 데이터 모델 설계

### 6.1 Recipe

레시피의 기본 정보.

```python
class Recipe(BaseModel):
    recipe_id: int
    name: str
    category: str
    cook_method: str
    calories: float | None = None
    carbohydrate: float | None = None
    protein: float | None = None
    fat: float | None = None
    sodium: float | None = None
    image_url: str | None = None
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]
```

DB 테이블로는 `recipes`에 해당한다.

주요 컬럼:

- recipe_id
- name
- category
- cook_method
- calories
- carbohydrate
- protein
- fat
- sodium
- image_url
- tip

### 6.2 Ingredient

표준 재료 마스터.

```python
class IngredientMaster(BaseModel):
    ingredient_id: int | None = None
    name: str
    category: str | None = None
```

DB 테이블:

```text
ingredients
```

예시:

| ingredient_id | name |
|---|---|
| 1 | 양파 |
| 2 | 대파 |
| 3 | 계란 |
| 4 | 두부 |

### 6.3 RecipeIngredient

레시피와 재료의 관계.

중요: 무게와 개수를 모두 저장한다.

```python
class RecipeIngredient(BaseModel):
    recipe_id: int
    name: str
    amount: float | None = None
    unit: str | None = None
    count: float | None = None
    count_unit: str | None = None
    section: str = "재료"
    raw: str
```

예시:

원문:

```text
연두부 75g(3/4모)
```

파싱 결과:

```json
{
  "name": "연두부",
  "amount": 75,
  "unit": "g",
  "count": 0.75,
  "count_unit": "모",
  "section": "재료",
  "raw": "연두부 75g(3/4모)"
}
```

원문:

```text
달걀 30g(1/2개)
```

파싱 결과:

```json
{
  "name": "계란",
  "amount": 30,
  "unit": "g",
  "count": 0.5,
  "count_unit": "개",
  "section": "재료",
  "raw": "달걀 30g(1/2개)"
}
```

무게와 개수를 함께 저장하는 이유:

- 레시피는 `100g(1/2개)`처럼 두 정보를 같이 제공하는 경우가 많다.
- 온라인 쇼핑몰은 `3입`, `1봉`, `1kg`처럼 판매 단위가 다양하다.
- 오이, 계란, 양파, 대파처럼 사용자는 실제로 개수 기준으로 구매하는 경우가 많다.
- 따라서 g만 저장하면 판매 단위 기반 잔여 재료 계산이 어렵다.

### 6.4 RecipeStep

조리 과정.

```python
class RecipeStep(BaseModel):
    recipe_id: int
    step_no: int
    description: str
    image_url: str | None = None
```

DB 테이블:

```text
recipe_steps
```

### 6.5 Product

쇼핑몰 상품.

```python
class Product(BaseModel):
    source: str
    source_product_id: int
    ingredient: str
    product_name: str
    package_amount: float | None = None
    package_unit: str | None = None
    package_count: float | None = None
    package_count_unit: str | None = None
    sales_unit: str | None = None
    volume: str | None = None
    price: int
    original_price: int | None = None
    discount_rate: int | None = None
    unit_price_text: str | None = None
    origin: str | None = None
    detail_url: str
    image_url: str | None = None
    is_sold_out: bool = False
```

예시:

컬리 상품:

```text
[KF365] 백다다기오이 3입
```

파싱 결과:

```json
{
  "source": "kurly",
  "source_product_id": 5054657,
  "ingredient": "오이",
  "product_name": "[KF365] 백다다기오이 3입",
  "package_count": 3,
  "package_count_unit": "개",
  "price": 2490,
  "original_price": 3490,
  "discount_rate": 28,
  "sales_unit": "1봉",
  "volume": "3개입 (개당 830원)",
  "origin": "국산",
  "detail_url": "https://www.kurly.com/goods/5054657"
}
```

---

## 7. 파서 설계

### 7.1 파서는 2단계로 분리한다

#### RecipeParser

역할:

- `RCP_PARTS_DTLS` 전체 문자열을 받는다.
- 줄바꿈을 처리한다.
- `고명`, `양념장`, `소스`, `드레싱`, `곁들임` 같은 section을 추적한다.
- 쉼표 기준으로 재료 단위 문자열을 나눈다.
- 각 재료 문자열을 IngredientParser에 넘긴다.

#### IngredientParser

역할:

- 재료 하나를 파싱한다.
- 무게, 부피, 개수, 분수를 추출한다.
- alias를 적용해 표준명을 만든다.

예시:

```text
연두부 75g(3/4모)
```

결과:

```json
{
  "name": "연두부",
  "amount": 75,
  "unit": "g",
  "count": 0.75,
  "count_unit": "모",
  "raw": "연두부 75g(3/4모)"
}
```

### 7.2 section 저장 정책

`고명`, `양념`, `양념장`, `소스`, `드레싱`, `곁들임`은 버리지 않는다.

이유:

- 양념도 실제로 구매가 필요한 경우가 있다.
- 다만 사용자가 “양념은 집에 있어”라고 하면 제외할 수 있어야 한다.
- 따라서 section 컬럼으로 구분한다.

예시:

```json
{
  "name": "시금치",
  "amount": 10,
  "unit": "g",
  "count": 3,
  "count_unit": "줄기",
  "section": "고명",
  "raw": "시금치 10g(3줄기)"
}
```

### 7.3 alias 관리

alias는 코드에 하드코딩하지 않고 JSON으로 관리한다.

파일:

```text
data/aliases/ingredient_aliases.json
```

초기 예시:

```json
{
  "달걀": "계란",
  "쇠고기": "소고기",
  "소고기": "소고기",
  "백다다기오이": "오이",
  "다다기오이": "오이",
}
```

장기적으로는 다음처럼 확장 가능하다.

```json
{
  "달걀": {
    "canonical": "계란",
    "category": "계란"
  },
  "백다다기오이": {
    "canonical": "오이",
    "category": "채소"
  }
}
```

하지만 MVP에서는 단순 key-value 구조를 사용한다.

---

## 8. ETL 파이프라인

### 8.1 전체 흐름

```text
식품안전나라 API
        ↓
Recipe Downloader
        ↓
data/raw/recipes_raw.json
        ↓
Recipe Parser
        ↓
data/processed/recipes.json
        ↓
Ingredient Master 생성
        ↓
data/processed/ingredient_master.json
        ↓
컬리 Search API
        ↓
컬리 Detail API
        ↓
Product Normalizer
        ↓
data/processed/products.json
        ↓
Supabase 업로드 또는 로컬 JSON 사용
        ↓
MCP Tool에서 조회
```

### 8.2 원칙

1. 다운로드와 파싱을 분리한다.
2. API 호출 결과는 반드시 raw로 저장한다.
3. parser를 수정할 때마다 API를 다시 호출하지 않는다.
4. processed 데이터는 모델 구조에 맞춰 저장한다.
5. Supabase는 데이터 구조가 안정된 뒤 마지막에 붙인다.

### 8.3 현재까지 완료된 작업

- Python 3.13.2 환경 사용
- FastMCP 3.4.3 확인
- 프로젝트 레포: `smart-grocery`
- Playwright 설치 및 컬리 JSON API 수집 검증 완료
- 컬리 상품 목록 API 확인
- 컬리 상품 상세 API 확인
- 식품안전나라 API Key 발급 완료
- 레시피 100개 다운로드 성공
- `recipes_raw.json` 생성 성공
- 레시피 원문 분석 스크립트 작성 및 실행
- 분석 결과:
  - 총 레시피: 100
  - 고명: 2
  - 양념: 17
  - 양념장: 7
  - 소스: 23
  - 평균 줄 수: 2.95
  - 최대 줄 수: 7
  - 최소 줄 수: 1

### 8.4 개발 중 제한

API 일일 제한을 고려해 개발 중에는 다음 제한을 둔다.

```text
레시피: 100개
컬리 검색 재료: 20~30개
상품 상세: 100개 내외
```

최종 제출 전 전체 데이터를 한 번만 수집한다.

---

## 9. 추천·최적화 설계

### 9.1 사용자의 식단 조건

최적화는 다음 입력을 고려한다.

- 며칠 식단인지
- 하루 몇 끼를 집에서 먹는지
- 몇 명이 먹는지
- 예산
- 선호 메뉴
- 제외 재료
- 냉장고 보유 재료
- 같은 메뉴 반복 허용 정도
- 남은 음식 재활용 허용 여부

### 9.2 하루 끼니 수의 중요성

사용자가 하루 1끼만 집에서 먹는다면:

```text
화: 카레
수: 제육볶음
목: 된장찌개
```

이렇게 메뉴 하나씩 배치해도 괜찮다.

하지만 하루 3끼를 집에서 먹는다면:

```text
아침: 카레
점심: 카레
저녁: 카레
```

처럼 추천하면 안 된다.

따라서 다음 제약을 둔다.

- 같은 메뉴 연속 반복 제한
- 같은 조리법 연속 제한
- 같은 주재료 연속 제한
- 재가열 가능한 메뉴는 일부 반복 허용
- 찌개, 카레 등은 남은 음식 활용 가능
- 샐러드, 비빔밥 등은 반복 적합도 낮음

### 9.3 최적화 목표

목표 함수는 다음 요소를 종합한다.

```text
최종 점수 =
  비용 절감 점수
+ 남는 재료 감소 점수
+ 메뉴 유사도 점수
+ 사용자 선택 유지 점수
+ 메뉴 다양성 점수
```

초기 가중치 예시:

```text
비용 절감: 40%
남는 재료 감소: 30%
메뉴 유사도: 15%
사용자 선택 유지: 10%
메뉴 다양성: 5%
```

이 가중치는 추후 실험적으로 조정한다.

### 9.4 OR-Tools 사용 위치

OR-Tools는 다음 문제를 푸는 데 사용한다.

1. 필요한 재료량을 충족하는 상품 조합 선택
2. 판매 단위 때문에 남는 양 최소화
3. 예산 초과 방지
4. 메뉴 후보 중 최적 조합 선택

예시:

필요량:

```text
양파 600g
```

상품 후보:

```text
양파 500g 2,490원
양파 1kg 3,980원
양파 2kg 6,990원
```

OR-Tools는 다음을 비교한다.

```text
500g 2개 = 1,000g / 4,980원 / 400g 남음
1kg 1개 = 1,000g / 3,980원 / 400g 남음
2kg 1개 = 2,000g / 6,990원 / 1,400g 남음
```

선택:

```text
양파 1kg 1개
```

---

## 10. 메뉴 교체 정책

### 10.1 최소 변경 원칙

사용자가 고른 식단을 최대한 유지한다.

예시:

```text
사용자 선택:
김치찌개, 카레, 제육볶음
```

추천은 전체를 갈아엎는 것이 아니라, 필요한 경우 하나만 바꾼다.

```text
김치찌개 → 된장찌개
```

### 10.2 유사 메뉴 제약

김치찌개를 빼라고 했을 때 가지볶음이 나오면 안 된다.

교체 후보는 다음을 만족해야 한다.

- 같은 RCP_PAT2 카테고리
- 비슷한 조리 방식
- 공통 식재료 존재
- 추가 구매가 적음
- 남는 재료를 줄임

예시:

```text
김치찌개 후보:
- 된장찌개
- 순두부찌개
- 부대찌개
- 두부찌개
```

### 10.3 메뉴 유사도 점수

메뉴 유사도는 다음으로 계산한다.

- 카테고리 일치 여부
- 조리 방식 일치 여부
- 공통 재료 비율
- 주재료 유사도
- 식사 맥락 유사도

---

## 11. MCP 서버 설계

### 11.1 기술 스택

- Python 3.13.2
- FastMCP 3.4.3
- Pydantic
- requests
- python-dotenv
- Playwright: ETL용
- OR-Tools
- Supabase: 최종 데이터 저장소
- Docker
- PlayMCP in KC

### 11.2 MCP Tool 목록

최종 Tool은 4개로 유지한다.

```text
optimize_meal_plan
replace_menu
analyze_cart
explain_plan
```

Tool을 너무 많이 만들지 않는다.

### 11.3 MCP 서버 역할

MCP 서버는 다음을 하지 않는다.

- 컬리 API 직접 호출
- 레시피 API 직접 호출
- 실시간 크롤링
- 대량 ETL

MCP 서버는 다음만 한다.

- DB 또는 processed JSON 조회
- 사용자 조건 해석
- 최적화 서비스 호출
- 추천 결과 반환

### 11.4 예상 MCP 구조

```text
app/
  mcp/
    server.py
    tools.py
  services/
    recommendation_service.py
    shopping_service.py
    optimizer_service.py
  optimizer/
    planner.py
  models/
    recipe.py
    ingredient.py
    product.py
  database/
    supabase.py
    repository.py
```

---

## 12. 권장 파일 구조

현재는 필요한 디렉토리만 `mkdir`로 순차 생성한다.

최종 예상 구조:

```text
smart-grocery/
│
├── app/
│   ├── config/
│   │   ├── ingredient_alias.py
│   │   └── regex.py
│   │
│   ├── parser/
│   │   ├── ingredient_parser.py
│   │   ├── recipe_parser.py
│   │   └── product_parser.py
│   │
│   ├── models/
│   │   ├── ingredient.py
│   │   ├── recipe.py
│   │   ├── product.py
│   │   └── shopping_plan.py
│   │
│   ├── mcp/
│   │   ├── server.py
│   │   └── tools.py
│   │
│   ├── services/
│   │   ├── recommendation_service.py
│   │   ├── shopping_service.py
│   │   └── optimizer_service.py
│   │
│   ├── optimizer/
│   │   └── planner.py
│   │
│   └── database/
│       ├── supabase.py
│       └── repository.py
│
├── etl/
│   ├── recipe/
│   │   ├── downloader.py
│   │   └── parser.py
│   │
│   └── product/
│       ├── kurly_search.py
│       ├── kurly_detail.py
│       └── normalizer.py
│
├── data/
│   ├── aliases/
│   │   └── ingredient_aliases.json
│   │
│   ├── raw/
│   │   ├── recipes_raw.json
│   │   ├── recipe_ingredients_raw.csv
│   │   ├── kurly_search/
│   │   └── kurly_detail/
│   │
│   └── processed/
│       ├── recipes.json
│       ├── ingredients.json
│       ├── recipe_ingredients.json
│       ├── products.json
│       └── product_mapping.json
│
├── scripts/
│   ├── analyze_recipe.py
│   ├── build_dataset.py
│   └── upload_supabase.py
│
├── tests/
│   ├── test_ingredient_parser.py
│   ├── test_recipe_parser.py
│   ├── test_product_parser.py
│   └── test_optimizer.py
│
├── .env
├── .gitignore
├── requirements.txt
├── Dockerfile
├── README.md
└── main.py
```

---

## 13. Supabase DB 설계 초안

Supabase는 JSON 데이터 모델이 안정된 뒤 붙인다.

### recipes

```text
id
source_recipe_id
name
category
cook_method
calories
carbohydrate
protein
fat
sodium
image_url
tip
created_at
```

### ingredients

```text
id
name
category
created_at
```

### ingredient_aliases

```text
id
ingredient_id
alias
created_at
```

### recipe_ingredients

```text
id
recipe_id
ingredient_id
amount
unit
count
count_unit
section
raw
created_at
```

### recipe_steps

```text
id
recipe_id
step_no
description
image_url
created_at
```

### products

```text
id
source
source_product_id
ingredient_id
product_name
package_amount
package_unit
package_count
package_count_unit
sales_unit
volume
price
original_price
discount_rate
unit_price_text
origin
detail_url
image_url
is_sold_out
collected_at
created_at
```

---

## 14. 현재 바로 다음 개발 단계

### 14.1 alias 구조 만들기

생성할 디렉토리:

```bash
mkdir data\aliases
mkdir app\config
mkdir app\parser
```

생성할 파일:

```text
data/aliases/ingredient_aliases.json
app/config/ingredient_alias.py
app/config/regex.py
app/parser/ingredient_parser.py
```

### 14.2 ingredient_parser 구현

목표:

```text
연두부 75g(3/4모)
```

을 다음으로 변환한다.

```json
{
  "name": "연두부",
  "amount": 75,
  "unit": "g",
  "count": 0.75,
  "count_unit": "모",
  "raw": "연두부 75g(3/4모)"
}
```

### 14.3 RecipeParser 구현

그 다음 `RCP_PARTS_DTLS` 전체를 처리한다.

입력:

```text
새우두부계란찜
연두부 75g(3/4모), 칵테일새우 20g(5마리), 달걀 30g(1/2개)
고명
시금치 10g(3줄기)
```

출력:

```json
[
  {
    "name": "연두부",
    "amount": 75,
    "unit": "g",
    "count": 0.75,
    "count_unit": "모",
    "section": "재료",
    "raw": "연두부 75g(3/4모)"
  },
  {
    "name": "새우",
    "amount": 20,
    "unit": "g",
    "count": 5,
    "count_unit": "마리",
    "section": "재료",
    "raw": "칵테일새우 20g(5마리)"
  },
  {
    "name": "계란",
    "amount": 30,
    "unit": "g",
    "count": 0.5,
    "count_unit": "개",
    "section": "재료",
    "raw": "달걀 30g(1/2개)"
  },
  {
    "name": "시금치",
    "amount": 10,
    "unit": "g",
    "count": 3,
    "count_unit": "줄기",
    "section": "고명",
    "raw": "시금치 10g(3줄기)"
  }
]
```

---

## 15. 개발 원칙

앞으로의 진행 방식:

1. 필요한 디렉토리를 먼저 `mkdir`로 만든다.
2. 쓰지 않을 가능성이 있는 파일은 미리 만들지 않는다.
3. 한 번에 최종 구조를 고려한 코드를 제공한다.
4. “A 코드 → 나중에 B로 개선” 방식은 피한다.
5. 다운로드, 파싱, 정규화, 저장을 분리한다.
6. API 키는 반드시 `.env`에서 읽는다.
7. MCP 서버는 외부 쇼핑몰이나 레시피 API를 직접 호출하지 않는다.
8. 공모전 제출 전에는 데이터셋을 한 번만 완성해 사용한다.

---

## 16. 공모전 제출 관점에서 어필할 포인트

### 16.1 단순 식단 추천이 아니다

기존 식단 추천은 메뉴만 추천한다.

이 서비스는:

- 메뉴
- 레시피 재료
- 실제 상품 가격
- 실제 판매 단위
- 할인 여부
- 남는 재료
- 메뉴 교체 효과

를 함께 계산한다.

### 16.2 AI가 계산을 대충 하는 서비스가 아니다

계산은 데이터와 최적화 엔진이 수행한다.

AI/MCP는:

- 사용자 의도 파악
- Tool 호출
- 결과 설명
- 메뉴 교체 이유 설명

을 담당한다.

### 16.3 사용자의 원래 의도를 보존한다

무조건 싼 메뉴만 추천하지 않는다.

사용자가 김치찌개를 먹고 싶다면 최대한 김치찌개를 유지하고, 바꾸더라도 된장찌개·순두부찌개처럼 유사 메뉴를 제안한다.

### 16.4 판매 단위 기반 최적화

핵심 차별점.

레시피는 100g을 요구하지만 쇼핑몰은 1kg을 판다.

서비스는 이 차이를 계산해:

- 어떤 상품을 사야 하는지
- 얼마나 남는지
- 남는 재료를 줄이려면 어떤 메뉴를 추가하면 좋은지

를 알려준다.

---

## 17. 예시 최종 응답

사용자 질문:

```text
2명이 3일 동안 저녁만 집에서 먹을 건데 김치찌개랑 카레는 먹고 싶어. 5만원 안에서 장보기 추천해줘.
```

응답 예시:

```text
3일 저녁 기준으로 김치찌개와 카레를 포함한 장보기 플랜을 구성했습니다.

추천 식단
1일차 저녁: 김치찌개
2일차 저녁: 카레
3일차 저녁: 계란말이 + 된장국

예상 총 장보기 비용: 42,800원
예산 50,000원 대비 약 7,200원 여유가 있습니다.

추천 상품

1. 양파
- 상품: [컬리] 국내산 양파 3입
- 가격: 3,490원
- 필요량: 약 1.5개
- 예상 잔여: 약 1.5개
- 활용 제안: 3일차 된장국과 계란말이에 일부 사용하도록 구성했습니다.

2. 두부
- 상품: [컬리] 국산콩 두부 300g
- 가격: 1,980원
- 필요량: 1모
- 잔여: 거의 없음

3. 계란
- 상품: [컬리] 무항생제 계란 10구
- 가격: 4,980원
- 필요량: 4개
- 예상 잔여: 6개
- 활용 제안: 아침 식사 또는 계란말이 추가 메뉴로 활용 가능합니다.

절약 포인트
- 김치찌개와 된장국이 대파, 양파, 두부를 함께 사용해 재료 낭비를 줄입니다.
- 카레에 필요한 양파와 감자를 다른 메뉴에도 일부 배치해 대용량 상품의 잔여를 줄였습니다.
- 김치찌개를 유지하면서도 된장국을 추가해 유사한 국물 메뉴 안에서 재료 활용도를 높였습니다.

대체 제안
더 절약하고 싶다면 김치찌개를 된장찌개로 바꾸면 약 3,500원을 줄일 수 있습니다. 두 메뉴 모두 국&찌개 카테고리이고 두부, 대파, 양파를 함께 사용하기 때문에 식단의 성격이 크게 바뀌지 않습니다.
```

---

## 18. 요약

이 프로젝트의 본질은 다음과 같다.

```text
사용자 식단 의도
        ↓
레시피 재료 계산
        ↓
실제 쇼핑몰 판매 단위 매칭
        ↓
남는 재료와 비용 계산
        ↓
유사 메뉴 교체 제안
        ↓
설명 가능한 장보기 플랜 제공
```

따라서 핵심 개발 순서는 다음이다.

```text
1. Recipe Downloader 완료
2. IngredientParser 구현
3. RecipeParser 구현
4. recipes.json / recipe_ingredients.json 생성
5. Ingredient Master 생성
6. 컬리 검색 ETL 구현
7. 컬리 상세 ETL 구현
8. ProductParser 구현
9. 상품-재료 매핑
10. 장보기 최적화 알고리즘
11. MCP Tool 구현
12. Dockerfile 작성
13. PlayMCP in KC 배포
14. PlayMCP 임시등록 후 테스트
15. 심사 요청
```

