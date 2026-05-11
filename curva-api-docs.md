# Curva Egypt API — Complete Documentation

**Base URL:** `https://octane.curvaegypt.com/api`

**Common Headers:**
```
Origin: https://curvaegypt.com
Referer: https://curvaegypt.com/
Accept: application/json
Content-Type: application/json          # required for POST endpoints
Accept-Language: ar                      # or "en" for English
```

> **Critical:** `/products` and `/clubs`, `/brands` are **POST-only** (GET returns 405). All filter params go in the JSON body, not query strings. `/offers`, `/categories`, `/seasons`, `/branches`, `/home`, `/product/{id}` are **GET**.

---

## 1. Categories

### `GET /categories`

Returns all 7 categories with nested subcategories. No pagination.

**Response:**
```json
{
  "status": true,
  "message": null,
  "data": [
    {
      "id": 1,
      "name": "ملابس كرة قدم",
      "image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/assets/uploads/banners/1745503278.fw.webp?v=1",
      "sub_category": [
        {
          "id": 3,
          "name": "قمصان نسخة اللاعبين",
          "category_id": 1
        },
        {
          "id": 77,
          "name": "قمصان بنسخة اللاعبين الاقتصادية",
          "category_id": 1
        }
      ]
    }
  ]
}
```

**Categories:**

| ID | Name (AR) | Name (EN) | Subcategories |
|----|-----------|-----------|---------------|
| 1 | ملابس كرة قدم | Football Wear | 19 |
| 2 | أحذية كرة قدم | Football Cleats | 11 |
| 4 | ملابس | Clothing | 17 |
| 5 | حقائب | Bags | 6 |
| 3 | اكسسوارات | Accessories | 13 |
| 6 | كرات | Balls | 4 |
| 7 | هدايا وباكدجات | Gifts & Bundles | 0 |

**Note:** `/categories/{id}` returns 404 — use `/categories` and filter client-side.

---

## 2. Products (List)

### `POST /products` — **POST only** (GET returns 405)

Paginated product listing with filters. All parameters go in the JSON body.

**Request Body (JSON):**
```json
{
  "limit": 30,
  "page": 1,
  "category_id": 1,
  "subcategory_id": 3,
  "club_id": 26,
  "brand_id": 8,
  "season_id": 40,
  "search": "زمالك",
  "min_price": 100,
  "max_price": 300,
  "sort": "init_price"
}
```

All filter params are optional. Combine freely.

### Filters

| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Items per page (default 30) |
| `page` | int | Page number |
| `category_id` | int | Filter by category (use IDs from `/categories`) |
| `subcategory_id` | int | Filter by subcategory |
| `club_id` | int | Filter by club or nation (use IDs from `/clubs`) |
| `brand_id` | int | Filter by brand (use IDs from `/brands`) |
| `season_id` | int | Filter by season (use IDs from `/seasons`) |
| `search` | string | Search product name (works in both AR and EN depending on `accept-language`) |
| `min_price` | number | Minimum price filter (EGP) |
| `max_price` | number | Maximum price filter (EGP) |
| `sort` | string | SQL column name for sorting (see below) |

### Sort

The `sort` parameter takes **raw SQL column names** from the `products` table. The API appends `DESC` automatically.

| Sort Value | Behavior |
|-----------|----------|
| `id` | Sort by ID descending (newest first — **this is the default when sort is omitted**) |
| `init_price` | Sort by price descending (most expensive first) |
| `views` | Sort by view count descending |
| `orders` | Sort by order count descending (best selling) |
| `created_at` | Sort by creation date descending |
| `name` | Sort by Arabic name |
| `name_en` | Sort by English name |
| `name_ar` | Sort by Arabic name |

> **Warning:** Using invalid column names returns a SQL error (500). No ascending sort is supported — always `DESC`.

**Filter result counts (examples):**

