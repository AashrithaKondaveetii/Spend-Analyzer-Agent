from flask import Flask, render_template, request, redirect, url_for, session
from requests_oauthlib import OAuth2Session
from callback import Callback
from logout import Logout
from oauth_config import client_id, authorization_base_url, redirect_callback
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from datetime import datetime, date
import matplotlib.pyplot as plt
from io import BytesIO
from dotenv import load_dotenv
from google.cloud import bigquery, storage
from models import create_bigquery_dataset, create_bigquery_table, insert_into_bigquery, upload_to_bucket, BUCKET_NAME,PROJECT_ID, DATASET_ID, TABLE_ID, FULL_TABLE_ID
import os

from agent.ocr_agent import OcrExtractionAgent
from agent.categorization_agent import CategorizationValidationAgent
from agent.orchestrator_agent import OrchestrationAgent
from observability.logging_config import setup_logging
from models import REPORT_BUCKET_NAME
from agent.adk_expense_agent import run_expense_query

load_dotenv()
app = Flask(__name__)

app.secret_key = os.urandom(24)

# Configure logging for the whole app
setup_logging()


client_id = os.environ.get("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")
redirect_callback = os.environ.get("REDIRECT_CALLBACK")
authorization_base_url = os.environ.get("AUTHORIZATION_BASE_URL", "https://accounts.google.com/o/oauth2/auth")
token_url = os.environ.get("TOKEN_URL", "https://accounts.google.com/o/oauth2/token")

report_bucket_name = os.environ.get("REPORT_BUCKET_NAME")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

endpoint = os.environ.get("AZURE_FORM_RECOGNIZER_ENDPOINT")
key = os.environ.get("AZURE_FORM_RECOGNIZER_KEY")

document_analysis_client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))


ocr_agent = OcrExtractionAgent(document_analysis_client)
categorization_agent = CategorizationValidationAgent()
orchestrator_agent = OrchestrationAgent(ocr_agent, categorization_agent)

@app.route('/', methods=['GET', 'POST'])
def index():
    answer = None

    if request.method == "POST":
        if "user_email" not in session:
            return redirect(url_for('login'))

        user_email = session["user_email"]

        # create session_id if missing
        if "session_id" not in session:
            import uuid
            session["session_id"] = str(uuid.uuid4())

        session_id = session["session_id"]
        user_message = request.form.get("message", "")

        if user_message:
            answer = run_expense_query(
                user_id=user_email,
                session_id=session_id,
                text=user_message
            )

    return render_template(
        'index.html',
        answer=answer
    )

@app.route('/login')
def login():
    """Initiates the OAuth flow."""
    google = OAuth2Session(client_id, redirect_uri=redirect_callback, scope=[
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ])
    authorization_url, state = google.authorization_url(authorization_base_url, prompt='login')
    session['oauth_state'] = state
    return redirect(authorization_url)


@app.route('/upload', methods=['GET', 'POST'])
def upload_receipt():
    """Restrict receipt upload to logged-in users."""
    if 'oauth_token' not in session:
        return redirect(url_for('login'))

    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session.get('user_email')

    if request.method == 'POST':
        if 'receipt_image' not in request.files:
            return render_template('upload_receipt.html', error="No file selected.")

        file = request.files['receipt_image']

        if file.filename == '':
            return render_template('upload_receipt.html', error="No file selected.")

        # === NEW MULTI-AGENT PIPELINE CALL ===
        destination_blob_name = f"uploads/{file.filename}"

        receipt_details, error = orchestrator_agent.process_receipt(
            file_obj=file,
            user_email=user_email,
            flask_session=session,
            destination_blob_name=destination_blob_name
        )

        if error:
            return render_template('upload_receipt.html', error=error)

        # Same as before — results.html stays unchanged
        return render_template('results.html', receipts=receipt_details)

    return render_template('upload_receipt.html')


@app.route('/view_receipts')
def view_receipts():
    """Restrict receipt viewing to logged-in users."""
    if 'oauth_token' not in session:
        return redirect(url_for('login'))
    """View all stored receipts from BigQuery."""
    if 'userinfo' not in session:
        return redirect(url_for('login'))

    user_email = session['userinfo']['email']
    client = bigquery.Client()
    query = f"""
        SELECT
            id,
            `Merchant Name` AS merchant_name,
            `Transaction Date` AS transaction_date,
            `Number of Items` AS num_items,
            `Category` AS category,
            `Total` AS total,
            `Receipt URL` AS receipt_url
        FROM `{FULL_TABLE_ID}`
        WHERE `User Email` = @user_email
        ORDER BY id ASC
    """
    query_job = client.query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("user_email", "STRING", user_email)]
    ))
    receipts = query_job.result()

    receipt_list = []
    for row in receipts:
        receipt_list.append({
            "id": row.id,
            "merchant_name": row.merchant_name,
            "transaction_date": row.transaction_date,
            "num_items": row.num_items,
            "category": row.category,
            "total": row.total,
            "receipt_url": row.receipt_url
        })

    return render_template('view_receipts.html', receipts=receipt_list)

