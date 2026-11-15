# Object Tagging

Object tags are key-value labels you attach to Snowflake objects such as warehouses, databases, tables, views, and columns. They make it possible to find sensitive data, attribute cost to teams, and drive policy enforcement from metadata instead of from object names. Tags are the foundation for tag-based masking and other attribute-based governance.

## How it works

A **tag** is a schema-level object. When you assign it to an object you provide a string value, and Snowflake stores the pair (for example `cost_center = 'finance'`). The same tag can be assigned to many objects and object types, with the same or different values. Creating and setting tags is available to all accounts; tag propagation and tag-based masking require Enterprise Edition or higher.

**Restricting values.** `ALLOWED_VALUES` limits which strings can be assigned, keeping values consistent (for example `'confidential'`, `'internal'`, `'public'`). Multi-value tags can hold more than one value.

**How an object gets a tag.** Snowflake records the method in the `APPLY_METHOD` column of `TAG_REFERENCES`:

- **Manual:** set with `CREATE <object> ... WITH TAG` or `ALTER <object> ... SET TAG`.
- **Inheritance:** tags flow down the hierarchy. A tag on a table is inherited by its columns; a tag on a schema is inherited by objects in it; a tag on the account is inherited by warehouses.
- **Propagation:** a tag configured with `PROPAGATE` copies itself to downstream objects (see below).
- **Classification:** sensitive data classification sets system tags and can map them to your own tags.
- **Clone or LIKE:** `CREATE TABLE ... CLONE` and `CREATE TABLE ... LIKE` always carry tags to the new table.

**Quotas.** An object can have at most **50 tags**. Separately, the columns of a single table can carry at most **50 different tags** combined. A single CREATE or ALTER TABLE statement can create at most 100 tag-entity associations.

### Tag propagation

Tag propagation (Enterprise Edition) automatically applies a tag from a source to target objects. Only a tag owner with the account-level APPLY TAG privilege can enable it. Set `PROPAGATE` on the tag:

- `ON_DEPENDENCY`: views, secure views, materialized views, and dynamic tables created from a tagged object receive the tag, and changes on the source (add, change value, remove) are **continuously** reflected.
- `ON_DATA_MOVEMENT`: CTAS, `CREATE DYNAMIC TABLE`, and DML (`INSERT`, `MERGE`, `UPDATE`, `COPY INTO`) copy the tag to the target; these are **not** kept in sync afterward.
- `ON_DEPENDENCY_AND_DATA_MOVEMENT`: both.

When different sources push different values to one target, `ON_CONFLICT` decides: the default writes the string `CONFLICT`, or you can supply a custom string, use `ALLOWED_VALUES_SEQUENCE` (earlier allowed value wins), or `MERGE` for multi-value tags. Manually applied values on the target always win. System tags and inherited tags are not propagated, and a single transaction can propagate a tag to at most 10,000 downstream objects. Set `ENABLE_TAG_PROPAGATION_EVENT_LOGGING` to log conflicts and failures to an event table.

## Example

Create a cost-attribution tag with controlled values and apply it to a warehouse:

```sql
CREATE TAG governance.tags.cost_center
  ALLOWED_VALUES 'finance', 'engineering', 'marketing';

ALTER WAREHOUSE finance_wh SET TAG governance.tags.cost_center = 'finance';
```

Create a sensitivity tag that propagates to views and to tables loaded from tagged sources, resolving conflicts toward the most sensitive value:

```sql
CREATE TAG governance.tags.data_sensitivity
  ALLOWED_VALUES 'confidential', 'internal', 'public'
  PROPAGATE = ON_DEPENDENCY_AND_DATA_MOVEMENT
  ON_CONFLICT = ALLOWED_VALUES_SEQUENCE;

ALTER TABLE crm.public.customers
  MODIFY COLUMN email SET TAG governance.tags.data_sensitivity = 'confidential';
```

Check how tags arrived on a table:

```sql
SELECT tag_name, tag_value, apply_method, level, domain
FROM TABLE(crm.INFORMATION_SCHEMA.TAG_REFERENCES('crm.public.customers', 'TABLE'));
```

## Best practices

- Create tags centrally with a `tag_admin` role so names and values stay consistent; let teams apply them.
- Use `ALLOWED_VALUES` on every governance tag to prevent typos that break reports or policies.
- Tag warehouses and other compute for chargeback, and tables/columns for data sensitivity; keep the two taxonomies separate.
- Order `ALLOWED_VALUES` from most to least sensitive if you rely on `ALLOWED_VALUES_SEQUENCE` conflict resolution.

## Common pitfalls

- Hitting the 50-tag limit by using tags as free-form documentation.
- Expecting data-movement propagation to update targets when the source tag value changes later.
- Reordering `ALLOWED_VALUES` and unintentionally changing future conflict resolution.
- Assuming future grants work on tags; they are not supported, so grant APPLY TAG to a role instead.

## Learn more

- [Introduction to object tagging](https://docs.snowflake.com/en/user-guide/object-tagging/introduction)
- [Automatic tag propagation with user-defined tags](https://docs.snowflake.com/en/user-guide/object-tagging/propagation)

## Knowledge check

### A tag with PROPAGATE = ON_DATA_MOVEMENT was copied to a table created with CTAS. Later the source column's tag value changes. What happens to the CTAS table?
- [ ] Its tag value updates automatically
- [x] It keeps the value it received at the time of the data movement
- [ ] The tag is removed from the target
- [ ] The tag value becomes CONFLICT
> Data-movement propagation is a one-time copy; only dependency-based propagation is continuously kept in sync.

### A view depends on two tables tagged data_sensitivity = 'internal' and 'public'. The tag uses ON_CONFLICT = ALLOWED_VALUES_SEQUENCE with ALLOWED_VALUES 'confidential', 'internal', 'public'. What value does the view get?
- [ ] public
- [x] internal
- [ ] CONFLICT
- [ ] Both values
> With ALLOWED_VALUES_SEQUENCE, the value appearing earlier in the allowed list wins, so 'internal' is chosen over 'public'.

### You want to know whether a column's tag was set by a person or arrived via propagation. Where do you look?
- [ ] SHOW TAGS output
- [x] The APPLY_METHOD column of TAG_REFERENCES
- [ ] The tag's ALLOWED_VALUES property
- [ ] QUERY_HISTORY for the ALTER statement
> TAG_REFERENCES and related functions include APPLY_METHOD, which records how the tag was associated with the object.