| Filter | Count |
|--------|-------|
| None (all products) | 4,235 |
| `category_id=1` | 4,131 |
| `subcategory_id=3` (Player Edition) | 168 |
| `subcategory_id=34` (Original Quality - Curva) | 56 |
| `club_id=26` (Zamalek) | 131 |
| `brand_id=8` (Nike) | 1,128 |
| `season_id=40` (2026/27) | 146 |
| `category_id=1` + `club_id=26` | 79 |
| `brand_id=8` + `club_id=26` | 45 |
| `brand_id=8` + `season_id=40` + `club_id=26` | 2 |
| `min_price=200` + `max_price=400` | 4,235 (no effect without other filters) |
| `min_price=200` + `max_price=400` + `category_id=1` | 1,377 |
| `search="زمالك"` (or `"zamalek"` in EN) | 378 |

### Response

```json
{
  "status": true,
  "message": null,
  "data": {
    "current_page": 1,
    "data": [
      {
        "id": 10307,
        "name": "قميص الزمالك الثالث 2025/26 بشعارات ثري دي TH-82",
        "init_price": 295,
        "offer_ratio": null,
        "availability": "available",
        "tags": null,
        "image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/...",
        "offer_price": null,
        "in_wishlist": false,
        "in_cart": false
      }
    ],
    "first_page_url": "https://octane.curvaegypt.com/api/products?page=1",
    "from": 1,
    "last_page": 142,
    "last_page_url": "https://octane.curvaegypt.com/api/products?page=142",
    "next_page_url": "https://octane.curvaegypt.com/api/products?page=2",
    "path": "https://octane.curvaegypt.com/api/products",
    "per_page": 30,
    "prev_page_url": null,
    "to": 30,
    "total": 4235,
    "links": [ ... ]
  }
}
```

### Response fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Product ID |
| `name` | string | Product name (AR or EN based on `accept-language`) |
| `init_price` | int | Original price in EGP |
| `offer_ratio` | string\|null | Discount percentage (e.g., `"33.33333333333333"`, `"25"`) or null |
| `offer_price` | int\|null | Discounted price in EGP, or null if no discount |
| `availability` | string | `"available"` or `"unavailable"` |
| `tags` | string\|null | Product tag code (e.g., `"PEA26"`) or null |
| `image` | string | Primary product image URL (WebP) |
| `in_wishlist` | bool | Whether user has wishlisted (requires auth) |
| `in_cart` | bool | Whether user has in cart (requires auth) |

---

## 3. Product Detail

### `GET /product/{id}`

Returns complete product details: sizes, colors, stock, images, related offers, and all relational data.

**Example:** `GET /product/10307`

### Response

```json
{
  "status": true,
  "message": null,
  "data": {
    "product": {
      "id": 10307,
      "name": "قميص الزمالك الثالث 2025/26 بشعارات ثري دي TH-82",
      "init_price": 295,
      "offer_ratio": null,
      "brand_id": 8,
      "club_id": 26,
      "category_id": 1,
      "subcategory_id": 34,
      "season_id": 40,
      "availability": "available",
      "desc": "<p>HTML description...</p>",
      "views": 1,
      "offer_price": null,
      "in_wishlist": false,
      "in_cart": false,

      "season":      { "id": 40, "name": "2026/27" },
      "brand":       { "id": 8, "name": "نايكي" },
      "club":        { "id": 26, "name": "الزمالك", "supplier": "", "brand": null },
      "category":    { "id": 1, "name": "ملابس كرة قدم" },
      "subcategory": { "id": 34, "name": "قمصان أوريجنال كواليتي - نسخة كورڤا" },

      "sizes": [ ... ],
      "images": [ ... ]
    },
    "offers": [ ... ]
  }
}
```

### Product object fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Product ID |
| `name` | string | Product name (AR or EN per `accept-language`) |
| `init_price` | int | Original price (EGP) |
| `offer_ratio` | string\|null | Discount percentage or null |
| `offer_price` | int\|null | Discounted price or null |
| `brand_id` | int | FK to brands |
| `club_id` | int | FK to clubs |
| `category_id` | int | FK to categories |
| `subcategory_id` | int | FK to subcategories |
| `season_id` | int | FK to seasons |
| `availability` | string | `"available"` or `"unavailable"` |
| `desc` | string | Full HTML description (AR or EN) |
| `views` | int | View count |
| `in_wishlist` | bool | Wishlisted (requires auth) |
| `in_cart` | bool | In cart (requires auth) |
| `season` | object | `{ "id": int, "name": "2026/27" }` |
| `brand` | object | `{ "id": int, "name": "..." }` |
| `club` | object | `{ "id": int, "name": "...", "supplier": "...", "brand": null }` |
| `category` | object | `{ "id": int, "name": "..." }` |
| `subcategory` | object | `{ "id": int, "name": "..." }` |
| `sizes` | array | Size/variant array (see below) |
| `images` | array | Product gallery (see below) |

