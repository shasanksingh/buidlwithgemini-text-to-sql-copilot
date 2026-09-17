# Enterprise Text-to-SQL Copilot

> **Enterprise SQL Copilot for planned, governed, and explainable text-to-SQL.**

SQL Copilot turns complex business questions into schema-grounded, read-only SQL queries through multi-agent planning, Vertex AI Agent Runtime orchestration, Spider dataset grounding, Firestore governance cataloging, live currency conversions, and public Cloud Storage exports.

---

## 🌟 Key Architecture & Features

1. **Multi-Agent Governance & SQL Planning Pipeline**:
   - **Intent & Schema Validation Agent**: Validates queries against enterprise schema mapping (`clients`, `sales_orders`, `projects`, `customer_profiles`).
   - **Spider Text-to-SQL Grounding Engine**: Grounded on Spider dataset benchmark (`spider_text_sql.csv`) for complex SQL joins and aggregation patterns.
   - **Read-Only Safety Guardrail**: Rejects `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, or `TRUNCATE` operations before query execution.
   - **Deterministic Confidence Scoring**: Evaluates schema coverage, join validity, and query safety.

2. **Vertex AI Memory Bank**:
   - Integrated with Vertex AI Memory Bank for long-term user session history, state preservation, and contextual query recall across turns.

3. **Firestore Database Integration**:
   - Collection: `schema_requests` on Project `qwiklabs-gcp-02-c95bba962a8e`.
   - Function tools (`get_pending_schema_requests`, `submit_schema_request`) allow users to query and log schema extension requests.

4. **Cloud Storage Query Artifact Export**:
   - Function tool (`export_query_to_cloud_storage`) formats and uploads `.sql` query files to public GCS bucket `text-to-sql-copilot-public-c95bba96`.

5. **Financial & Currency Exchange Rates**:
   - Function tool (`get_currency_exchange_rates`) fetches live European Central Bank exchange rates via Frankfurter API for multi-currency revenue conversions (USD, EUR, GBP, JPY).

6. **Cloud Run Enterprise UI Proxy**:
   - FastAPI containerized frontend providing an interactive dark-mode workspace with 3 clickable enterprise prompt templates.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Google Cloud SDK (`gcloud`) initialized with project `qwiklabs-gcp-02-c95bba962a8e`

### Installation
```bash
# Clone repository
git clone https://github.com/your-username/text-to-sql-copilot.git
cd text-to-sql-copilot

# Create virtual environment and sync dependencies
uv venv
uv sync
```

### Running Locally

1. **Test Agent Locally**:
   ```bash
   uv run python app/agent.py
   ```

2. **Run Frontend Proxy Locally**:
   ```bash
   cd frontend
   export AGENT_ENGINE_RESOURCE_NAME="projects/1057696110870/locations/us-east1/reasoningEngines/8532795171727736832"
   python main.py
   ```
   Open `http://localhost:8080` in your browser.

---

## 🚢 Deployment

### Deploy Agent to Vertex AI Agent Runtime
```bash
agents-cli deploy --target agent_runtime
```

### Deploy Frontend Proxy to Cloud Run
```bash
gcloud run deploy text-to-sql-copilot-frontend \
  --source ./frontend \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars="AGENT_ENGINE_RESOURCE_NAME=projects/1057696110870/locations/us-east1/reasoningEngines/8532795171727736832,AGENT_DIRECTORY=app" \
  --project=qwiklabs-gcp-02-c95bba962a8e
```

---

## 🛠 Project Structure

```
text-to-sql-copilot/
├── app/
│   └── agent.py                  # Vertex AI Agent definition & function tools
├── frontend/
│   ├── main.py                   # FastAPI proxy server
│   ├── requirements.txt          # Frontend dependencies
│   ├── Dockerfile                # Cloud Run container definition
│   └── static/
│       └── index.html            # Enterprise SQL Copilot chat interface
├── data/
│   └── spider_text_sql.csv       # Spider dataset benchmark grounding
├── scripts/
│   └── seed_firestore.py         # Seed script for Firestore schema_requests
├── agents-cli-manifest.yaml     # Agents CLI project deployment manifest
├── pyproject.toml               # Python package configuration
└── README.md                    # Project documentation
```
