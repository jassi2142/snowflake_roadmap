# Git Integration

Snowflake's Git integration connects a remote Git repository (on GitHub, GitLab, Bitbucket, Azure DevOps, and other supported platforms) to your account as a **Git repository clone** object. You can then browse branches, tags, and commits, run SQL scripts directly from the repository, and use repository files for stored procedure and UDF handlers, Streamlit apps, notebooks, and Workspaces, which makes Git the source of truth for code that runs in Snowflake.

## How it works

Setting up Git integration involves three objects:

1. **Secret** (optional, for private repositories): stores credentials such as a username and personal access token (`TYPE = PASSWORD`). Public repositories do not need one.
2. **API integration** (`CREATE API INTEGRATION ... API_PROVIDER = git_https_api`): an account-level object that lists allowed repository URL prefixes (`API_ALLOWED_PREFIXES`) and the secrets that may be used (`ALLOWED_AUTHENTICATION_SECRETS`). Creating it requires the account-level `CREATE INTEGRATION` privilege.
3. **Git repository** (`CREATE GIT REPOSITORY`): a schema-level object pointing at the repository's origin URL with the API integration and optional secret.

Once created, the repository behaves like a read-only stage. Files are addressed by branch, tag, or commit:

- `@repo/branches/main/path/file.sql`
- `@repo/tags/v1.4.0/path/file.sql`
- `@repo/commits/<hash>/path/file.sql`

**Syncing.** The clone does not update automatically from SQL alone. `ALTER GIT REPOSITORY ... FETCH` pulls all branches, tags, and commits from the remote and prunes ones that no longer exist.

**Running code.** `EXECUTE IMMEDIATE FROM @repo/branches/main/deploy.sql` runs a SQL file from the repository. Combined with Jinja templating and `USING` variables, this lets one script deploy to several environments. Repository files can also be referenced in `IMPORTS` for Python, Java, or Scala handlers.

**Pushing.** Git repository objects are read-only from SQL. Snowsight Workspaces connected to a Git repository support pull, commit, and push from the UI for private repositories.

**Access.** Git operations can fail with insufficient privileges if neither the current role nor the repository's owner role has `USAGE` on the API integration. Reading files requires `READ` on the repository.

## Example

Connect a private GitHub repository and deploy a script from a release tag.

```sql
CREATE OR REPLACE SECRET platform.git.github_pat
  TYPE = PASSWORD
  USERNAME = 'deploy-bot'
  PASSWORD = 'replace-with-personal-access-token';

CREATE OR REPLACE API INTEGRATION github_api_integration
  API_PROVIDER = git_https_api
  API_ALLOWED_PREFIXES = ('https://github.com/my-org')
  ALLOWED_AUTHENTICATION_SECRETS = (platform.git.github_pat)
  ENABLED = TRUE;

CREATE OR REPLACE GIT REPOSITORY platform.git.data_platform
  API_INTEGRATION = github_api_integration
  GIT_CREDENTIALS = platform.git.github_pat
  ORIGIN = 'https://github.com/my-org/data-platform.git';

ALTER GIT REPOSITORY platform.git.data_platform FETCH;

SHOW GIT TAGS IN platform.git.data_platform;
LS @platform.git.data_platform/tags/v1.4.0/sql;

EXECUTE IMMEDIATE FROM @platform.git.data_platform/tags/v1.4.0/sql/deploy.sql;
```

Deploying from a tag rather than a branch makes the deployment reproducible.

## Best practices

- Deploy from tags or specific commits in production, not from a moving branch.
- Narrow `API_ALLOWED_PREFIXES` to your organization or specific repositories.
- Use a dedicated bot account or app token with read-only scope for the secret, and rotate it.
- Run `FETCH` as an explicit step in your deployment pipeline so Snowflake sees the latest commits.
- Keep the API integration and secrets in a platform-owned schema with restricted grants.

## Common pitfalls

- Forgetting to `FETCH`, then deploying stale code.
- Expecting to push commits from SQL; the repository object is read-only.
- Granting `READ` on the repository but not `USAGE` on the API integration.
- Using a personal token tied to an employee who later leaves.

## Learn more

- [Working with Git repositories](https://docs.snowflake.com/en/developer-guide/git/git-operations)
- [Connect to a Git repository over a public network](https://docs.snowflake.com/en/developer-guide/git/git-setting-up-public)
- [ALTER GIT REPOSITORY](https://docs.snowflake.com/en/sql-reference/sql/alter-git-repository)

## Knowledge check

### A developer merged a fix to `main`, but `EXECUTE IMMEDIATE FROM @repo/branches/main/deploy.sql` still runs the old code. Why?
- [ ] EXECUTE IMMEDIATE caches files for 24 hours
- [x] The repository clone has not been refreshed with ALTER GIT REPOSITORY ... FETCH
- [ ] Branches cannot be used, only tags
- [ ] The API integration is disabled
> The Snowflake clone reflects the remote only as of the last fetch.

### Which object defines which repository URLs Snowflake is allowed to connect to?
- [ ] The secret
- [ ] The Git repository object
- [x] The API integration, through API_ALLOWED_PREFIXES
- [ ] A network policy
> The API integration restricts allowed URL prefixes and authentication secrets for Git repositories.

### For a reproducible production deployment, which path should you execute?
- [ ] @repo/branches/main/deploy.sql
- [x] @repo/tags/v2.3.0/deploy.sql
- [ ] @repo/branches/dev/deploy.sql
- [ ] A copy of the script pasted into a worksheet
> Tags and commits are immutable references, so the same code runs every time.