### Sizes structure

Each product has a `sizes` array. Each size entry contains color variants with stock quantities:

```json
{
  "id": 51929,
  "price": "295",
  "sort": 7,
  "size_id": 6,
  "product_id": 10307,
  "final_price": 295,
  "offer_price": null,
  "size": { "id": 6, "name": "M" },
  "colors": [
    {
      "id": 374184,
      "barcode": "10307-6-105",
      "size_id": 6,
      "color_id": 105,
      "product_id": 10307,
      "product_size_id": 51929,
      "quantity": "65",
      "image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/...",
      "color": { "id": 105, "name": "فيروزي", "color": "#07f8aa" },
      "product": { /* full product object repeated */ }
    }
  ],
  "product": { /* full product object repeated */ }
}
```

**Key size/color fields:**

| Field | Description |
|-------|-------------|
| `size.name` | Size label: `"S"`, `"M"`, `"L"`, `"XL"`, `"XXL"`, `"XXXL"`, etc. |
| `price` | Price for this size variant (string) |
| `final_price` | Effective price after discount (int) |
| `offer_price` | Discounted price for this variant, or null |
| `quantity` | Stock count (string) |
| `barcode` | Format: `{product_id}-{size_id}-{color_id}` |
| `color.name` | Color name in AR/EN |
| `color.color` | Hex color code (e.g., `"#07f8aa"`) |
| `color` on `color.color` field | Hex value |

> **Note:** The `product` key inside `sizes[]` and `sizes[].colors[]` contains the **full product object repeated** — this is redundant but allows self-contained variant data. In the nested product, additional fields appear: `name_ar`, `name_en`, `desc_ar`, `desc_en`, `shortfall`, `status`, `buying_price`, `commission`.

### Images structure

```json
{
  "id": 72457,
  "image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/assets/uploads/products/...",
  "sort": 1,
  "barcodes": null,
  "product_id": 10307,
  "created_at": "2026-05-10T12:43:16.000000Z",
  "updated_at": "2026-05-10T12:43:16.000000Z"
}
```

- `sort`: Display order (1 = primary image)
- `barcodes`: Typically `null`, can link image to specific barcode variant

### Offers array

The `offers` array in the product detail response contains **related/similar products** that are currently on sale:

```json
{
  "id": 10306,
  "name": "قميص الزمالك الأساسي 2025/26...",
  "init_price": 295,
  "offer_ratio": null,
  "image": "https://...",
  "offer_price": null,
  "in_wishlist": false,
  "in_cart": false
}
```

---

## 4. Club Detail

### `GET /clubs/{id}`

Returns detailed info about a specific club or national team.

**Example:** `GET /clubs/26`

**Response:**
```json
{
  "status": true,
  "message": null,
  "data": {
    "id": 26,
    "name": "الزمالك",
    "desc": "<p>HTML description of the club...</p>",
    "full_name": "نادي الزمالك الرياضي",
    "founders_name": "جورج مرزباخ",
    "nickname": "النادي الملكي",
    "brand_id": 72,
    "image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/assets/uploads/banners/42876626.webp?v=1",
    "founding_date": "1911-01-05",
    "kit_supplier_year": 2024,
    "kit_color": "أبيض/أحمر",
    "league_id": 3,
    "stadium_id": 1,
    "type": "club",
    "kit_color_id": 35,
    "supplier": "زات أوتفيت",
    "league": {
      "id": 3,
      "name": "الدوري المصري الممتاز"
    },
    "stadium": {
      "id": 1,
      "name": "ستاد القاهرة الدولي"
    },
    "brand": {
      "id": 72,
      "name_ar": "زات أوتفيت",
      "name_en": "ZAT Outfit",
      "image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/...",
      "desc_ar": "HTML Arabic description...",
      "desc_en": "HTML English description...",
      "views": 1636,
      "orders": 78,
      "status": "active",
      "created_at": "2024-05-08T15:35:22.000000Z",
      "updated_at": "2026-05-10T02:21:51.000000Z"
    }
  }
}
```

