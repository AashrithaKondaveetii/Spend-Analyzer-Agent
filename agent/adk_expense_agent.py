# adk_expense_agent.py

import asyncio
import os
from typing import Optional, Dict

from google.cloud import bigquery
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from models import FULL_TABLE_ID, PROJECT_ID


# ============================================================
# 0. CONFIGURE GOOGLE AI API (Gemini)
# ============================================================
# Using Google AI API with API key from AI Studio
# Make sure GOOGLE_API_KEY is set in your .env file

# IMPORTANT: Disable Vertex AI to use Google AI API instead
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"

# Check that API key is available
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError(
        "GOOGLE_API_KEY environment variable is required. "
        "Get one from https://aistudio.google.com/app/apikey and add it to your .env file."
    )

print(f"Using Google AI API (Gemini) with API key")


# ============================================================
# 1. BigQuery Helper Functions (TOOLS)
# ============================================================

def _bq_client() -> bigquery.Client:
    return bigquery.Client()


def get_total_spend_for_merchant(user_email: str, merchant_name: str) -> Dict:
    client = _bq_client()

    query = f"""
        SELECT SUM(Total) AS total
        FROM `{FULL_TABLE_ID}`
        WHERE LOWER(`User Email`) = LOWER(@user_email)
          AND LOWER(`Merchant Name`) = LOWER(@merchant_name)
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
                bigquery.ScalarQueryParameter("merchant_name", "STRING", merchant_name),
            ]
        )
    )

    rows = list(job.result())
    total = rows[0].total if rows and rows[0].total else None

    if not total:
        return {
            "status": "no_data",
            "merchant": merchant_name,
            "message": f"No spend found for '{merchant_name}'."
        }

    return {
        "status": "success",
        "merchant": merchant_name,
        "total": float(total),
        "message": f"You spent ${float(total):.2f} at {merchant_name}."
    }


def get_total_spend_for_category(user_email: str, category: str, last_n_days: Optional[int] = None) -> Dict:
    client = _bq_client()

    params = [
        bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
        bigquery.ScalarQueryParameter("category", "STRING", category),
    ]

    date_filter = ""
    if last_n_days is not None:
        date_filter = """
            AND `Transaction Date` >= DATETIME(
                TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            )
        """
        params.append(bigquery.ScalarQueryParameter("days", "INT64", last_n_days))

    query = f"""
        SELECT SUM(Total) AS total
        FROM `{FULL_TABLE_ID}`
        WHERE LOWER(`User Email`) = LOWER(@user_email)
          AND LOWER(`Category`) = LOWER(@category)
          {date_filter}
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(query_parameters=params)
    )

    rows = list(job.result())
    total = rows[0].total if rows and rows[0].total else None

    scope = f"last {last_n_days} days" if last_n_days else "all time"

    if not total:
        return {
            "status": "no_data",
            "category": category,
            "message": f"No spend found for category '{category}' ({scope})."
        }

    return {
        "status": "success",
        "category": category,
        "total": float(total),
        "message": f"You spent ${float(total):.2f} on {category} ({scope})."
    }


