-- Reserved for future use. Populated when vector text search or SigLip2 image
-- search is added. Empty for now — schema only.

create extension if not exists vector;

create table if not exists product_embeddings (
  product_id  int primary key,
  embedding   vector(1024),
  name_concat text,
  updated_at  timestamptz default now()
);

create table if not exists product_image_embeddings (
  image_id    int primary key,
  product_id  int not null,
  embedding   vector(768),
  image_url   text not null,
  updated_at  timestamptz default now()
);
create index if not exists product_image_embeddings_product_idx
  on product_image_embeddings(product_id);