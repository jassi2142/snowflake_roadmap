# Native App Framework

The Snowflake Native App Framework lets providers package code, data, and UI into an application that consumers install and run inside their own Snowflake accounts. The consumer's data never leaves their account, and the provider's logic and IP remain protected - a fundamentally different distribution model from shipping SaaS or sharing raw data.

## How it works

### Provider-side building blocks

- **Application package** - the container for an app's data content, logic, and versions. Creating one needs the global `CREATE APPLICATION PACKAGE` privilege. Privileges on the package separate duties: `DEVELOP` (create the app in development mode), `INSTALL`, `MANAGE VERSIONS`, `MANAGE RELEASES`, and `ATTACH LISTING`.
- **Manifest file (`manifest.yml`)** - points to the setup script and declares version information, configuration, the privileges the app requests, and **references** - named requests for consumer objects (for example "orders table" with `SELECT`) that the consumer binds at install time.
- **Setup script** - SQL executed when the app is installed or upgraded. It creates the app's internal objects, **application roles**, and grants to those roles. Consumers access the app only through application roles.
- **Release channels** - enabled by default on new packages and cannot be disabled afterwards. They manage which versions and patches are offered to which consumers.
- **Distribution** - setting `DISTRIBUTION = EXTERNAL` (sharing outside your organization) triggers an automated security scan of each version and patch; internal distribution does not.

Apps are published through **listings** (private or Marketplace), which also provide Cross-Cloud Auto-Fulfillment for application packages.

### Consumer-side model

The consumer installs an **APPLICATION** object. The app runs with its own identity and has no access to consumer data until the consumer grants requested privileges or binds references. Consumers grant application roles to their own account roles to control who can use the app. Providers can optionally allow up to 30 instances per consumer account with `MULTIPLE_INSTANCES = TRUE`, a setting that cannot be reverted.

### Architectural trade-offs

- **Data gravity vs. control.** Running in the consumer account removes data egress and eases compliance reviews, but the provider loses direct operational visibility; plan for event sharing and telemetry from the start.
- **Versioned schemas.** Keep stateless objects (procedures, views) in versioned schemas and state (tables) in regular schemas, so upgrades and rollbacks do not destroy consumer data.
- **Least privilege.** Every requested privilege and reference is a consent prompt. Request narrowly scoped references instead of broad account privileges.
- **Upgrade discipline.** Setup scripts must be idempotent (`CREATE OR REPLACE`, `CREATE ... IF NOT EXISTS`, `CREATE OR ALTER VERSIONED SCHEMA`) because they rerun on every upgrade.
- **Compute.** Apps can include Streamlit UIs and Snowpark Container Services workloads; container apps add compute pool and specification management.

## Example

`manifest.yml`:

```yaml
manifest_version: 1
artifacts:
  setup_script: setup.sql
  readme: README.md
references:
  - orders_table:
      label: "Orders table"
      description: "Table containing the orders to score"
      privileges:
        - SELECT
      object_type: TABLE
      multi_valued: false
      register_callback: core.register_reference
```

`setup.sql`:

```sql
CREATE APPLICATION ROLE IF NOT EXISTS app_user;

CREATE OR ALTER VERSIONED SCHEMA core;
GRANT USAGE ON SCHEMA core TO APPLICATION ROLE app_user;

CREATE OR REPLACE PROCEDURE core.register_reference(ref_name STRING, operation STRING, ref_or_alias STRING)
RETURNS STRING
LANGUAGE SQL
AS $$
BEGIN
  CASE (operation)
    WHEN 'ADD' THEN SELECT SYSTEM$SET_REFERENCE(:ref_name, :ref_or_alias);
    WHEN 'REMOVE' THEN SELECT SYSTEM$REMOVE_REFERENCE(:ref_name, :ref_or_alias);
    WHEN 'CLEAR' THEN SELECT SYSTEM$REMOVE_ALL_REFERENCES(:ref_name);
  END CASE;
  RETURN 'OK';
END;
$$;

CREATE OR REPLACE VIEW core.order_counts AS
  SELECT COUNT(*) AS n FROM REFERENCE('orders_table');
GRANT SELECT ON VIEW core.order_counts TO APPLICATION ROLE app_user;
```

Provider: create the package and install locally for testing (the Snowflake CLI command `snow app run` automates these steps):

```sql
CREATE APPLICATION PACKAGE order_scorer_pkg;
CREATE SCHEMA order_scorer_pkg.stage_content;
CREATE STAGE order_scorer_pkg.stage_content.files;
-- upload manifest.yml, setup.sql, README.md to the stage, then:
CREATE APPLICATION order_scorer_dev
  FROM APPLICATION PACKAGE order_scorer_pkg
  USING '@order_scorer_pkg.stage_content.files';
```

Consumer: after installing from a listing, expose the app to a team:

```sql
GRANT APPLICATION ROLE order_scorer.app_user TO ROLE analyst;
```

## Best practices

- Separate stateful and stateless objects using versioned schemas.
- Request references for specific consumer objects instead of broad privileges.
- Use release channels to test with internal or pilot consumers before default release.
- Make setup scripts idempotent and test upgrades from every supported prior version.
- Design telemetry and event sharing up front for supportability.

## Common pitfalls

- Storing consumer state in a versioned schema, where it is dropped when old versions are retired.
- Forgetting that `DISTRIBUTION = EXTERNAL` requires the security scan to pass before release.
- Setting `MULTIPLE_INSTANCES = TRUE` casually; it cannot be turned off.
- Assuming the app can read consumer data without privileges or reference bindings.

## Learn more

- [Create and manage an application package](https://docs.snowflake.com/en/developer-guide/native-apps/creating-app-package)
- [Snowflake Native App Framework workflow](https://docs.snowflake.com/en/developer-guide/native-apps/native-apps-workflow)

## Knowledge check

### An app must read a consumer's ORDERS table, but the table name differs per customer. What is the right mechanism?
- [ ] Hard-code the table name in the setup script
- [x] Declare a reference in the manifest that the consumer binds to their table at install time
- [ ] Ask the consumer to share the table back to the provider
- [ ] Grant the app ACCOUNTADMIN
> References let the app request privileges on a consumer object without knowing its name, and the consumer explicitly binds and consents.

### After an upgrade, consumer-generated results stored by the app disappear. What design error is most likely?
- [ ] The app used application roles
- [x] The results table was created in a versioned schema
- [ ] The manifest lacked a readme
- [ ] Release channels were enabled
> Versioned schemas are tied to app versions and are intended for stateless code objects; state belongs in regular schemas.

### A provider wants to distribute an app to customers outside their organization. What happens when DISTRIBUTION is EXTERNAL?
- [ ] Nothing changes from internal distribution
- [x] Each version and patch goes through an automated security scan
- [ ] The app can only be installed in reader accounts
- [ ] Release channels are disabled
> Choosing external distribution initiates an automated security scan for each version and patch in the application package.
