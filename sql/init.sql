DROP TABLE IF EXISTS ingredient_product_map;
DROP TABLE IF EXISTS kurly_products;
DROP TABLE IF EXISTS recipe_ingredients;
DROP TABLE IF EXISTS recipes;

CREATE TABLE recipes(

    recipe_id INTEGER PRIMARY KEY,

    name TEXT NOT NULL,

    category TEXT,

    cook_method TEXT,

    kcal REAL,

    carb REAL,

    protein REAL,

    fat REAL,

    sodium REAL,

    thumbnail TEXT,

    image TEXT,

    tip TEXT

);

CREATE TABLE recipe_ingredients(

    id SERIAL PRIMARY KEY,

    recipe_id INTEGER NOT NULL,

    ingredient TEXT NOT NULL,

    amount REAL,

    unit VARCHAR(20),

    count VARCHAR(30),

    raw TEXT

);

CREATE TABLE kurly_products(

    product_id BIGINT PRIMARY KEY,

    name TEXT NOT NULL,

    brand TEXT,

    price INTEGER,

    unit TEXT,

    image TEXT,

    url TEXT,

    category TEXT

);

CREATE TABLE ingredient_product_map(

    id SERIAL PRIMARY KEY,

    ingredient TEXT NOT NULL,

    product_id BIGINT NOT NULL,

    confidence REAL

);

CREATE INDEX idx_recipe_name
ON recipes(name);

CREATE INDEX idx_recipe_category
ON recipes(category);

CREATE INDEX idx_recipe_ingredient
ON recipe_ingredients(ingredient);

CREATE INDEX idx_kurly_name
ON kurly_products(name);

CREATE INDEX idx_map_ingredient
ON ingredient_product_map(ingredient);