def get_monthly_summary(user_email: str, year: int, month: int) -> Dict:
    client = _bq_client()

    query = f"""
        SELECT `Category` AS category, SUM(Total) AS total
        FROM `{FULL_TABLE_ID}`
        WHERE LOWER(`User Email`) = LOWER(@user_email)
          AND EXTRACT(YEAR FROM `Transaction Date`) = @year
          AND EXTRACT(MONTH FROM `Transaction Date`) = @month
        GROUP BY category
        ORDER BY total DESC
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
                bigquery.ScalarQueryParameter("year", "INT64", year),
                bigquery.ScalarQueryParameter("month", "INT64", month),
            ]
        )
    )

    rows = list(job.result())

    if not rows:
        return {
            "status": "no_data",
            "year": year,
            "month": month,
            "message": f"No spend data found for {year}-{month:02d}.",
            "by_category": []
        }

    return {
        "status": "success",
        "year": year,
        "month": month,
        "message": f"Summary for {year}-{month:02d}",
        "by_category": [
            {"category": r.category, "total": float(r.total)}
            for r in rows
        ],
    }


# ============================================================
# 2. REGISTER TOOLS WITH ADK
# ============================================================

total_merchant_tool = FunctionTool(func=get_total_spend_for_merchant)
total_category_tool = FunctionTool(func=get_total_spend_for_category)
monthly_summary_tool = FunctionTool(func=get_monthly_summary)


# ============================================================
# 3. ADK AGENT DEFINITION
# ============================================================

# Model ID for Google AI API (Gemini)
GEMINI_MODEL_ID = "gemini-2.0-flash"

expense_agent = Agent(
    model=GEMINI_MODEL_ID,
    name="expense_agent",
    instruction=(
        "You are a financial assistant that answers questions about a user's spending.\n"
        "Use the provided tools to retrieve exact data from BigQuery.\n"
        "The user's email is provided as the user_id - use it when calling tools.\n\n"
        "Rules:\n"
        "- Never make up numbers.\n"
        "- Always use tools for answers.\n"
        "- If no data is found, say so clearly.\n"
        "- The user_email parameter for tools should be the user's email address.\n"
    ),
    tools=[total_merchant_tool, total_category_tool, monthly_summary_tool],
)


# ============================================================
# 4. RUNNER + SESSION SERVICE
# ============================================================

_session_service: Optional[InMemorySessionService] = None
_runner: Optional[Runner] = None

# Use consistent app name
APP_NAME = "expense_tracker"


def _get_session_service() -> InMemorySessionService:
    """Get or create the global session service."""
    global _session_service
    if _session_service is None:
        _session_service = InMemorySessionService()
    return _session_service


def _get_runner() -> Runner:
    """Get or create the global runner."""
    global _runner
    if _runner is None:
        _runner = Runner(
            app_name=APP_NAME,
            agent=expense_agent,
            session_service=_get_session_service(),
        )
    return _runner


async def _ensure_session_exists(user_id: str, session_id: str) -> None:
    """
    Check if session exists, create it if not.
    ADK requires sessions to be created before use.
    """
    session_service = _get_session_service()
    
    # Try to get existing session
    existing_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )
    
    # If session doesn't exist, create it
    if existing_session is None:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
        print(f"Created new session: {session_id} for user: {user_id}")
    else:
        print(f"Using existing session: {session_id}")


def _run_in_new_loop(coro):
    """Run an async coroutine in a new event loop (safe for Flask)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================
# 5. MAIN ENTRY POINT USED BY app.py
# ============================================================

def run_expense_query(user_id: str, session_id: str, text: str) -> str:
    """
    Main entry point for running expense queries.
    Ensures session exists before running the agent.
    """
    # Step 1: Ensure session exists
    _run_in_new_loop(_ensure_session_exists(user_id, session_id))
    
    # Step 2: Get the runner
    runner = _get_runner()

    # Step 3: Create the user message
    # Include the user_id (email) in the message so the agent knows which user
    enhanced_text = f"[User email: {user_id}] {text}"
    
    user_msg = types.Content(
        role="user",
        parts=[types.Part(text=enhanced_text)],
    )

    # Step 4: Run the agent
    events = runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg,
    )

    # Step 5: Process events and extract response
    # Updated for newer ADK API - check event attributes directly
    final_text = ""

    for event in events:
        print("EVENT:", event)
        
        # Check if this event has content with text (model response)
        if hasattr(event, 'content') and event.content:
            content = event.content
            if hasattr(content, 'parts') and content.parts:
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        final_text = part.text
        
        # Also check for 'text' attribute directly on event
        if hasattr(event, 'text') and event.text:
            final_text = event.text

    if not final_text:
        final_text = "Sorry, I couldn't answer that. Try asking about a merchant or category."

    return final_text