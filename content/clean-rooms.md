# Data Clean Rooms

A data clean room lets two or more organizations analyze their combined data without either side seeing the other's raw rows. Snowflake Data Clean Rooms are built on Snowflake's sharing and Native App technology, so data stays in each party's account while only approved queries - and approved outputs - cross the boundary.

## How it works

Snowflake currently offers the **Collaboration** clean room experience (generally available, not available in government or VPS deployments). The legacy Provider and Consumer clean rooms are being discontinued, so new designs should target collaborations.

A **collaboration** is defined by a YAML specification and has three collaboration roles - capabilities, not RBAC roles:

- **Owner** - creates the collaboration, invites collaborators, assigns roles, decides who can share data with whom, and tears it down. Exactly one per collaboration, and it cannot be transferred. The owner gets no elevated run privileges by default.
- **Data provider** - contributes **data offerings** (tables or views exposed as a live view, with the columns and policies defined in the offering spec) to specific analysis runners.
- **Analysis runner** - runs approved **templates** against the data offerings it has been granted.

One account can hold several roles. Other resources include **templates** (JinjaSQL queries with run-time parameters, whose results are either returned directly or **activated** into a designated collaborator's account) and **code specs** (custom Python functions or procedures callable from templates). After creation, the owner can propose changes such as adding collaborators or changing roles, which take effect only after the affected collaborators approve them.

Requirements and constraints:

- Data providers need **Enterprise Edition**; owners and analysis runners can use Standard Edition. Activating results to another Snowflake account also requires Enterprise Edition. Trial accounts are not supported.
- Collaborators in other cloud regions must enable Cross-Cloud Auto-Fulfillment before joining.
- Collaborations can be managed in Snowsight or through the Collaboration API (stored procedures in `SAMOOHA_BY_SNOWFLAKE_LOCAL_DB.COLLABORATION`).

### Design considerations

- **Trust model.** Neither side can query the other's data directly; access is only through templates both sides accept. Template review is the critical security control - a permissive template (for example one that returns row-level identifiers) defeats the purpose.
- **Privacy controls.** Clean rooms support join and column policies on data offerings and differential privacy. Aggregation thresholds and projection limits should be part of every template design.
- **Activation risk.** Exporting results is the main path for data to leave; restrict which templates can activate and to whose account.
- **Cost.** The account running an analysis pays standard compute; cross-region collaboration adds replication costs.

## Example

A minimal collaboration specification - Alice owns the collaboration and runs `template1` against her own data and Bob's; Bob runs `template2` against one of Alice's offerings:

```yaml
api_version: 2.0.0
spec_type: collaboration
name: basic_collaboration
owner: alice
collaborator_identifier_aliases:
  alice: corp1.acct123
  bob: corp2.acctxyz
analysis_runners:
  alice:
    data_providers:
      alice:
        data_offerings:
        - id: alice_data_1
      bob:
        data_offerings:
        - id: bob_data_1
    templates:
    - id: template1
  bob:
    data_providers:
      alice:
        data_offerings:
        - id: alice_data_1
    templates:
    - id: template2
```

Check your roles and the spec after joining:

```sql
CALL SAMOOHA_BY_SNOWFLAKE_LOCAL_DB.COLLABORATION.GET_STATUS('basic_collaboration');

CALL SAMOOHA_BY_SNOWFLAKE_LOCAL_DB.COLLABORATION.VIEW_COLLABORATIONS()
  ->> SELECT "COLLABORATION_SPEC" FROM $1
      WHERE "SOURCE_NAME" = 'basic_collaboration';
```

## Best practices

- Design templates to return only aggregates, with minimum group sizes, and review every template change.
- Expose curated views with only the join keys and attributes required, not full tables.
- Grant each analysis runner only the data offerings it needs, rather than all offerings to everyone.
- Use differential privacy for exploratory or repeated queries where re-identification risk is higher.
- Plan migrations off legacy Provider/Consumer clean rooms now.

## Common pitfalls

- Treating the owner role as an administrator with data access; it has none by default.
- Data providers on Standard Edition, which cannot share data with policy enforcement.
- Forgetting Cross-Cloud Auto-Fulfillment for collaborators in other regions.
- Approving templates that allow arbitrary projections, which can leak row-level data.

## Learn more

- [Overview of Snowflake Data Clean Rooms](https://docs.snowflake.com/en/user-guide/cleanrooms/overview)
- [Collaborator roles in Collaboration Data Clean Rooms](https://docs.snowflake.com/en/user-guide/cleanrooms/roles)

## Knowledge check

### An advertiser (Standard Edition) and a publisher (Enterprise Edition) want to measure audience overlap. Only the publisher's data is shared. Which setup works?
- [ ] Neither can participate without Business Critical
- [x] The publisher acts as data provider; the advertiser can be owner and analysis runner on Standard Edition
- [ ] The advertiser must be the data provider
- [ ] Both must be data providers
> Data providers require Enterprise Edition, while owners and analysis runners can use Standard Edition.

### The collaboration owner wants to add a new analysis runner after creation. What happens?
- [ ] The change applies immediately
- [x] The owner proposes the edit, and it takes effect only after affected collaborators approve
- [ ] The collaboration must be recreated
- [ ] Only Snowflake Support can add collaborators
> Changes to collaborators and roles are requested by the owner and require approval from the affected collaborators.

### What is the main control preventing an analysis runner from extracting a partner's raw rows?
- [ ] Network policies on the partner account
- [ ] The owner role's privileges
- [x] Approved templates and data offering policies that limit what queries can return
- [ ] Tri-Secret Secure
> Data in a clean room is accessible only through approved templates, constrained by the policies defined on each data offering.
