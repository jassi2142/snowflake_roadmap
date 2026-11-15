# What is Snowflake?

Snowflake is a cloud data platform delivered as a fully managed service. You use it to store, transform, query, and share data with SQL and other languages, without installing hardware or software or tuning the system yourself. It matters because one platform covers work that used to need several separate systems: data warehousing, data lakes, data engineering, data sharing, and AI/ML.

## How it works

Snowflake runs entirely on public cloud infrastructure: Amazon Web Services, Microsoft Azure, or Google Cloud. You never manage servers, operating systems, or upgrades. Snowflake handles maintenance, patching, and tuning, and it releases new features on a regular schedule.

A few core ideas set Snowflake apart from a traditional database:

- **Separation of storage and compute.** Data sits in one central storage layer. Queries run on independent compute clusters called **virtual warehouses**. You can resize, start, or stop a warehouse without moving any data, and several warehouses can read the same data at once without competing for resources.
- **Pay for what you use.** Compute is billed in **credits** while warehouses are running. Storage is billed separately based on the amount of data stored. Warehouses can suspend automatically when idle, so you stop paying for compute when nobody is using it.
- **Automatic data organization.** When data is loaded, Snowflake compresses it, stores it in a columnar format, and splits it into small units called micro-partitions. You do not need to define indexes or partitions to get good performance.
- **Native support for many data shapes.** Alongside structured tables, Snowflake supports semi-structured data (JSON, Avro, ORC, Parquet, XML), geospatial data, and unstructured files.
- **Secure data sharing.** You can give other Snowflake accounts live, read-only access to your data without copying it.

You interact with Snowflake through **Snowsight** (the web interface), the **Snowflake CLI**, drivers such as JDBC, ODBC, and the Python connector, and many third-party tools.

## Example

After signing in, you can run SQL right away. This example creates a small warehouse that suspends itself after 60 seconds of inactivity, then queries one of the sample datasets.

```sql
CREATE WAREHOUSE IF NOT EXISTS learn_wh
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

USE WAREHOUSE learn_wh;

SELECT c_mktsegment, COUNT(*) AS customers
FROM snowflake_sample_data.tpch_sf1.customer
GROUP BY c_mktsegment
ORDER BY customers DESC;
```

The warehouse supplies the compute; the data itself sits in Snowflake's storage layer.

## Best practices

- Start with the smallest warehouse that meets your needs, and size up only if queries are too slow.
- Keep auto-suspend enabled so idle warehouses stop using credits.
- Use separate warehouses for different workloads (for example, loading and reporting) so they do not slow each other down.
- Learn the three-layer architecture early. Most cost and performance decisions follow from it.

## Common pitfalls

- Treating Snowflake like an on-premises database and trying to manage indexes or physical partitions that do not exist.
- Leaving large warehouses running, or turning off auto-suspend, which wastes credits.
- Assuming storage and compute are billed together. They are separate charges.

## Learn more

- [Key concepts & architecture](https://docs.snowflake.com/en/user-guide/intro-key-concepts)
- [Snowflake editions](https://docs.snowflake.com/en/user-guide/intro-editions)

## Knowledge check

### A team wants to run heavy data loads without slowing down analysts' dashboards. What Snowflake capability makes this possible?
- [ ] Creating indexes on the tables the dashboards use
- [x] Running each workload on its own virtual warehouse against the same stored data
- [ ] Copying the data into a second database for the analysts
- [ ] Scheduling loads only at night
> Storage and compute are separate, so independent warehouses can read the same data at the same time without competing for compute.

### Which statement about Snowflake billing is correct?
- [ ] Compute and storage are billed as one combined fee
- [ ] You pay for compute only when you create a warehouse
- [x] Compute is billed in credits while warehouses run, and storage is billed separately
- [ ] Storage is free and only queries are billed
> Snowflake bills credits for running compute and charges separately for the data you store.

### What does a customer need to manage to keep Snowflake's software up to date?
- [ ] Apply patches to the virtual warehouse servers
- [ ] Upgrade the database engine on each cloud VM
- [x] Nothing; Snowflake is a managed service and handles updates
- [ ] Reinstall drivers after every release
> Snowflake is a fully managed service, so infrastructure, software upgrades, and maintenance are handled by Snowflake.