### Club detail fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Club/nation ID |
| `name` | string | Short name (AR or EN per `accept-language`) |
| `desc` | string | Full HTML description |
| `full_name` | string | Full official name |
| `founders_name` | string | Founder name |
| `nickname` | string | Club nickname |
| `brand_id` | int | Kit supplier brand ID |
| `image` | string | Club logo/image URL |
| `founding_date` | string | ISO date (e.g., `"1911-01-05"`) |
| `kit_supplier_year` | int | Year of current kit supplier deal |
| `kit_color` | string | Primary kit colors (AR) |
| `kit_color_id` | int | FK to color palette |
| `type` | string | `"club"` or `"nation"` |
| `supplier` | string | Kit supplier name |
| `league` | object | `{ "id": int, "name": "..." }` |
| `stadium` | object | `{ "id": int, "name": "..." }` |
| `brand` | object | Full brand object with `name_ar`, `name_en`, `desc_ar`, `desc_en` |

**English response** (`accept-language: en`):
- `name` → `"Zamalek"`
- `full_name` → `"Zamalek Sports Club"`
- `founders_name` → `"George Marzback"`
- `nickname` → `"The Royal Club"`
- `kit_color` → `"White/Red"`
- `league.name` → `"Egyptian Premier League"`
- `stadium.name` → `"Cairo International Stadium"`

---

## 5. Clubs (List)

### `POST /clubs` — **POST only** (GET returns 405)

Returns paginated list of all clubs/national teams.

**Request Body:**
```json
{ "limit": 200, "page": 1 }
```

**Response:**
```json
{
  "status": true,
  "data": {
    "current_page": 1,
    "data": [
      {
        "id": 26,
        "name": "الزمالك",
        "image": "https://...",
        "orders": 2274,
        "type": "club",
        "supplier": "",
        "brand": null
      }
    ],
    "total": 117
  }
}
```

### Club list fields

| Field | Description |
|-------|-------------|
| `id` | Unique ID |
| `name` | Club/nation name (AR or EN) |
| `image` | Club logo URL |
| `orders` | Total order count (popularity ranking) |
| `type` | `"club"` or `"nation"` |
| `supplier` | Kit supplier name (may be empty) |
| `brand` | Brand object or null |

**Total: 117 entries** — downloadable in a single request with `limit: 200`.

**Top entries by orders:**

| ID | Name | Type | Orders |
|----|------|------|--------|
| 26 | الزمالك (Zamalek) | club | 2,274 |
| 40 | برشلونة (Barcelona) | club | 2,039 |
| 25 | الأهلي (Al Ahly) | club | 1,496 |
| 73 | مصر (Egypt) | nation | 974 |
| 29 | ريال مدريد (Real Madrid) | club | 942 |
| 33 | أرسنال (Arsenal) | club | 670 |
| 83 | البرازيل (Brazil) | nation | 614 |
| 45 | الأرجنتين (Argentina) | nation | 450 |
| 76 | البرتغال (Portugal) | nation | 444 |
| 49 | مانشستر يونايتد (Man United) | club | 334 |

---

## 6. Brand Detail

### `GET /brands/{id}`

Returns detailed info about a brand.

**Example:** `GET /brands/8`

**Response:**
```json
{
  "status": true,
  "message": null,
  "data": {
    "id": 8,
    "name": "نايكي",
    "desc": "<p>HTML description...</p>",
    "image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/assets/uploads/banners/8635328.webp?v=1"
  }
}
```

### Brand detail fields

| Field | Description |
|-------|-------------|
| `id` | Brand ID |
| `name` | Brand name (AR or EN per `accept-language`) |
| `desc` | Full HTML description of the brand |
| `image` | Brand logo URL |

> **Note:** Brand detail doesn't include `name_ar`/`name_en` or `views`/`orders` like club detail does. The list endpoint has `orders`, but the detail endpoint has `desc`.

---

## 7. Brands (List)

### `POST /brands` — **POST only**

**Request Body:**
```json
{ "limit": 200, "page": 1 }
```

