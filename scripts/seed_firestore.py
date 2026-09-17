#!/usr/bin/env python3
"""Seed script for full enterprise Text-to-SQL Copilot Firestore collections."""

import csv
import datetime
import os
from google.cloud import firestore
from google.api_core import exceptions

# CRITICAL: Hardcode GCP project ID as string for Firestore client
PROJECT_ID = "qwiklabs-gcp-02-c95bba962a8e"


def seed_firestore():
    print(f"Connecting to Firestore for project: {PROJECT_ID}")
    try:
        db = firestore.Client(project=PROJECT_ID)

        # 1. Full Enterprise Schema Catalog
        schema_catalog = [
            {
                "id": "clients",
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
                "id": "projects",
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
                "id": "invoices",
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
                "id": "payments",
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
                "id": "employees",
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
                "id": "tasks",
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
                "id": "time_logs",
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
                "id": "customer_feedback",
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
        ]

        print("Seeding full 'schema_catalog' collection...")
        for item in schema_catalog:
            doc_id = item["id"]
            db.collection("schema_catalog").document(doc_id).set(item)
            print(f"  - Seeded schema table: {doc_id}")

        # 2. Seed Spider SQL Patterns Collection
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "spider_text_sql.csv")
        if os.path.exists(csv_path):
            print("Seeding 'spider_patterns' collection from spider_text_sql.csv...")
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    doc_id = f"pattern_{idx+1:03d}"
                    db.collection("spider_patterns").document(doc_id).set(row)
                    print(f"  - Seeded Spider pattern: {doc_id}")

        print("Firestore seeding completed successfully!")
    except exceptions.NotFound:
        print(f"Firestore database (default) not found for project '{PROJECT_ID}'. Please enable Firestore in GCP Console.")
    except Exception as e:
        print(f"Firestore seed note ({type(e).__name__}): {e}")


if __name__ == "__main__":
    seed_firestore()
