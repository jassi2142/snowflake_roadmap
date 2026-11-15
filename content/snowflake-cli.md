# Snowflake CLI

Snowflake CLI is an open-source command-line tool for working with Snowflake from your terminal. The command is `snow`. You can use it to run SQL, manage objects and stages, and develop and deploy workloads such as Snowpark code, Streamlit apps, Native Apps, notebooks, and dbt projects. It is useful for automation, scripting, and CI/CD pipelines.

## How it works

Snowflake CLI is available in every Snowflake edition. Its main ideas are:

- **Connections.** The CLI stores named connection profiles (account, user, authentication method, default role, warehouse, database, and schema) in a configuration file. You can mark one connection as the default and choose another for a single command with `--connection` (or `-c`).
- **Authentication.** Connections can use the methods Snowflake supports, such as key-pair authentication, browser-based SSO, OAuth, or programmatic access tokens. For automation, prefer key-pair authentication or workload identity over passwords.
- **Command groups.** Commands are grouped by area. For example, `snow sql` runs SQL, `snow connection` manages profiles, `snow object` lists and describes objects, and `snow stage` manages files on stages. Other groups cover Snowpark, Streamlit, Native Apps, Git repositories, and more.
- **Project definitions.** For application work, a `snowflake.yml` file in your project describes what to deploy. That lets the same commands deploy the project to different environments.
- **Help.** Run `snow --help` or `snow <group> --help` to see the commands and options in your installed version.

## Example

Add a connection interactively, then test it:

```bash
snow connection add
snow connection test --connection learn
```

Run a single query, or a SQL file, with that connection:

```bash
snow sql -q "SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()" -c learn
snow sql -f setup.sql -c learn
```

Upload a local file to a stage, then list the stage's contents:

```bash
snow stage copy ./data/orders.csv @learn_db.public.raw_stage -c learn
snow stage list-files @learn_db.public.raw_stage -c learn
```

List the tables in a schema:

```bash
snow object list table --database learn_db --schema public -c learn
```

## Best practices

- Create a separate named connection for each environment (dev, test, prod), and pass `-c` explicitly in scripts.
- Keep secrets out of scripts and source control. Use key-pair files, environment variables, or your CI system's secret store.
- Keep SQL in version-controlled `.sql` files and run them with `snow sql -f` so deployments can be repeated.
- Run `--help` for your installed version rather than relying on memory; options change between releases.

## Common pitfalls

- Running a command against the wrong account because the default connection points somewhere unexpected.
- Hard-coding passwords in shell history or CI configuration.
- Confusing Snowflake CLI (`snow`) with the older SnowSQL client (`snowsql`). They are different tools with different commands and configuration files.

## Learn more

- [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index)

## Knowledge check

### A CI pipeline must run a migration script against production with Snowflake CLI. What is the best approach?
- [ ] Rely on whatever the default connection is on the build agent
- [x] Define a named production connection using key-pair auth from the secret store, and run `snow sql -f migrate.sql -c prod`
- [ ] Paste the SQL into Snowsight manually
- [ ] Put the password directly in the command line
> Naming the connection explicitly and using secret-managed, non-password authentication makes runs safe and repeatable.

### Which command runs an ad hoc SQL statement?
- [ ] `snow run "SELECT 1"`
- [x] `snow sql -q "SELECT 1"`
- [ ] `snow query --text "SELECT 1"`
- [ ] `snowsql -q "SELECT 1"` (this is Snowflake CLI)
> `snow sql -q` runs a query string, and `-f` runs a file. `snowsql` is a different, older client.

### What is the purpose of `snowflake.yml` in a Snowflake CLI project?
- [ ] It stores user passwords
- [x] It defines the project's entities so they can be deployed with CLI commands
- [ ] It configures the warehouse size for the account
- [ ] It replaces the connection configuration file
> The project definition file describes what to deploy, while connections are stored separately in the CLI configuration.