**Response:**
```json
{
  "status": true,
  "data": {
    "current_page": 1,
    "data": [
      { "id": 14, "name": "أديداس", "image": "https://...", "orders": 6483 }
    ],
    "total": 76
  }
}
```

**Total: 76 brands** — downloadable in a single request.

**Top brands by orders:**

| ID | Name (AR) | Name (EN) | Orders |
|----|-----------|-----------|--------|
| 14 | أديداس | Adidas | 6,483 |
| 8 | نايكي | Nike | 6,446 |
| 9 | كورڤا | Curva | 3,483 |
| 12 | بوما | Puma | 2,404 |
| 21 | أير جوردان | Air Jordan | 210 |

---

## 8. Seasons

### `GET /seasons`

Returns all available seasons. No pagination.

**Response:**
```json
{
  "status": true,
  "data": [
    { "id": 1, "name": "2019/20" },
    { "id": 2, "name": "2020/21" },
    { "id": 40, "name": "2026/27" },
    ...
  ]
}
```

Total: ~40 seasons ranging from `1997/98` to `2026/27`.

---

## 9. Branches

### `GET /branches`

Returns all physical store branches. No pagination.

**Response:**
```json
{
  "status": true,
  "data": [
    {
      "id": 3,
      "name": "مدينة نصر",
      "phones": ["01097613728", "0224104605"],
      "sort": 1,
      "phone": "01097613728"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `id` | Branch ID |
| `name` | Branch/area name (AR) |
| `phones` | Array of phone numbers |
| `phone` | Primary phone number |
| `sort` | Display order |

---

## 10. Offers

### `GET /offers`

Paginated list of products currently on discount (`offer_price` is not null). Uses standard Laravel pagination via query parameters.

**Query Parameters:** `?limit=30&page=1`

**Response:** Same paginated structure as `/products`. Total: **1,331** offer products.

Each item:
```json
{
  "id": 10296,
  "name": "تيشرت بولو الزمالك 2025/26 AT-166",
  "init_price": 450,
  "offer_ratio": "33.33333333333333",
  "availability": "available",
  "image": "https://...",
  "offer_price": 300,
  "in_wishlist": false,
  "in_cart": false
}
```

> **Note:** Unlike `/products`, the `/offers` endpoint uses **GET** with query parameters (not POST with JSON body).

---

## 11. Home

### `GET /home`

Returns homepage aggregation data — curated collections for the storefront.

**Response:**
```json
{
  "status": true,
  "data": {
    "categories": [
      { "id": 1, "name": "ملابس كرة قدم", "image": "https://..." }
    ],
    "latest": [
      { "id": 10307, "name": "...", "init_price": 295, "offer_ratio": null, "availability": "available", "image": "https://...", "offer_price": null, "in_wishlist": false, "in_cart": false }
    ],
    "best_seller": [ /* same structure, 10 items */ ],
    "offers": [ /* same structure, 10 items */ ],
    "brands": [
      { "id": 14, "name": "أديداس", "image": "https://..." }
    ],
    "clubs": [
      { "id": 26, "name": "الزمالك", "image": "https://...", "supplier": "", "brand": null }
    ],
    "banners": [
      {
        "id": 1,
        "title": "...",
        "read_more": "...",
        "buy_now": "...",
        "more_link": "...",
        "buy_now_link": "...",
        "image": "https://..."
      }
    ]
  }
}
```

| Section | Count | Structure |
|---------|-------|-----------|
| `categories` | 7 | `{ id, name, image }` |
| `latest` | 10 | Product summary |
| `best_seller` | 10 | Product summary |
| `offers` | 10 | Product summary (with discounts) |
| `brands` | 10 | `{ id, name, image }` |
| `clubs` | 10 | `{ id, name, image, supplier, brand }` |
| `banners` | 4 | Banner with links |

---

## 12. Language Support

The `Accept-Language` header controls localization across all endpoints:

| `accept-language` | Effect |
|-------------------|--------|
| `ar` | Arabic names, descriptions, club details |
| `en` | English names, descriptions, club details |

### What changes by language:

| Field | `ar` | `en` |
|-------|------|------|
| Product `name` | `قميص الزمالك الثالث 2025/26 بشعارات ثري دي TH-82` | `Zamalek 2025/26 Third Jersey with 3D logos TH-82` |
| Product `desc` | Arabic HTML | English HTML |
| Category `name` | `ملابس كرة قدم` | `Football Wear` |
| Subcategory `name` | `قمصان أوريجنال كواليتي - نسخة كورڤا` | `Original Quality Jerseys - Curva Edition` |
| Club `name` | `الزمالك` | `Zamalek` |
| Club `full_name` | `نادي الزمالك الرياضي` | `Zamalek Sports Club` |
| Club `nickname` | `النادي الملكي` | `The Royal Club` |
| Club `founders_name` | `جورج مرزباخ` | `George Marzback` |
| Club `kit_color` | `أبيض/أحمر` | `White/Red` |
| Brand `name` | `نايكي` | `Nike` |
| Brand `desc` | Arabic HTML | English HTML |
| Season `name` | Always same: `"2026/27"` etc. | Same |
| Color `name` | `فيروزي` | `Turbquoise` |
| Branch `name` | `مدينة نصر` | Stays Arabic (untranslated) |

### Fields that are always bilingual (in product detail):

The nested `product` object inside `sizes[].colors[].product` contains both:
- `name_ar` and `name_en`
- `desc_ar` and `desc_en`

These are available regardless of the `accept-language` header.

---

## 13. Image CDN

All images are hosted on DigitalOcean Spaces CDN:

```
https://curva-app.nyc3.cdn.digitaloceanspaces.com/assets/uploads/{type}/{filename}
```

| Type path | Used for |
|-----------|----------|
| `products/` | Product images |
| `banners/` | Category banners, club logos, brand logos |

All images use **WebP** format with a `?v=1` cache-busting query parameter.

---

## 14. Authentication Endpoints

These endpoints exist but require authentication:

| Method | Endpoint | Response (unauthenticated) |
|--------|----------|-----------------------------|
| POST | `/login` | 405 (needs credentials) |
| POST | `/register` | 405 (needs credentials) |
| GET | `/profile` | 401 Unauthorized |
| GET | `/wishlist` | 401 Unauthorized |
| GET | `/orders` | 401 Unauthorized |

---

## 15. Endpoints That Don't Exist

All return `{"status": false, "message": "Not Fount", "data": null}`:

| Endpoint | Note |
|----------|------|
| `GET /categories/{id}` | Use `/categories` and filter client-side |
| `GET /sizes` | Size info is in product detail only |
| `GET /colors` | Color info is in product detail only |
| `GET /leagues` | League info is nested in club detail |
| `GET /stadiums` | Stadium info is nested in club detail |
| `GET /banners` | Use `/home` instead |
| `GET /slider` | Doesn't exist |
| `GET /settings` | Doesn't exist |
| `GET /pages` | Doesn't exist |
| `GET /ads` | Doesn't exist |
| Any POST to `/products/search`, `/products/filter`, `/products/latest` etc. | Only `/products` with JSON body filters exists |

---

## 16. Error Handling

### 404-style response
```json
{ "status": false, "message": "Not Fount", "data": null }
```

### 405 Method Not Allowed
Using GET on POST-only endpoints returns 405 with HTML error page.

### 500 Server Error (invalid sort)
Using an invalid SQL column name in `sort` returns a raw SQL error:
```json
{
  "message": "SQLSTATE[42S22]: Column not found: 1054 Unknown column 'newest' in 'order clause'",
  "exception": "Illuminate\\Database\\QueryException"
}
```

### 401 Unauthorized
Accessing authenticated endpoints without a token:
```json
{ "message": "Unauthenticated." }
```

---

## 17. Common Patterns

### Pagination

All paginated endpoints use Laravel's standard pagination:

```
current_page, first_page_url, from, last_page, last_page_url,
next_page_url, path, per_page, prev_page_url, to, total, links[]
```

**Paginated endpoints:**
- `POST /products` — body: `{"limit": 30, "page": 1, ...}`
- `POST /clubs` — body: `{"limit": 200, "page": 1}`
- `POST /brands` — body: `{"limit": 200, "page": 1}`
- `GET /offers` — query: `?limit=30&page=1`

**Non-paginated endpoints:**
- `GET /categories` — returns all 7 categories
- `GET /seasons` — returns all ~40 seasons
- `GET /branches` — returns all branches
- `GET /home` — returns fixed curated sets
- `GET /product/{id}` — single item
- `GET /clubs/{id}` — single item
- `GET /brands/{id}` — single item

### Price & Offers

| Field | Level | Description |
|-------|-------|-------------|
| `init_price` | Product | Original price (EGP) |
| `offer_price` | Product | Discounted price or `null` |
| `offer_ratio` | Product/list | Discount percentage string (e.g., `"25"`, `"33.33333333333333"`) or `null` |
| `price` | Size variant | Variant price (string) |
| `final_price` | Size variant | Effective price after discount (int) |
| `offer_price` | Size variant | Discounted price for this variant or `null` |

**Calculation:** `offer_price = init_price × (1 - offer_ratio/100)`, rounded to nearest integer.

### Barcode Format

`{product_id}-{size_id}-{color_id}`

Example: `10307-6-105` = Product 10307, Size M (id=6), Turquoise (id=105).

### Product Availability

`availability` field: `"available"` or `"unavailable"`. The list endpoint only returns `available` products.

### Product Status

In nested product objects (inside `sizes[].colors[].product`), a `status` field appears with value `"active"`.

### Shortfall

In nested product objects, a `shortfall` field appears with value `"yes"` or `"no"`. This likely indicates whether the product has inventory shortfall.

---

## Quick Reference: All Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/categories` | No | All categories with subcategories |
| POST | `/products` | No | Paginated products (filters in body) |
| GET | `/product/{id}` | No | Single product detail |
| POST | `/clubs` | No | Paginated clubs/nations list |
| GET | `/clubs/{id}` | No | Single club/nation detail |
| POST | `/brands` | No | Paginated brands list |
| GET | `/brands/{id}` | No | Single brand detail |
| GET | `/seasons` | No | All seasons |
| GET | `/branches` | No | All store branches |
| GET | `/offers` | No | Paginated discounted products |
| GET | `/home` | No | Homepage aggregation |
| POST | `/login` | Required | User login (405 without credentials) |
| POST | `/register` | Required | User registration (405 without credentials) |
| GET | `/profile` | Required | User profile (401 without auth) |
| GET | `/wishlist` | Required | User wishlist (401 without auth) |
| GET | `/orders` | Required | User orders (401 without auth) |

