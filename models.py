from google.cloud import bigquery, storage
from google.api_core.exceptions import NotFound
import os
import uuid
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_ID = os.getenv("DATASET_ID")
TABLE_ID = os.getenv("TABLE_ID")
FULL_TABLE_ID = os.getenv("FULL_TABLE_ID")

BUCKET_NAME = os.getenv("BUCKET_NAME")

REPORT_BUCKET_NAME = os.getenv("REPORT_BUCKET_NAME")


def create_bigquery_dataset():
    """Create the BigQuery dataset if it doesn't exist."""
    client = bigquery.Client()
    try:
        client.get_dataset(DATASET_ID)
        print(f"Dataset {DATASET_ID} already exists.")
    except NotFound:
        dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
        dataset.location = "US"
        client.create_dataset(dataset, timeout=30)
        print(f"Created dataset {DATASET_ID}.")

def create_bigquery_table():
    """Create the BigQuery table if it doesn't exist."""
    client = bigquery.Client()
    schema = [
        bigquery.SchemaField("id", "INTEGER"),
        bigquery.SchemaField("Merchant Name", "STRING"),
        bigquery.SchemaField("Transaction Date", "DATETIME"),
        bigquery.SchemaField("Number of Items", "INTEGER"),
        bigquery.SchemaField("Category", "STRING"),
        bigquery.SchemaField("Total", "FLOAT"),
        bigquery.SchemaField("Receipt URL", "STRING"),
        bigquery.SchemaField("User Email", "STRING"),
    ]

    try:
        client.get_table(FULL_TABLE_ID)
        print(f"Table {FULL_TABLE_ID} already exists.")
    except NotFound:
        table = bigquery.Table(FULL_TABLE_ID, schema=schema)
        client.create_table(table)
        print(f"Created table {FULL_TABLE_ID}.")

def get_next_id():
    """Get the next available integer ID for the BigQuery table."""
    client = bigquery.Client()
    query = f"SELECT MAX(id) AS max_id FROM `{FULL_TABLE_ID}`"
    query_job = client.query(query)
    result = query_job.result()
    max_id = next(result).max_id
    return (max_id or 0) + 1

def insert_into_bigquery(receipt_data):
    """Insert a receipt record into BigQuery."""
    client = bigquery.Client()
    next_id = get_next_id()

    rows_to_insert = [
        {
            "id": next_id,
            "Merchant Name": receipt_data["Merchant Name"],
            "Transaction Date": receipt_data["Transaction Date"].strftime("%Y-%m-%d %H:%M:%S")
            if receipt_data["Transaction Date"] != "N/A" else None,
            "Number of Items": receipt_data["Number of Items"],
            "Category": receipt_data["Category"],
            "Total": float(receipt_data["Total"]) if receipt_data["Total"] != "N/A" else None,
            "Receipt URL": receipt_data["Receipt URL"],
            "User Email": receipt_data["User Email"],
        }
    ]
    errors = client.insert_rows_json(FULL_TABLE_ID, rows_to_insert)
    if errors:
        print(f"Encountered errors while inserting rows: {errors}")

def upload_to_bucket(file, destination_blob_name):
    """Uploads a file to the Google Cloud Storage bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_file(file)
    public_url = blob.public_url
    print(f"File {destination_blob_name} uploaded to {BUCKET_NAME}. Public URL: {public_url}")
    return public_url

def delete_receipt_from_bigquery(receipt_id):
    client = bigquery.Client()

    query = f"""
        DELETE FROM `{FULL_TABLE_ID}`
        WHERE id = @receipt_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("receipt_id", "INT64", receipt_id)
        ]
    )

    client.query(query, job_config=job_config).result()