@app.route('/delete_receipt/<int:receipt_id>', methods=['POST'])
def delete_receipt(receipt_id):
    if 'oauth_token' not in session:
        return redirect(url_for('login'))

    from models import delete_receipt_from_bigquery

    try:
        delete_receipt_from_bigquery(receipt_id)
    except Exception as e:
        print("Error deleting receipt:", e)

    return redirect('/view_receipts')




app.add_url_rule('/callback',
                 view_func=Callback.as_view('callback'),
                 methods=["GET"])

app.add_url_rule('/logout',
                 view_func=Logout.as_view('logout'),
                 methods=["GET"])


@app.route('/generate_report')
def generate_report():
    """Generate store-wise total purchase report and monthly expense report for logged-in user."""
    user_email = session.get('user_email')
    if not user_email:
        return redirect(url_for('login'))

    client = bigquery.Client()
    

    store_query = f"""
        SELECT 
            LOWER(`Merchant Name`) AS normalized_store, 
            SUM(Total) AS total_purchase 
        FROM `{FULL_TABLE_ID}`
        WHERE Total IS NOT NULL AND `User Email` = '{user_email}'
        GROUP BY normalized_store
        ORDER BY total_purchase DESC
        LIMIT 5
    """
    store_query_job = client.query(store_query)
    store_results = store_query_job.result()
    

    store_labels = []
    store_values = []
    for row in store_results:
        store_labels.append(f"{row.normalized_store.capitalize()} (${row.total_purchase:.2f})")
        store_values.append(row.total_purchase)

    if not store_labels or not store_values:
        return render_template('report.html', pie_chart_url=None, line_chart_url=None, error="No data available to generate the report.")

    from io import BytesIO
    import matplotlib.pyplot as plt

    pie_buffer = BytesIO()
    plt.figure(figsize=(8, 8))
    wedges, texts, autotexts = plt.pie(
        store_values,
        labels=store_labels,
        autopct='%1.1f%%',
        startangle=140,
        textprops={'fontsize': 10}
    )
    plt.title("Top 5 Store-Wise Total Purchases", fontsize=14)
    plt.tight_layout()
    plt.savefig(pie_buffer, format='png')
    plt.close()
    pie_buffer.seek(0)

    pie_blob_name = f"report_pie_chart_{user_email}.png"
    pie_bucket = storage.Client().bucket(report_bucket_name)
    pie_blob = pie_bucket.blob(pie_blob_name)
    pie_blob.upload_from_file(pie_buffer, content_type='image/png')
    pie_chart_url = pie_blob.generate_signed_url(expiration=3600*24*7)
    # pie_chart_url = pie_blob.public_url

    monthly_query = f"""
        SELECT 
            FORMAT_TIMESTAMP('%Y-%m', `Transaction Date`) AS month,
            SUM(Total) AS monthly_total
        FROM `{FULL_TABLE_ID}`
        WHERE Total IS NOT NULL AND `User Email` = '{user_email}'
        GROUP BY month
        ORDER BY month
    """
    monthly_query_job = client.query(monthly_query)
    monthly_results = monthly_query_job.result()

    months = []
    totals = []
    for row in monthly_results:
        if not row.month:   # skip None, empty, invalid values
            continue
        months.append(row.month)
        totals.append(row.monthly_total)

    if not months or not totals:
        return render_template('report.html', pie_chart_url=pie_chart_url, line_chart_url=None, error="No data available for monthly expenses.")

    line_buffer = BytesIO()
    plt.figure(figsize=(10, 6))
    plt.plot(months, totals, marker='o', linestyle='-', color='b')
    plt.xticks(rotation=45)
    plt.title("Monthly Expenses")
    plt.xlabel("Month")
    plt.ylabel("Total Expenses ($)")
    plt.grid()
    plt.tight_layout()
    plt.savefig(line_buffer, format='png')
    plt.close()
    line_buffer.seek(0)

    line_blob_name = f"monthly_expenses_line_chart_{user_email}.png"
    line_blob = pie_bucket.blob(line_blob_name)
    line_blob.upload_from_file(line_buffer, content_type='image/png')
    line_chart_url = line_blob.generate_signed_url(expiration=3600*24*7)

    return render_template(
        'report.html',
        pie_chart_url=pie_chart_url,
        line_chart_url=line_chart_url,
        error=None
    )




if __name__ == '__main__':
    create_bigquery_dataset()
    create_bigquery_table()
    app.run(debug=True, port=5000)