---

## Full API Scrape Strategy for AI Agent

To build a complete local product database:

### Phase 1: Reference Data (6 requests)
```bash
GET  /categories                    # 7 categories, ~70 subcategories
GET  /seasons                       # ~40 seasons
GET  /branches                      # ~8 branches
POST /clubs   {"limit":200,"page":1}  # 117 clubs/nations (1 page)
POST /brands  {"limit":200,"page":1}  # 76 brands (1 page)
GET  /home                          # Homepage aggregation
```

### Phase 2: All Products (142 requests)
```bash
# Total: 4,235 products. At limit=30 → 142 pages
for page in $(seq 1 142); do
  POST /products {"limit":30,"page":$page}
done
```

### Phase 3: Club & Brand Details (193 requests, optional)
```bash
# Only if you need desc, founding_date, league, stadium, etc.
for id in $ALL_CLUB_IDS; do
  GET /clubs/$id
done
for id in $ALL_BRAND_IDS; do
  GET /brands/$id
done
```

### Phase 4: Product Details (4,235 requests, optional)
```bash
# Only if you need sizes, colors, stock, images, descriptions, full variant data
# The list endpoint already has: id, name, price, offer info, availability, image
for id in $ALL_PRODUCT_IDS; do
  GET /product/$id
done
```

### Phase 5: Offers (45 requests)
```bash
# Total: 1,331 offer products. At limit=30 → 45 pages
for page in $(seq 1 45); do
  GET /offers?limit=30&page=$page
done
```

### Optimized Strategy (Minimum Requests)

If you only need product listing data (no sizes/colors/stock):
- **149 requests total** = 6 (reference) + 142 (products) + 1 (offers page 1 for total count)

If you need full variant details with sizes, colors, and stock:
- **4,384 requests total** = 6 (reference) + 142 (products) + 4,235 (product details) + 1 (offers)

### Rate Limiting

No rate limiting was observed during testing, but consider adding respectful delays (200-500ms) between requests for production scraping.