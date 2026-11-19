# Cortex Agents

Cortex Agents are schema-level Snowflake objects that orchestrate an LLM across a set of tools: Cortex Analyst for structured data, Cortex Search for unstructured content, custom procedures and functions, charting, code execution, MCP connectors, and more. They let you ship "talk to your data" and task-automation experiences where planning, tool calling, and governance all happen inside Snowflake.

## How it works

An agent can be designed interactively in **Snowsight Agent Studio** (under **AI > Agent Studio**), created via the REST API, or declared with `CREATE AGENT ... FROM SPECIFICATION`, using a YAML specification with these main sections:

- **models**: the orchestration model, or `auto`.
- **orchestration**: execution budget (`seconds`, `tokens`), `tool_not_accessible` behavior (whether a missing tool privilege aborts the run or lets it continue), and capabilities such as analytical search, which is off by default.
- **instructions**: `orchestration` (planning and routing guidance), `response` (tone and format), and `sample_questions`.
- **tools** and **tool_resources**: each tool has a type and a name (1 to 64 characters) plus its resources, for example a semantic view and warehouse for `cortex_analyst_text_to_sql`, or a search service, filters, `max_results`, and column descriptions for `cortex_search`. Custom tools wrap a stored procedure or UDF and run on the warehouse you specify.

At runtime the agent plans, selects tools, invokes them, reflects on the results, and composes a response with citations. The token budget covers orchestration only, not tokens consumed inside tools. Conversation state can be kept server-side in **threads**: you create a thread, then pass `thread_id` and `parent_message_id` (0 for the first turn) on each `:run` call, so clients do not resend history. You can call an agent with `SNOWFLAKE.CORTEX.DATA_AGENT_RUN` from SQL or `POST .../agents/<name>:run` over REST. A feedback endpoint captures ratings for iteration.

**Security**: authorization comes from the request's primary role (the `X-Snowflake-Role` header for REST, or the user's default role). Each tool then enforces its own model: Analyst needs SELECT on the semantic view, custom procedures keep their owner's-rights or caller's-rights semantics, and Cortex Search serves with owner's rights. `ALTER AGENT ... SET SPECIFICATION` replaces the entire specification, so omitted fields are removed.

Web search is an optional tool that an ACCOUNTADMIN must enable at the account level. Queries leave Snowflake to the provider's API. Snowflake documents a zero-data-retention arrangement for this, but you should still review it with your security team.

## Example

An agent that routes revenue questions to Analyst and policy questions to Search:

```sql
CREATE OR REPLACE AGENT analytics.agents.sales_assistant
  COMMENT = 'Sales and policy assistant'
  PROFILE = '{"display_name": "Sales Assistant"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto
  orchestration:
    tool_not_accessible: accept
    budget:
      seconds: 60
      tokens: 16000
  instructions:
    orchestration: "Use RevenueAnalyst for metrics and trends. Use PolicySearch for contract or policy questions. Never estimate numbers without a tool result."
    response: "Be concise. Show figures in a table and cite sources."
    sample_questions:
      - question: "What was revenue by segment last quarter?"
  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "RevenueAnalyst"
        description: "Answers questions about orders, revenue, and customers"
    - tool_spec:
        type: "cortex_search"
        name: "PolicySearch"
        description: "Searches sales policies and contract terms"
  tool_resources:
    RevenueAnalyst:
      semantic_view: "analytics.semantic.revenue_sv"
      execution_environment:
        type: "warehouse"
        warehouse: "agent_wh"
    PolicySearch:
      search_service: "docs_db.search.policy_svc"
      max_results: 5
  $$;
```

Smoke-test it from SQL:

```sql
SELECT TRY_PARSE_JSON(
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'analytics.agents.sales_assistant',
    $${"messages":[{"role":"user","content":[{"type":"text","text":"Revenue by segment in 1997?"}]}]}$$,
    TRUE
  )
) AS response;
```

## Best practices

- Write tool descriptions as routing contracts: what the tool answers, what it does not, and the key entities it covers. Poor descriptions are the most common cause of wrong tool selection.
- Keep the semantic views and search services behind the agent narrow and well-described, because agent accuracy is bounded by tool accuracy.
- Build an evaluation set (questions, expected tool, expected answer) and run it on every spec change. Treat the spec as code in Git and deploy with `CREATE OR REPLACE` or `ALTER` from CI.
- Set explicit time and token budgets to bound latency and cost, and use dedicated warehouses for tool execution so spend is attributable.
- Expose actions (writes) only through custom tools implemented as stored procedures with tightly scoped owner's rights, input validation, and auditing.

## Common pitfalls

- Patching an agent with `ALTER AGENT ... SET SPECIFICATION` using a partial spec and unintentionally deleting tools.
- Assuming the agent enforces data security on its own. Each tool's privilege model applies, including owner's rights for search.
- Packing dozens of loosely related tools into one agent, which degrades planning. Split by domain instead.
- Leaving the orchestration instruction empty, so the model guesses routing rules that the business considers fixed.
- Testing only with ACCOUNTADMIN, then failing in production because end-user roles lack USAGE or SELECT on tool objects.

## Learn more

- [Create and manage agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage)
- [Get started with Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-get-started)

## Knowledge check

### An engineer runs ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION with only a new response instruction. Afterwards, the agent no longer answers revenue questions. Why?
- [ ] The response instruction overrides tool routing
- [x] The new specification fully replaces the old one, so the omitted tools and tool_resources were removed
- [ ] ALTER AGENT resets the orchestration model to a default that cannot call tools
- [ ] The agent needs to be resumed after an ALTER
> Setting the specification replaces it wholesale. Always submit the complete specification, for example by starting from DESCRIBE AGENT output.

### Users ask policy questions, but the agent keeps querying the semantic view and returning "no data". What is the most effective first fix?
- [ ] Increase the token budget
- [ ] Switch the orchestration model
- [x] Tighten the tool descriptions and add an orchestration instruction that routes policy and contract questions to the search tool
- [ ] Add more verified queries to the semantic view
> Tool selection is driven by descriptions and orchestration instructions. Explicit routing guidance is the cheapest and most reliable correction.

### You need the agent to create support tickets in a Snowflake table. Which design is most appropriate?
- [ ] Give the agent's users INSERT on the table and let Cortex Analyst generate INSERT statements
- [x] Implement a custom tool backed by a stored procedure that validates inputs and performs the insert with scoped privileges
- [ ] Enable web search so the agent can call your ticketing API
- [ ] Use the code execution tool to run arbitrary SQL
> Custom tools wrap procedures, so writes happen through a controlled, auditable interface with known rights semantics instead of free-form generated SQL.
