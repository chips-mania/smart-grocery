

------------------------------------------------------------
-- recipes
------------------------------------------------------------

create table recipes (

    recipe_id bigint primary key,

    name text not null,

    category text,

    cook_method text,

    kcal real,

    carb real,

    protein real,

    fat real,

    sodium real,

    thumbnail text,

    image text,

    tip text,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now()

);

------------------------------------------------------------
-- recipe_ingredients
------------------------------------------------------------

create table recipe_ingredients (

    id bigint generated always as identity primary key,

    recipe_id bigint not null
        references recipes(recipe_id)
        on delete cascade,

    ingredient text not null,

    amount real,

    unit varchar(20),

    count varchar(30),

    raw text

);

------------------------------------------------------------
-- kurly_products
------------------------------------------------------------

create table kurly_products (

    product_id bigint primary key,

    name text not null,

    brand text,

    price integer,

    unit text,

    image text,

    url text,

    category text,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now()

);

------------------------------------------------------------
-- ingredient_product_map
------------------------------------------------------------

create table ingredient_product_map (

    id bigint generated always as identity primary key,

    ingredient text not null,

    product_id bigint not null
        references kurly_products(product_id)
        on delete cascade,

    confidence real not null default 1.0,

    created_at timestamptz not null default now(),

    unique (ingredient, product_id)

);

------------------------------------------------------------
-- Index
------------------------------------------------------------

create index idx_recipe_name
on recipes(name);

create index idx_recipe_category
on recipes(category);

create index idx_recipe_ingredient
on recipe_ingredients(recipe_id);

create index idx_ingredient_name
on recipe_ingredients(ingredient);

create index idx_kurly_name
on kurly_products(name);

create index idx_kurly_category
on kurly_products(category);

create index idx_map_ingredient
on ingredient_product_map(ingredient);

create index idx_map_product
on ingredient_product_map(product_id);

create index idx_recipe_id
on recipe_ingredients(recipe_id);