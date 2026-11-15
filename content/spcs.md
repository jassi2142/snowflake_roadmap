# Snowpark Container Services

Snowpark Container Services (SPCS) is a fully managed container platform inside Snowflake: you push OCI images to a Snowflake image registry and run them as long-running services or batch jobs on compute pools, with Snowflake handling scheduling, networking, identity, and governance. It is the escape hatch for workloads that do not fit warehouses or UDFs, such as GPU inference, custom web apps and APIs, third-party engines, and specialized runtimes, while keeping data inside the Snowflake security boundary.

## How it works

The core objects are:

- **Image repository**: an account-hosted OCI registry (`CREATE IMAGE REPOSITORY`) that you push to with standard Docker tooling.
- **Compute pool**: an account-level pool of VM nodes defined by `INSTANCE_FAMILY` (CPU, high-memory, or GPU families) and `MIN_NODES` and `MAX_NODES`. Snowflake autoscales nodes between those bounds and removes idle nodes down to the minimum. Billing follows the instance type actually provisioned, including any `BACKUP_INSTANCE_FAMILIES` used during capacity shortages. Every account also includes system pools (`SYSTEM_COMPUTE_POOL_CPU` and `SYSTEM_COMPUTE_POOL_GPU`) for notebooks, Streamlit (CPU only), model serving, and ML jobs.
- **Service**: created with `CREATE SERVICE ... IN COMPUTE POOL ... FROM SPECIFICATION`, using a YAML spec that lists containers, resources, volumes (including stage mounts and block storage), readiness probes, and endpoints. `MIN_INSTANCES` and `MAX_INSTANCES` control replicas. All containers in one instance always run on a single node. Job services (`EXECUTE JOB SERVICE`) run to completion.
- **Networking**: endpoints can be private (service-to-service through Snowflake DNS) or `public: true` for HTTP ingress authenticated by Snowflake. Egress to the internet is blocked unless you attach an external access integration. Service functions expose an endpoint as a SQL function for batch calls from queries.

**Privileges**: compute pools support MODIFY, MONITOR, OPERATE, USAGE, and OWNERSHIP. USAGE allows creating services and can trigger auto-resume. By default USAGE on the system pools is granted to PUBLIC, and an ACCOUNTADMIN can revoke it.

**Operational realities**:

- Snowflake performs node maintenance in weekly windows (weekend nights in the region's time zone) and replaces at most 50 percent of a service's instances at a time. Snowflake therefore recommends multiple instances, a readiness probe, handling SIGTERM, and setting `MIN_READY_INSTANCES` below 50 percent of `MIN_INSTANCES`. Job services can be interrupted during maintenance.
- Stage volume mounts are limited to eight per compute pool node.
- Suspending a pool suspends its services, but job services run to a terminal state first. You must stop all services before you drop a pool.

## Example

Create a pool and repository, then run a service with a public endpoint and a SQL service function:

```sql
CREATE COMPUTE POOL api_pool
  MIN_NODES = 1
  MAX_NODES = 3
  INSTANCE_FAMILY = CPU_X64_S
  AUTO_RESUME = TRUE;

CREATE IMAGE REPOSITORY apps.spcs.images;
-- docker push <account>.registry.snowflakecomputing.com/apps/spcs/images/scorer:1.0

CREATE SERVICE apps.spcs.scorer
  IN COMPUTE POOL api_pool
  FROM SPECIFICATION $$
spec:
  containers:
  - name: scorer
    image: /apps/spcs/images/scorer:1.0
    resources:
      requests:
        memory: 2G
    readinessProbe:
      port: 8080
      path: /health
  endpoints:
  - name: api
    port: 8080
    public: true
$$
  MIN_INSTANCES = 2
  MAX_INSTANCES = 4;

CREATE FUNCTION apps.spcs.score(payload VARCHAR)
  RETURNS VARIANT
  SERVICE = apps.spcs.scorer
  ENDPOINT = api
  AS '/score';
```

Two instances and a readiness probe keep the service available during rolling maintenance. The service function lets SQL users call the container in batch.

## Best practices

- Size pools for scheduling, not just averages: resource requests decide whether instances fit on a node. Set `MAX_NODES` as a cost guardrail.
- Run at least two instances for anything user-facing, and store state in tables, stages, or block storage rather than container memory.
- Use dedicated pools per workload class (GPU inference, apps, batch jobs) so suspension, scaling, and cost attribution are independent.
- Grant only the external access integrations a service needs, with narrowly scoped network rules.
- Monitor with `SHOW SERVICE CONTAINERS IN SERVICE`, service logs in the event table, and `SYSTEM$GET_COMPUTE_POOL_PENDING_MAINTENANCE`, and schedule job services outside maintenance windows.
- Set auto-suspend on pools used intermittently, and verify that idle services are suspended.

## Common pitfalls

- Running a single-instance production service, which goes down during every maintenance replacement.
- Assuming containers can reach the internet. Without an external access integration, egress is blocked.
- Leaving GPU pools at `MIN_NODES` greater than zero after an experiment and paying for idle GPUs.
- Hitting the eight-stage-mounts-per-node limit and seeing instances stuck in PENDING with "insufficient resources".
- Leaving USAGE on the system GPU pool granted to PUBLIC in accounts where GPU spend must be controlled.

## Learn more

- [Snowpark Container Services overview](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview)
- [Working with compute pools](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/working-with-compute-pool)

## Knowledge check

### A customer-facing service with MIN_INSTANCES = 2 and MIN_READY_INSTANCES = 2 goes PENDING every weekend. What is the most likely cause and fix?
- [ ] The compute pool auto-suspends; disable AUTO_SUSPEND
- [x] Rolling maintenance replaces up to half the instances at a time, so readiness drops below the minimum; lower MIN_READY_INSTANCES below 50 percent of MIN_INSTANCES or add instances
- [ ] The image repository is unavailable during maintenance
- [ ] Public endpoints are disabled on weekends
> During maintenance, Snowflake recreates at most 50 percent of instances at a time. If MIN_READY_INSTANCES cannot be met, the service transitions to PENDING.

### A container must call a third-party REST API. What is required?
- [ ] Set the endpoint to public: true
- [ ] Nothing; services have outbound internet by default
- [x] An external access integration with network rules for that host, attached to the service
- [ ] A service function that points to the external URL
> Egress from SPCS is blocked by default. External access integrations, backed by network rules, define which external hosts a service may reach.

### Analysts need to score millions of rows in SQL with a model running in a container. Which interface fits best?
- [ ] Call the public endpoint from each row with a Python UDF
- [x] Create a service function bound to the service endpoint and call it in a SELECT
- [ ] Use EXECUTE JOB SERVICE for each query
- [ ] Copy the data into the container's local disk
> Service functions expose a service endpoint as a SQL function, so Snowflake batches rows to the container from ordinary queries.
