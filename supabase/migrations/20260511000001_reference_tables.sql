-- Reference data mirrored from curvaegypt.com weekly via Edge Function.

create table if not exists categories (
  id          int primary key,
  name_ar     text not null,
  name_en     text not null,
  image       text,
  updated_at  timestamptz not null default now()
);

create table if not exists subcategories (
  id          int primary key,
  category_id int not null references categories(id) on delete cascade,
  name_ar     text not null,
  name_en     text not null,
  updated_at  timestamptz not null default now()
);
create index if not exists subcategories_category_id_idx on subcategories(category_id);

create table if not exists clubs (
  id            int primary key,
  name_ar       text not null,
  name_en       text,
  type          text,
  supplier      text,
  image         text,
  orders_count  int not null default 0,
  updated_at    timestamptz not null default now()
);

create table if not exists brands (
  id            int primary key,
  name_ar       text not null,
  name_en       text,
  image         text,
  orders_count  int not null default 0,
  updated_at    timestamptz not null default now()
);

create table if not exists seasons (
  id          int primary key,
  name        text not null,
  updated_at  timestamptz not null default now()
);

create table if not exists branches (
  id          int primary key,
  name        text not null,
  phones      text[] not null default '{}',
  sort        int,
  updated_at  timestamptz not null default now()
);