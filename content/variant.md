# VARIANT, OBJECT, ARRAY

VARIANT, OBJECT, and ARRAY are Snowflake's semi-structured data types. They let you store and query data such as JSON, Avro, ORC, Parquet, and XML without defining every field up front, which makes it easy to load data whose shape varies or changes over time.

## How it works

**VARIANT** can hold a value of any other type, including OBJECT and ARRAY. It stores both the value and its type. A VARIANT value can be up to 128 MB of uncompressed data, though the practical maximum is usually smaller because of internal overhead.

**OBJECT** is like a JSON object or a dictionary: a set of key-value pairs. Each key is a VARCHAR and each value is a VARIANT, so different keys can hold different types. Keys should not be empty strings, and neither key nor value should be NULL.

**ARRAY** is an ordered list. Each element is a VARIANT, so elements can have different types. Indexes start at 0, arrays grow dynamically, and reading past the end returns NULL.

You access nested data with path notation:

- Colon for the first level: `v:customer`
- Dot or brackets for deeper levels: `v:customer.name` or `v['customer']['name']`
- Brackets with a number for arrays: `v:items[0]`

Values extracted from a VARIANT are still VARIANT. Strings display with double quotes until you cast them, for example `v:customer.name::STRING`. Use `TYPEOF` to see the stored type.

There are two kinds of null:

- **SQL NULL**: the value is missing.
- **JSON null**: a real value meaning "null" in the source data. Convert it to SQL NULL by casting to a string, for example `TO_VARCHAR(v:a)`.

When data is loaded from JSON, values without a native JSON type, such as dates and timestamps, are stored as strings inside the VARIANT. Snowflake also offers **structured** ARRAY, OBJECT, and MAP types (for example `ARRAY(INTEGER)`) when you want declared element types.

## Example

Create a table and insert JSON:

```sql
CREATE OR REPLACE TABLE raw_orders (v VARIANT);

INSERT INTO raw_orders
  SELECT PARSE_JSON('{
    "order_id": 1001,
    "customer": {"name": "Ana", "tier": "gold"},
    "items": [{"sku": "A1", "qty": 2}, {"sku": "B7", "qty": 1}],
    "coupon": null
  }');
```

Query nested fields and cast them to proper types:

```sql
SELECT v:order_id::NUMBER        AS order_id,
       v:customer.name::STRING   AS customer_name,
       v:items[0].sku::STRING    AS first_sku,
       ARRAY_SIZE(v:items)       AS item_count,
       TYPEOF(v:coupon)          AS coupon_type
FROM raw_orders;
```

Build OBJECT and ARRAY values with functions or literals:

```sql
SELECT OBJECT_CONSTRUCT('name', 'Jones', 'age', 42) AS person,
       ARRAY_CONSTRUCT(1, 'two', 3.0)              AS mixed,
       {'city': 'Oslo', 'zip': '0150'}              AS object_literal,
       [10, 20, 30]                                 AS array_literal;
```

## Best practices

- Land raw semi-structured data in a VARIANT column first if you do not yet know how it will be queried.
- Always cast extracted values (`::STRING`, `::NUMBER`, `::DATE`) before comparing, joining, or displaying them.
- Promote frequently queried fields, especially dates, timestamps, and numbers stored as strings, into typed relational columns.
- Use `STRIP_NULL_VALUES = TRUE` in the file format if JSON nulls just mean "missing".
- Use `TRY_PARSE_JSON` when input may be malformed.

## Common pitfalls

- Forgetting that path names are case-sensitive: `v:Customer` and `v:customer` are different.
- Comparing an uncast VARIANT to a string literal and getting unexpected results or quoted output.
- Confusing JSON null with SQL NULL in filters (`IS NULL` does not match JSON null).
- Assuming array indexes start at 1; they start at 0.

## Learn more

- [Semi-structured data types](https://docs.snowflake.com/en/sql-reference/data-types-semistructured)
- [Considerations for semi-structured data stored in VARIANT](https://docs.snowflake.com/en/user-guide/semistructured-considerations)

## Knowledge check

### A VARIANT column `v` contains `{"status": "open"}`. Which expression returns the plain text open without quotes?
- [ ] v:status
- [x] v:status::STRING
- [ ] v.status
- [ ] TYPEOF(v:status)
> Extracted values remain VARIANT and display with quotes; casting to STRING returns the plain value.

### For JSON `{"a": null}`, why does `WHERE v:a IS NULL` not match the row?
- [ ] Path expressions cannot be used in WHERE
- [x] v:a is a JSON null value, which is different from SQL NULL
- [ ] The key a is case-insensitive
- [ ] VARIANT columns cannot contain null
> JSON null is a real stored value; convert it with a cast such as TO_VARCHAR to obtain SQL NULL.

### What is the index of the first element in a Snowflake ARRAY?
- [x] 0
- [ ] 1
- [ ] -1
- [ ] It depends on the data
> Snowflake arrays are 0-based, so the first element is at index 0.
