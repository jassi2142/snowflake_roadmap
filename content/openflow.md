# Openflow

Snowflake Openflow is a managed data integration service, built on Apache NiFi, that moves data from many kinds of sources to Snowflake and other destinations. It covers structured and unstructured data in batch and streaming modes, and it is Snowflake's answer to the question of how to run connectors (databases with CDC, SaaS apps, Kafka, file and document stores) without operating a separate integration platform.

## How it works

Openflow separates a Snowflake-managed **control plane** from the **data plane** where flows actually execute. The core objects are:

- **Deployment**: the infrastructure that hosts runtimes. There are two deployment types:
  - **Openflow - Snowflake Deployment**, which runs on Snowpark Container Services (SPCS) using a compute pool, integrated with Snowflake's security model. Available in AWS, Azure, and GCP commercial regions.
  - **Bring Your Own Cloud (BYOC)**, where the data plane runs in your own VPC as a managed Kubernetes cluster while Snowflake runs the control plane. Available in AWS commercial regions. BYOC suits cases where sensitive data must be preprocessed inside your network or private sources are reachable only from your VPC.
- **Runtime**: a cluster of NiFi runtime servers inside a deployment that runs flow definitions. Teams typically create several runtimes to isolate projects, teams, or SDLC stages.
- **Connector**: a packaged flow for a specific source, installed from the connector catalog. You can also build custom flows from NiFi processors and controller services.

**Generations.** Openflow has gen 1 and gen 2 resources. Every new deployment is gen 2; new gen 1 deployments can no longer be created. In gen 2, deployments, runtimes, and connectors are first-class Snowflake objects managed with SQL (`CREATE OPENFLOW DEPLOYMENT`, `CREATE OPENFLOW RUNTIME ... IN DEPLOYMENT`, `CREATE OPENFLOW CONNECTOR`), runtimes and connectors are schema-scoped, and connector configuration is versioned so it can be promoted through CI/CD. Gen 2 deployment and runtime objects are generally available, while gen 2 connector configuration is in public preview. Each account supports up to three Snowflake (SPCS) Openflow deployments, shared across generations.

**Security and identity.** The recommended authentication is **Snowflake Managed Token**: SPCS session tokens in Snowflake deployments, and workload identity federation in BYOC. A runtime's **execute-as role** determines what its connectors can read and write. Admin privileges include `CREATE OPENFLOW DEPLOYMENT` on the account and `CREATE OPENFLOW RUNTIME` and `CREATE OPENFLOW CONNECTOR` on a schema. Openflow users need `DEFAULT_SECONDARY_ROLES = ('ALL')`, and Openflow cannot be used while ACCOUNTADMIN, ORGADMIN, GLOBALORGADMIN, or SECURITYADMIN is the active role.

**Cost.** Snowflake deployments incur compute charges based on uptime and usage of the compute pool. BYOC deployments incur cloud infrastructure, compute, and storage costs in your account. Because gen 2 runtimes are SQL objects, you can script suspend and resume to reduce cost during idle hours.

## Example

Grant gen 2 admin privileges and enable secondary roles for an Openflow user.

```sql
USE ROLE ACCOUNTADMIN;

GRANT CREATE OPENFLOW DEPLOYMENT ON ACCOUNT TO ROLE openflow_admin;
GRANT CREATE DATABASE ON ACCOUNT TO ROLE openflow_admin;

CREATE DATABASE IF NOT EXISTS openflow_db;
CREATE SCHEMA IF NOT EXISTS openflow_db.ops;
GRANT OWNERSHIP ON DATABASE openflow_db TO ROLE openflow_admin COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA openflow_db.ops TO ROLE openflow_admin COPY CURRENT GRANTS;

ALTER USER jdoe SET DEFAULT_SECONDARY_ROLES = ('ALL');
```

Decommission a gen 2 runtime safely, draining in-flight data before dropping it.

```sql
ALTER OPENFLOW RUNTIME openflow_db.ops.cdc_runtime SUSPEND;
SELECT SYSTEM$WAIT_FOR_STABLE_OPENFLOW_RUNTIMES(600, 'openflow_db.ops.cdc_runtime');

ALTER OPENFLOW RUNTIME openflow_db.ops.cdc_runtime TERMINATE;
SELECT SYSTEM$WAIT_FOR_STABLE_OPENFLOW_RUNTIMES(600, 'openflow_db.ops.cdc_runtime');

DROP OPENFLOW RUNTIME openflow_db.ops.cdc_runtime;
```

## Best practices

- Default to a Snowflake (SPCS) deployment; choose BYOC when data residency, private network reachability, or local preprocessing requires it.
- Separate runtimes per domain or environment so a noisy or failing flow cannot starve others.
- Give each runtime a least-privilege execute-as role scoped to the target databases and schemas.
- Prefer Snowflake Managed Token over key pairs to avoid long-lived credentials.
- Manage gen 2 connector configuration as versioned artifacts and promote it through Git-based workflows.
- Stop connectors before suspending or removing runtimes, and use `TERMINATE` (not `TERMINATE FORCE`) unless data loss is acceptable.

## Common pitfalls

- Trying to use Openflow with ACCOUNTADMIN as the active role, which produces consent errors.
- Forgetting `DEFAULT_SECONDARY_ROLES`, so users cannot see or act on resources they were granted.
- Transferring ownership of gen 2 deployments, runtimes, or connectors; the docs currently warn this can break functionality.
- Assuming `USAGE` on a gen 2 deployment grants access to its runtimes; runtime privileges must be granted directly.
- Expecting Openflow in a trial account without contacting the account team.

## Learn more

- [About Openflow](https://docs.snowflake.com/en/user-guide/data-integration/openflow/about)
- [Openflow gen 1 and gen 2](https://docs.snowflake.com/en/user-guide/data-integration/openflow/gen2/openflow-generations)
- [Set up Openflow - BYOC](https://docs.snowflake.com/en/user-guide/data-integration/openflow/setup-openflow-byoc)

## Knowledge check

### A regulated customer must mask PII from an on-premises database before any data leaves their AWS network, and the database is reachable only from their VPC. Which Openflow deployment type fits?
- [ ] Openflow - Snowflake Deployment on SPCS
- [x] Bring Your Own Cloud (BYOC)
- [ ] Either; deployment type does not affect where data is processed
> In BYOC, the data plane runs inside the customer's own cloud environment, so preprocessing happens within their network boundary and private sources are reachable.

### A user with USAGE on a gen 2 Openflow deployment cannot see any of its runtimes. Why?
- [ ] Gen 2 runtimes are only visible to ACCOUNTADMIN
- [x] In gen 2, deployment USAGE does not grant runtime access; USAGE, OPERATE, or MONITOR must be granted on the runtime, plus USAGE on its database and schema
- [ ] The user needs CREATE OPENFLOW DEPLOYMENT
> Gen 2 runtimes are schema-scoped objects with their own privileges. Unlike gen 1, privileges on the deployment do not cascade to its runtimes.

### What is the recommended way for Openflow runtimes to authenticate to Snowflake?
- [ ] A shared password stored in the flow definition
- [ ] Key-pair authentication for every connector
- [x] Snowflake Managed Token, using SPCS session tokens or workload identity federation
> Snowflake Managed Token is the default and recommended method across both deployment types. It avoids long-lived credentials; key-pair authentication remains an alternative for BYOC.
