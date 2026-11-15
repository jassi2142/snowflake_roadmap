# FLATTEN & LATERAL

FLATTEN is a table function that explodes an array or object into one row per element, and LATERAL lets that function reference columns from tables earlier in the FROM clause. Together they are the standard way to turn nested JSON into relational rows you can filter, join, and aggregate.

## How it works

FLATTEN takes a VARIANT, OBJECT, or ARRAY input:

```sql
FLATTEN( INPUT => <expr>
         [, PATH => '<path>']
         [, OUTER => TRUE | FALSE]
         [, RECURSIVE => TRUE | FALSE]
         [, MODE => 'OBJECT' | 'ARRAY' | 'BOTH'] )
```

- `PATH`: the element inside the input to flatten. Default is an empty path (the input itself).
- `OUTER`: if `FALSE` (default), rows whose input is empty or missing are dropped. If `TRUE`, one row is produced with NULL in KEY, INDEX, and VALUE, similar to a left outer join.
- `RECURSIVE`: if `TRUE`, all nested sub-elements are expanded. Default `FALSE`.
- `MODE`: flatten objects, arrays, or both (default `BOTH`).

Each output row has fixed columns:

| Column | Meaning |
| --- | --- |
| SEQ | Sequence number per input record (not guaranteed gap-free or ordered) |
| KEY | Key for object elements; NULL for arrays |
| PATH | Path to the element |
| INDEX | Array index; NULL for objects |
| VALUE | The element value |
| THIS | The element being flattened |

The source row's columns remain available and are repeated for each produced row.

**LATERAL** is what makes the correlation work. In `FROM t, LATERAL FLATTEN(INPUT => t.v:items) f`, FLATTEN runs once per row of `t`. For a single level, `TABLE(FLATTEN(...))` and `LATERAL FLATTEN(...)` produce the same result, but when a second FLATTEN must reference the output of the first (nested arrays), use LATERAL so each call can see the previous one.

Because each array element becomes a row, flattening multiplies row counts. Flattening two independent arrays from the same row produces their Cartesian product.

## Example

Sample data:

```sql
CREATE OR REPLACE TABLE orders_raw (v VARIANT);
INSERT INTO orders_raw SELECT PARSE_JSON('{
  "order_id": 1,
  "lines": [
    {"sku": "A1", "qty": 2, "tags": ["promo", "new"]},
    {"sku": "B7", "qty": 1, "tags": []}
  ]}');
```

One row per order line:

```sql
SELECT o.v:order_id::NUMBER AS order_id,
       l.index              AS line_no,
       l.value:sku::STRING  AS sku,
       l.value:qty::NUMBER  AS qty
FROM orders_raw o,
     LATERAL FLATTEN(INPUT => o.v:lines) l;
```

Nested flatten with OUTER so lines without tags are kept:

```sql
SELECT o.v:order_id::NUMBER AS order_id,
       l.value:sku::STRING  AS sku,
       t.value::STRING      AS tag
FROM orders_raw o,
     LATERAL FLATTEN(INPUT => o.v:lines) l,
     LATERAL FLATTEN(INPUT => l.value:tags, OUTER => TRUE) t;
```

Discover every key path in a document:

```sql
SELECT DISTINCT f.path, TYPEOF(f.value) AS type
FROM orders_raw o,
     LATERAL FLATTEN(INPUT => o.v, RECURSIVE => TRUE) f;
```

## Best practices

- Cast `VALUE` sub-fields to proper types in the SELECT list.
- Use `OUTER => TRUE` when parent rows must survive empty or missing arrays.
- Filter parent rows before flattening to reduce work.
- Flatten independent arrays in separate queries or CTEs and join on a key, rather than in one FROM clause, to avoid accidental cross products.
- For frequently queried arrays, materialize the flattened result in a table or dynamic table.

## Common pitfalls

- Losing rows silently because `OUTER` defaults to `FALSE`.
- Row explosion from flattening two sibling arrays together.
- Using `SEQ` as a stable ordering key; it is not guaranteed to be ordered or gap-free. Use `INDEX` for array position.
- Forgetting that `RECURSIVE => TRUE` returns intermediate container rows as well as leaf values.

## Learn more

- [FLATTEN](https://docs.snowflake.com/en/sql-reference/functions/flatten)
- [LATERAL](https://docs.snowflake.com/en/sql-reference/constructs/join-lateral)

## Knowledge check

### An order has an empty `lines` array, and it disappears from your flattened results. What fixes this?
- [ ] Use RECURSIVE => TRUE
- [x] Use OUTER => TRUE
- [ ] Use MODE => 'OBJECT'
- [ ] Replace LATERAL with TABLE
> With OUTER => FALSE (the default), inputs that expand to zero rows are dropped; OUTER => TRUE keeps one row with NULL values.

### Each record has an `items` array of 3 elements and a `discounts` array of 4 elements. You flatten both in the same FROM clause. How many rows per record result?
- [ ] 3
- [ ] 7
- [x] 12
- [ ] 4
> Flattening two independent arrays produces every combination, here 3 x 4 = 12 rows.

### Why is LATERAL needed when you flatten `f.value:business` after flattening `contact`?
- [ ] LATERAL improves pruning
- [x] The second FLATTEN must reference output columns of the first FLATTEN
- [ ] TABLE() cannot accept VARIANT input
- [ ] LATERAL converts JSON null to SQL NULL
> LATERAL allows a table function to reference columns from preceding items in the FROM clause, including a previous FLATTEN's output.
