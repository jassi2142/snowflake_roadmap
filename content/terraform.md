# Terraform Provider

The Snowflake Terraform provider lets you define Snowflake infrastructure, such as warehouses, databases, schemas, roles, grants, and users, as code in HashiCorp Configuration Language (HCL). Terraform compares your configuration with what exists and applies only the needed changes, giving you reviewable, repeatable, and auditable account administration.

## How it works

**Declarative state.** You describe the desired end state in `.tf` files. Terraform keeps a **state file** that maps each resource in your code to a real Snowflake object. Each run follows a cycle:

1. `terraform init` downloads the provider (published as `snowflakedb/snowflake` in the Terraform Registry).
2. `terraform plan` compares configuration, state, and the real account, and shows what will be created, changed, or destroyed.
3. `terraform apply` executes the plan by issuing SQL against Snowflake.

**Provider configuration.** The `provider "snowflake"` block identifies the account (organization and account name) and authentication. For automation, use a dedicated service user with key-pair authentication rather than a password, and pass secrets through environment variables or a secrets manager.

**Resources and data sources.** Resources (for example `snowflake_warehouse`, `snowflake_database`, `snowflake_schema`, `snowflake_account_role`, and grant resources) create and manage objects. Data sources read existing objects without managing them.

**What to manage with Terraform.** Terraform is strongest for account-level and structural objects: warehouses, databases, roles, role hierarchy, grants, users, network policies, integrations, and resource monitors. Table schemas and transformation logic change frequently and usually fit better in migration tools or dbt.

**State matters.** The state file can contain sensitive values, so store it in a secured remote backend with locking (for example, an S3 bucket with locking, Azure Storage, or Terraform Cloud). Changes made by hand in Snowsight create **drift**, which the next `plan` reports and may try to revert.

**Versions.** The provider evolves, and major versions have included breaking changes and resource renames. Pin the provider version and read the migration guide before upgrading.

## Example

A minimal configuration that creates a database, a warehouse, a role, and grants.

```hcl
terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

provider "snowflake" {
  organization_name = "MYORG"
  account_name      = "ANALYTICS_PROD"
  user              = "TERRAFORM_SVC"
  role              = "SYSADMIN"
  authenticator     = "SNOWFLAKE_JWT"
  private_key       = file(var.private_key_path)
}

resource "snowflake_database" "analytics" {
  name    = "ANALYTICS"
  comment = "Managed by Terraform"
}

resource "snowflake_warehouse" "transform" {
  name           = "TRANSFORM_WH"
  warehouse_size = "SMALL"
  auto_suspend   = 60
  auto_resume    = true
}

resource "snowflake_account_role" "analyst" {
  name = "ANALYST"
}

resource "snowflake_grant_privileges_to_account_role" "analyst_db_usage" {
  account_role_name = snowflake_account_role.analyst.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.analytics.name
  }
}
```

Run `terraform plan` to review, then `terraform apply`. Resource and argument names differ between provider versions, so check the registry documentation for the version you pin.

## Best practices

- Pin provider versions and upgrade deliberately, following the official migration guide.
- Use a remote, encrypted, locked state backend; never commit state to Git.
- Authenticate with a dedicated service user and key pair, using a role with only the privileges Terraform needs.
- Split configurations by blast radius (for example, account-level objects separate from per-team databases).
- Run `plan` in pull requests and `apply` only from CI after approval.
- Use `terraform import` (or import blocks) to bring existing objects under management instead of recreating them.

## Common pitfalls

- Making manual changes in Snowsight, then being surprised when Terraform reverts them.
- Managing the same object in two Terraform configurations, or in Terraform and another tool.
- Destroying and recreating databases because of a renamed or moved resource, which loses data; review every plan for destroys.
- Using ACCOUNTADMIN for all Terraform runs.

## Learn more

- [Snowflake Terraform provider (Terraform Registry)](https://registry.terraform.io/providers/snowflakedb/snowflake/latest/docs)

## Knowledge check

### An engineer resized a warehouse manually in Snowsight. What happens on the next `terraform apply` if the code still has the old size?
- [ ] Terraform adopts the new size automatically
- [x] Terraform detects drift and changes the warehouse back to the size in code
- [ ] Terraform fails with an error
- [ ] Terraform drops and recreates the warehouse
> Terraform reconciles real objects to the configuration, so manual changes are reported as drift and reverted.

### Why should the Terraform state file be stored in a secured remote backend?
- [ ] Snowflake requires it
- [x] It can contain sensitive values and must be shared with locking to prevent concurrent corruption
- [ ] Terraform cannot run without internet access
- [ ] It stores table data
> State maps resources to real objects, may include secrets, and needs locking when several people or pipelines run Terraform.

### Which objects are usually the best fit for Terraform in a Snowflake platform?
- [ ] Rows in reference tables
- [ ] Transformation SQL for daily models
- [x] Warehouses, databases, roles, grants, and integrations
- [ ] Ad hoc analyst queries
> Terraform excels at structural and account-level objects; frequently changing table logic is better handled by migration tools or dbt.
