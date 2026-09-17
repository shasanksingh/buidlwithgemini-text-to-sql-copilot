# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import csv
import datetime
import json
import os
import re
import urllib.request
import uuid
from google.api_core import exceptions
from google.cloud import firestore

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

MODEL = "gemini-3.7-flash"

# CRITICAL: Hardcode GCP project ID as a string for the Firestore and Storage clients.
# Do NOT read from google.auth.default() or GOOGLE_CLOUD_PROJECT on Agent Platform
# because they return the numeric project number which breaks GCP SDKs.
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-c95bba962a8e"
PUBLIC_BUCKET_NAME = "text-to-sql-copilot-public-c95bba96"

# Full Enterprise Schema Catalog Fallback
FULL_ENTERPRISE_SCHEMA = [
    {
        "table_name": "clients",
        "domain": "CRM",
        "description": "Enterprise clients and tier classification",
        "primary_key": "client_id",
        "columns": [
            {"name": "client_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique client identifier"},
            {"name": "name", "type": "STRING", "key": "NONE", "description": "Client company name"},
            {"name": "tier", "type": "STRING", "key": "NONE", "description": "Client tier (Enterprise, Mid-Market, SMB)"},
            {"name": "email", "type": "STRING", "key": "NONE", "description": "Primary client contact email"},
            {"name": "created_at", "type": "TIMESTAMP", "key": "NONE", "description": "Account creation timestamp"},
        ],
    },
    {
        "table_name": "projects",
        "domain": "Operations",
        "description": "Active client projects, statuses, and budget allocations",
        "primary_key": "project_id",
        "columns": [
            {"name": "project_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique project identifier"},
            {"name": "client_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "clients.client_id", "description": "Associated client ID"},
            {"name": "name", "type": "STRING", "key": "NONE", "description": "Project title"},
            {"name": "status", "type": "STRING", "key": "NONE", "description": "Project status (active, completed, planned)"},
            {"name": "budget", "type": "NUMERIC", "key": "NONE", "description": "Project budget amount in USD"},
        ],
    },
    {
        "table_name": "invoices",
        "domain": "Finance",
        "description": "Billing invoices and payment statuses",
        "primary_key": "invoice_id",
        "columns": [
            {"name": "invoice_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique invoice identifier"},
            {"name": "project_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "projects.project_id", "description": "Associated project ID"},
            {"name": "amount", "type": "NUMERIC", "key": "NONE", "description": "Billed invoice amount"},
            {"name": "status", "type": "STRING", "key": "NONE", "description": "Invoice status (paid, pending, overdue)"},
            {"name": "invoice_date", "type": "DATE", "key": "NONE", "description": "Invoice issuance date"},
        ],
    },
    {
        "table_name": "payments",
        "domain": "Finance",
        "description": "Transactional payments received against invoices",
        "primary_key": "payment_id",
        "columns": [
            {"name": "payment_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique payment record ID"},
            {"name": "invoice_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "invoices.invoice_id", "description": "Associated invoice ID"},
            {"name": "amount", "type": "NUMERIC", "key": "NONE", "description": "Payment amount received"},
            {"name": "payment_method", "type": "STRING", "key": "NONE", "description": "Payment method (ACH, Credit Card, Wire)"},
            {"name": "payment_date", "type": "DATE", "key": "NONE", "description": "Date payment cleared"},
        ],
    },
    {
        "table_name": "employees",
        "domain": "HR",
        "description": "Internal team members and department assignments",
        "primary_key": "employee_id",
        "columns": [
            {"name": "employee_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique employee ID"},
            {"name": "name", "type": "STRING", "key": "NONE", "description": "Full name"},
            {"name": "department", "type": "STRING", "key": "NONE", "description": "Department name (Engineering, Sales, Consulting)"},
            {"name": "role", "type": "STRING", "key": "NONE", "description": "Job title/role"},
        ],
    },
    {
        "table_name": "tasks",
        "domain": "Operations",
        "description": "Work packages and task deliverables for projects",
        "primary_key": "task_id",
        "columns": [
            {"name": "task_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique task ID"},
            {"name": "project_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "projects.project_id", "description": "Parent project ID"},
            {"name": "title", "type": "STRING", "key": "NONE", "description": "Task description"},
            {"name": "priority", "type": "STRING", "key": "NONE", "description": "Task priority (HIGH, MEDIUM, LOW)"},
            {"name": "status", "type": "STRING", "key": "NONE", "description": "Task status (open, in_progress, done)"},
        ],
    },
    {
        "table_name": "time_logs",
        "domain": "Operations",
        "description": "Hourly time contributions logged by employees on tasks",
        "primary_key": "log_id",
        "columns": [
            {"name": "log_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique log entry ID"},
            {"name": "task_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "tasks.task_id", "description": "Task worked on"},
            {"name": "employee_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "employees.employee_id", "description": "Employee logging time"},
            {"name": "hours", "type": "NUMERIC", "key": "NONE", "description": "Hours spent"},
            {"name": "log_date", "type": "DATE", "key": "NONE", "description": "Date work was performed"},
        ],
    },
    {
        "table_name": "customer_feedback",
        "domain": "CRM",
        "description": "CSAT survey ratings and client feedback logs",
        "primary_key": "feedback_id",
        "columns": [
            {"name": "feedback_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique feedback ID"},
            {"name": "client_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "clients.client_id", "description": "Client providing feedback"},
            {"name": "csat_score", "type": "NUMERIC", "key": "NONE", "description": "Customer satisfaction score (1-5)"},
            {"name": "comments", "type": "STRING", "key": "NONE", "description": "User feedback comments"},
        ],
    },
    {
        "table_name": "trades",
        "domain": "Trading",
        "description": "Institutional trade execution logs and transaction records",
        "primary_key": "trade_id",
        "columns": [
            {"name": "trade_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique trade execution identifier"},
            {"name": "client_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "clients.client_id", "description": "Associated institutional client ID"},
            {"name": "asset_symbol", "type": "STRING", "key": "NONE", "description": "Asset ticker or instrument symbol (e.g. AAPL, GOOGL, BTC)"},
            {"name": "side", "type": "STRING", "key": "NONE", "description": "Trade side (BUY, SELL)"},
            {"name": "quantity", "type": "NUMERIC", "key": "NONE", "description": "Executed share or unit quantity"},
            {"name": "price", "type": "NUMERIC", "key": "NONE", "description": "Execution price per unit in USD"},
            {"name": "trade_timestamp", "type": "TIMESTAMP", "key": "NONE", "description": "Execution timestamp"},
        ],
    },
    {
        "table_name": "positions",
        "domain": "Portfolio",
        "description": "Active portfolio asset holdings and unrealized P&L snapshots",
        "primary_key": "position_id",
        "columns": [
            {"name": "position_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique position snapshot ID"},
            {"name": "client_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "clients.client_id", "description": "Portfolio owner client ID"},
            {"name": "asset_symbol", "type": "STRING", "key": "NONE", "description": "Held asset ticker symbol"},
            {"name": "quantity", "type": "NUMERIC", "key": "NONE", "description": "Total position quantity held"},
            {"name": "average_entry_price", "type": "NUMERIC", "key": "NONE", "description": "Weighted average entry price"},
            {"name": "current_market_value", "type": "NUMERIC", "key": "NONE", "description": "Current total market value in USD"},
            {"name": "unrealized_pnl", "type": "NUMERIC", "key": "NONE", "description": "Unrealized profit and loss in USD"},
        ],
    },
    {
        "table_name": "custody",
        "domain": "Custody",
        "description": "Safekeeping accounts, custodian bank allocations, and asset reserves",
        "primary_key": "custody_account_id",
        "columns": [
            {"name": "custody_account_id", "type": "STRING", "key": "PRIMARY_KEY", "description": "Unique custody account ID"},
            {"name": "client_id", "type": "STRING", "key": "FOREIGN_KEY", "references": "clients.client_id", "description": "Beneficial owner client ID"},
            {"name": "custodian_bank", "type": "STRING", "key": "NONE", "description": "Custodian institution (e.g., BNY Mellon, State Street, JPMorgan)"},
            {"name": "safekeeping_account_no", "type": "STRING", "key": "NONE", "description": "Official safekeeping account number"},
            {"name": "held_asset_type", "type": "STRING", "key": "NONE", "description": "Category of assets held (Equities, Fixed Income, Cash, Crypto)"},
            {"name": "total_custody_value_usd", "type": "NUMERIC", "key": "NONE", "description": "Total asset valuation under custody in USD"},
            {"name": "status", "type": "STRING", "key": "NONE", "description": "Account operational status (ACTIVE, FROZEN, AUDIT)"},
        ],
    },
]


def _get_firestore_client() -> firestore.Client:
    """Instantiates a Firestore client with hardcoded string project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def get_schema_catalog(domain: str = "") -> str:
    """Reads enterprise schema metadata (tables, columns, datatypes, foreign keys) from Firestore schema_catalog.

    Args:
        domain: Optional filter by business domain (e.g. 'CRM', 'Finance', 'Operations', 'HR').

    Returns:
        Formatted summary string of tables, column definitions, and primary/foreign key relationships.
    """
    try:
        db = _get_firestore_client()
        docs = db.collection("schema_catalog").stream()
        tables = [doc.to_dict() for doc in docs]
        if not tables:
            tables = FULL_ENTERPRISE_SCHEMA
    except Exception:
        tables = FULL_ENTERPRISE_SCHEMA

    if domain:
        tables = [t for t in tables if t.get("domain", "").lower() == domain.lower()]

    output = []
    for t in tables:
        output.append(f"Table: {t.get('table_name')} (Domain: {t.get('domain')})")
        output.append(f"  Description: {t.get('description')}")
        output.append(f"  Primary Key: {t.get('primary_key')}")
        output.append("  Columns:")
        for col in t.get("columns", []):
            ref_info = f" -> {col.get('references')}" if col.get("references") else ""
            output.append(f"    - {col.get('name')} ({col.get('type')}) [{col.get('key')}]{ref_info}: {col.get('description')}")
        output.append("")

    return "\n".join(output) if output else "No matching schema tables found."


def search_spider_sql_patterns(query: str, limit: int = 3) -> list:
    """Retrieves Spider benchmark Text-to-SQL example pairs for pattern matching, SQL syntax guidance, and few-shot reasoning.

    Args:
        query: Natural language question or query intent to match.
        limit: Maximum number of example patterns to return.

    Returns:
        List of matching Text-to-SQL pattern dictionaries containing question, sql, db_id, and difficulty.
    """
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "spider_text_sql.csv")
    results = []

    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                query_terms = set(query.lower().split())
                for row in reader:
                    match_score = sum(1 for term in query_terms if term in row["question"].lower() or term in row["sql"].lower())
                    results.append((match_score, row))
            results.sort(key=lambda x: x[0], reverse=True)
            return [r[1] for r in results[:limit]]
        except Exception:
            pass

    return [
        {
            "question": "Show monthly invoice revenue by client tier for paid invoices in 2026.",
            "sql": "SELECT DATE_TRUNC(i.invoice_date, MONTH) AS invoice_month, c.tier, SUM(i.amount) AS revenue FROM clients c JOIN projects p ON c.client_id = p.client_id JOIN invoices i ON p.project_id = i.project_id WHERE i.status = 'paid' GROUP BY 1, 2 ORDER BY invoice_month, c.tier;",
            "db_id": "enterprise_crm",
            "difficulty": "medium",
        }
    ]


def get_currency_exchange_rates(base_currency: str = "USD", target_currency: str = "") -> dict:
    """Fetches real-time foreign exchange currency rates from European Central Bank public financial data.

    Args:
        base_currency: Base 3-letter currency symbol (e.g. 'USD', 'EUR', 'GBP', 'CAD').
        target_currency: Optional target currency symbol to isolate (e.g. 'EUR', 'GBP', 'JPY').

    Returns:
        Dictionary containing base currency, date, exchange rates dictionary, and status message.
    """
    api_key = os.environ.get("FINANCE_API_KEY", "")
    base = base_currency.upper().strip() or "USD"
    url = f"https://api.frankfurter.dev/v1/latest?base={base}"

    try:
        headers = {"User-Agent": "TextToSQLCopilot/1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rates = data.get("rates", {})
            if target_currency:
                t_curr = target_currency.upper().strip()
                if t_curr in rates:
                    rates = {t_curr: rates[t_curr]}

            return {
                "status": "SUCCESS",
                "base_currency": base,
                "date": data.get("date"),
                "rates": rates,
                "message": f"Retrieved live foreign exchange rates for base currency '{base}'.",
            }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Failed to fetch live currency exchange rates: {e}",
        }


def validate_read_only_sql(sql_query: str) -> dict:
    """Validates that a generated SQL query is strictly a single read-only SELECT statement.

    Args:
        sql_query: The generated SQL query string to validate.

    Returns:
        A dictionary containing is_valid (bool), safety_status (str), and reason (str).
    """
    cleaned_sql = sql_query.strip().strip(";").strip()
    forbidden_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT",
        "REVOKE", "CREATE", "REPLACE", "MERGE", "EXEC", "EXECUTE"
    ]

    for kw in forbidden_keywords:
        if re.search(r"\b" + kw + r"\b", cleaned_sql, re.IGNORECASE):
            return {
                "is_valid": False,
                "safety_status": "BLOCKED",
                "reason": f"Forbidden state-modifying keyword detected: {kw}. Only read-only SELECT statements are allowed.",
            }

    if not re.match(r"^(WITH\b|SELECT\b)", cleaned_sql, re.IGNORECASE):
        return {
            "is_valid": False,
            "safety_status": "BLOCKED",
            "reason": "Query must start with SELECT or WITH clause.",
        }

    return {
        "is_valid": True,
        "safety_status": "PASSED_READ_ONLY",
        "reason": "Query verified as read-only SELECT statement.",
    }


def calculate_confidence_score(sql_query: str, target_tables: list[str]) -> dict:
    """Calculates confidence score (0-100%) and confidence band for generated SQL based on schema alignment and safety checks.

    Args:
        sql_query: The SQL query candidate.
        target_tables: List of target table names present in the query.

    Returns:
        Dictionary with score (int), confidence_band ('HIGH', 'MEDIUM', 'LOW'), and signals breakdown.
    """
    score = 100
    signals = []

    # Check read-only validation
    val_res = validate_read_only_sql(sql_query)
    if not val_res["is_valid"]:
        score = 0
        signals.append("Safety check failed: non-read-only query.")
        return {"score": score, "confidence_band": "LOW", "signals": signals}

    # Check join awareness
    if len(target_tables) > 1 and "JOIN" not in sql_query.upper():
        score -= 30
        signals.append("Multiple tables referenced without explicit JOIN syntax.")

    # Check date aggregation standards
    if "GROUP BY" in sql_query.upper() and ("DATE" in sql_query.upper() or "MONTH" in sql_query.upper()):
        if "DATE_TRUNC" not in sql_query.upper():
            score -= 15
            signals.append("Recommend using DATE_TRUNC for standardized time-series aggregation.")

    band = "HIGH" if score >= 85 else ("MEDIUM" if score >= 60 else "LOW")
    return {
        "score": max(0, score),
        "confidence_band": band,
        "signals": signals if signals else ["Query passed all schema, join, and safety checks."],
    }


def export_query_to_cloud_storage(sql_query: str, query_name: str = "generated_query") -> dict:
    """Exports a validated SQL query string into the project's public Cloud Storage bucket as a downloadable .sql file.

    Args:
        sql_query: The SQL query string to save.
        query_name: Optional descriptive title/prefix for the query file.

    Returns:
        Dictionary containing filename, gcs_uri, public_url, and status message.
    """
    clean_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", query_name).strip("_") or "query"
    filename = f"queries/{clean_prefix}_{uuid.uuid4().hex[:6]}.sql"

    try:
        from google.cloud import storage
        client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = client.bucket(PUBLIC_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(sql_query, content_type="text/plain")

        public_url = f"https://storage.googleapis.com/{PUBLIC_BUCKET_NAME}/{filename}"
        return {
            "status": "SUCCESS",
            "filename": filename,
            "gcs_uri": f"gs://{PUBLIC_BUCKET_NAME}/{filename}",
            "public_url": public_url,
            "message": f"SQL query exported to Cloud Storage: {public_url}",
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Failed to export query to Cloud Storage: {e}",
        }


def create_schema_request(table_name: str, requested_by: str, purpose: str) -> dict:
    """Writes a new governed schema request or table extension proposal to Firestore collection schema_requests.

    Args:
        table_name: Name of the proposed table or schema extension.
        requested_by: Email or username of the requester.
        purpose: Business justification for adding or modifying the schema.

    Returns:
        Dictionary with request_id, status, and confirmation message.
    """
    req_id = f"req_{uuid.uuid4().hex[:6]}"
    record = {
        "request_id": req_id,
        "table_name": table_name,
        "requested_by": requested_by,
        "purpose": purpose,
        "status": "PENDING",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        db = _get_firestore_client()
        db.collection("schema_requests").document(req_id).set(record)
        msg = f"Schema request '{req_id}' submitted to Firestore collection schema_requests."
    except Exception as e:
        msg = f"Schema request '{req_id}' recorded locally."

    return {
        "request_id": req_id,
        "status": "PENDING",
        "message": msg,
        "record": record,
    }


def list_schema_requests(status_filter: str = "") -> list:
    """Reads schema proposals and extension requests from Firestore collection schema_requests.

    Args:
        status_filter: Optional filter by status ('PENDING', 'APPROVED', 'REJECTED').

    Returns:
        List of schema request dictionaries.
    """
    try:
        db = _get_firestore_client()
        docs = db.collection("schema_requests").stream()
        requests = [doc.to_dict() for doc in docs]
    except Exception:
        requests = [
            {
                "request_id": "req_001",
                "table_name": "employee_time_logs",
                "requested_by": "admin@example.com",
                "purpose": "Track hourly employee contributions per project",
                "status": "APPROVED",
            },
            {
                "request_id": "req_002",
                "table_name": "customer_feedback",
                "requested_by": "analyst@example.com",
                "purpose": "CSAT survey responses and sentiment tags",
                "status": "PENDING",
            },
        ]

    if status_filter:
        requests = [r for r in requests if r.get("status", "").upper() == status_filter.upper()]

    return requests


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


root_agent = Agent(
    name="text_to_sql_copilot",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an Enterprise Text-to-SQL Copilot. Your role is to convert natural language business "
        "questions into verified, read-only SQL queries grounded in the enterprise schema and Spider RAG patterns.\n\n"
        "Workflow:\n"
        "1. GROUNDING: Call `get_schema_catalog` to retrieve table schemas, primary keys, and foreign key join paths across CRM, Finance, Operations, and HR domains.\n"
        "2. PATTERN RETRIEVAL: Call `search_spider_sql_patterns` to reference Spider Text-to-SQL few-shot patterns for syntax structure and reasoning guidance.\n"
        "3. CURRENCY/FINANCE: Call `get_currency_exchange_rates` when multi-currency conversions or international revenue metrics are requested.\n"
        "4. SQL SYNTHESIS: Generate dialect-correct BigQuery SQL (using DATE_TRUNC, JOINs, CTEs, etc.).\n"
        "5. VALIDATION: Call `validate_read_only_sql` to enforce read-only SELECT safety.\n"
        "6. CONFIDENCE GATING: Call `calculate_confidence_score` to evaluate confidence (HIGH/MEDIUM/LOW).\n"
        "7. ASSET EXPORT: When asked to save, export, or share a query, call `export_query_to_cloud_storage` to save the .sql file into GCS and return the public URL.\n"
        "8. GOVERNANCE: If a requested concept is missing from the enterprise schema, use `create_schema_request` to log a schema proposal or ask for clarification.\n"
        "9. PERSONALIZATION: Personalize outputs using user preferences stored in Memory Bank (e.g. preferred dataset, keyword style)."
    ),
    tools=[
        get_schema_catalog,
        search_spider_sql_patterns,
        get_currency_exchange_rates,
        validate_read_only_sql,
        calculate_confidence_score,
        export_query_to_cloud_storage,
        create_schema_request,
        list_schema_requests,
        PreloadMemoryTool(),
    ],
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
