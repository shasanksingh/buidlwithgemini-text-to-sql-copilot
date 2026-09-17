# My agent: Enterprise Text-to-SQL Copilot

One-liner: An enterprise multi-agent Text-to-SQL copilot that converts natural language business questions into verified BigQuery queries using schema RAG documents, entity key mappings, and multi-agent validation.

## Architecture & Multi-Agent Workflow

1. **Intent Agent**
   - Parses the user's natural language question.
   - Identifies business domain, intent, filters, time ranges, and target metrics.

2. **Schema Validation Agent**
   - Queries Vertex AI RAG Engine for table schemas, data dictionary docs, and primary/foreign key mappings.
   - Verifies column compatibility, join paths, and business logic definitions.

3. **Query Generation Agent**
   - Synthesizes dialect-correct BigQuery SQL (handling `DATE_TRUNC`, `SAFE_CAST`, nested JSON/STRUCTs, etc.).
   - Applies schema rules, join conditions, and optimized CTE structures.

4. **Confidence Score & Verification Agent**
   - Runs BigQuery `DRY_RUN` to validate SQL syntax and estimate bytes scanned/cost.
   - Computes a confidence score (0-100%) based on schema match, syntax validity, and join safety.
   - Triggers reflection/correction loop back to Query Generation if confidence is below threshold.

---

## Tool Coverage

- **Memory**: Remembers user query history, preferred BigQuery datasets, custom domain glossary/acronyms, and favorite query templates across sessions.
- **Tools**:
  - `search_schema_rag`: Retrieves schema documentation and entity key mappings from Vertex AI RAG Engine.
  - `fetch_table_metadata`: Fetches live BigQuery dataset schemas and column types.
  - `validate_sql_dryrun`: Performs BigQuery dry-run validation and estimates scan size.
- **Catalog/UI**: Renders schema table/column mapping cards, highlighted SQL preview, and dry-run query cost breakdown cards (A2UI).
- **Image gen**: Renders visual ER diagrams / join graph diagrams for complex multi-table queries.
- **Sandbox**: Computes query complexity scores and analyzes execution plan metrics.

---

## Core Rails & Stretch Menu

- **Core Rails**: Memory Bank, RAG Engine, Function Tools, Evaluation Suite, Agent Runtime Deployment, A2UI Frontend.
- **Stretch Menu**: A2UI query execution cards, automated dry-run cost warnings, ER diagram generation.
- **First Eval Question**: "Find the top 10 customers by total revenue in Q3 2026, joining `sales_orders` and `customer_profiles` using customer_id mapping."
