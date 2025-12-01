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

# IMPORTANT: Disable Vertex AI to use Google AI API instead
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"

# Check that API key is available
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError(
        "GOOGLE_API_KEY environment variable is required. "
        "Get one from https://aistudio.google.com/app/apikey and add it to your .env file."
    )

print("Using Google AI API (Gemini) with API key")


# ============================================================
# 1. BigQuery Helper Functions (TOOLS)
# ============================================================

def _bq_client() -> bigquery.Client:
    return bigquery.Client()


# Category mapping for fuzzy matching
CATEGORY_ALIASES = {
    "food": "Food & Beverage",
    "food & beverage": "Food & Beverage",
    "food and beverage": "Food & Beverage",
    "food and beverages": "Food & Beverage",
    "food & beverages": "Food & Beverage",
    "restaurant": "Food & Beverage",
    "restaurants": "Food & Beverage",
    "dining": "Food & Beverage",
    "eating out": "Food & Beverage",
    "coffee": "Food & Beverage",
    "cafe": "Food & Beverage",
    
    "grocery": "Groceries",
    "groceries": "Groceries",
    "supermarket": "Groceries",
    
    "transport": "Transport",
    "transportation": "Transport",
    "travel": "Transport",
    "uber": "Transport",
    "lyft": "Transport",
    "gas": "Transport",
    "fuel": "Transport",
    
    "shop": "Shopping",
    "shopping": "Shopping",
    "retail": "Shopping",
    
    "utility": "Utilities",
    "utilities": "Utilities",
    "bills": "Utilities",
    
    "entertainment": "Entertainment",
    "fun": "Entertainment",
    "movies": "Entertainment",
    "games": "Entertainment",
    
    "health": "Health & Pharmacy",
    "pharmacy": "Health & Pharmacy",
    "medical": "Health & Pharmacy",
    "medicine": "Health & Pharmacy",
    
    "electronics": "Electronics",
    "tech": "Electronics",
    "gadgets": "Electronics",
    
    "auto": "Automotive",
    "automotive": "Automotive",
    "car": "Automotive",
}


def _normalize_category(category: str) -> str:
    """Normalize category input to match database categories."""
    if not category:
        return category
    
    category_lower = category.lower().strip()
    
    # Check if it's an alias
    if category_lower in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[category_lower]
    
    # Return original if no alias found
    return category


def get_total_spend_for_merchant(user_email: str, merchant_name: str) -> Dict:
    """
    Get total spending for a specific merchant.
    Use this when user asks about spending at a specific store/merchant.
    """
    client = _bq_client()
    
    # Use LIKE for partial matching
    merchant_pattern = f"%{merchant_name}%"
    
    # Debug logging
    print(f"DEBUG MERCHANT: Searching for merchant='{merchant_name}', Pattern='{merchant_pattern}', User='{user_email}'")

    query = f"""
        SELECT SUM(Total) AS total
        FROM `{FULL_TABLE_ID}`
        WHERE LOWER(`User Email`) = LOWER(@user_email)
          AND LOWER(`Merchant Name`) LIKE LOWER(@merchant_pattern)
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
                bigquery.ScalarQueryParameter("merchant_pattern", "STRING", merchant_pattern),
            ]
        )
    )

    rows = list(job.result())
    total = rows[0].total if rows and rows[0].total else None
    
    print(f"DEBUG MERCHANT: Query result total={total}")

    if not total:
        return {
            "status": "no_data",
            "merchant": merchant_name,
            "message": f"No spending found for '{merchant_name}'."
        }

    return {
        "status": "success",
        "merchant": merchant_name,
        "total": float(total),
        "message": f"You spent ${float(total):.2f} at {merchant_name}."
    }


def get_total_spend_for_category(user_email: str, category: str, last_n_days: Optional[int] = None) -> Dict:
    """
    Get total spending for a category like 'food', 'groceries', 'transport', etc.
    Supports fuzzy matching - 'food' will match 'Food & Beverage'.
    """
    client = _bq_client()
    
    # Normalize the category (fuzzy matching)
    normalized_category = _normalize_category(category)
    
    # Use pattern matching with % wildcards for partial matches
    category_pattern = f"%{normalized_category}%"
    
    # Debug logging
    print(f"DEBUG: Original category='{category}', Normalized='{normalized_category}', Pattern='{category_pattern}'")

    params = [
        bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
        bigquery.ScalarQueryParameter("category_pattern", "STRING", category_pattern),
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
          AND LOWER(`Category`) LIKE LOWER(@category_pattern)
          {date_filter}
    """
    
    print(f"DEBUG: Running query with user_email='{user_email}'")

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(query_parameters=params)
    )

    rows = list(job.result())
    total = rows[0].total if rows and rows[0].total else None
    
    print(f"DEBUG: Query result total={total}")

    scope = f"in the last {last_n_days} days" if last_n_days else "in total"

    if not total:
        return {
            "status": "no_data",
            "category": category,
            "normalized_category": normalized_category,
            "message": f"No spending found for '{category}' ({scope})."
        }

    return {
        "status": "success",
        "category": category,
        "normalized_category": normalized_category,
        "total": float(total),
        "message": f"You spent ${float(total):.2f} on {normalized_category} {scope}."
    }


def get_total_spending(user_email: str, year: Optional[int] = None, month: Optional[int] = None, last_n_days: Optional[int] = None) -> Dict:
    """
    Get total overall spending. Can optionally filter by year, month, or last N days.
    Use this when user asks 'how much did I spend overall/total/in general'.
    - If no filters: returns all-time total
    - If year only: returns yearly total
    - If year and month: returns monthly total
    - If last_n_days: returns spending in last N days
    """
    client = _bq_client()
    
    params = [
        bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
    ]
    
    filters = []
    scope_description = "all time"
    
    if last_n_days is not None:
        filters.append("""
            `Transaction Date` >= DATETIME(
                TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            )
        """)
        params.append(bigquery.ScalarQueryParameter("days", "INT64", last_n_days))
        scope_description = f"last {last_n_days} days"
    else:
        if year is not None:
            filters.append("EXTRACT(YEAR FROM `Transaction Date`) = @year")
            params.append(bigquery.ScalarQueryParameter("year", "INT64", year))
            scope_description = str(year)
            
        if month is not None:
            filters.append("EXTRACT(MONTH FROM `Transaction Date`) = @month")
            params.append(bigquery.ScalarQueryParameter("month", "INT64", month))
            scope_description = f"{year}-{month:02d}" if year else f"month {month}"
    
    where_clause = " AND ".join(filters) if filters else "1=1"
    
    query = f"""
        SELECT 
            SUM(Total) AS total,
            COUNT(*) AS transaction_count
        FROM `{FULL_TABLE_ID}`
        WHERE LOWER(`User Email`) = LOWER(@user_email)
          AND Total IS NOT NULL
          AND {where_clause}
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(query_parameters=params)
    )

    rows = list(job.result())
    total = rows[0].total if rows and rows[0].total else None
    count = rows[0].transaction_count if rows else 0

    if not total:
        return {
            "status": "no_data",
            "scope": scope_description,
            "message": f"No spending data found for {scope_description}."
        }

    return {
        "status": "success",
        "scope": scope_description,
        "total": float(total),
        "transaction_count": count,
        "message": f"You spent ${float(total):.2f} in {scope_description} across {count} transactions."
    }


def get_monthly_summary(user_email: str, year: int, month: int) -> Dict:
    """
    Get spending breakdown by category for a specific month.
    Use this when user asks for a detailed monthly summary or breakdown.
    """
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
            "message": f"No spending data found for {year}-{month:02d}.",
            "by_category": []
        }
    
    total_spent = sum(float(r.total) for r in rows)

    return {
        "status": "success",
        "year": year,
        "month": month,
        "total": total_spent,
        "message": f"In {year}-{month:02d}, you spent ${total_spent:.2f} total.",
        "by_category": [
            {"category": r.category, "total": float(r.total)}
            for r in rows
        ],
    }


def get_spending_by_category(user_email: str, year: Optional[int] = None) -> Dict:
    """
    Get spending breakdown by all categories.
    Use this when user asks 'what are my spending categories' or 'breakdown by category'.
    """
    client = _bq_client()
    
    params = [
        bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
    ]
    
    year_filter = ""
    scope = "all time"
    if year is not None:
        year_filter = "AND EXTRACT(YEAR FROM `Transaction Date`) = @year"
        params.append(bigquery.ScalarQueryParameter("year", "INT64", year))
        scope = str(year)

    query = f"""
        SELECT 
            `Category` AS category, 
            SUM(Total) AS total,
            COUNT(*) AS count
        FROM `{FULL_TABLE_ID}`
        WHERE LOWER(`User Email`) = LOWER(@user_email)
          AND Total IS NOT NULL
          {year_filter}
        GROUP BY category
        ORDER BY total DESC
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(query_parameters=params)
    )

    rows = list(job.result())

    if not rows:
        return {
            "status": "no_data",
            "scope": scope,
            "message": f"No spending data found for {scope}.",
            "categories": []
        }
    
    total_spent = sum(float(r.total) for r in rows)

    return {
        "status": "success",
        "scope": scope,
        "total": total_spent,
        "message": f"Your spending breakdown for {scope}:",
        "categories": [
            {"category": r.category, "total": float(r.total), "count": r.count}
            for r in rows
        ],
    }


def get_all_merchants(user_email: str) -> Dict:
    """
    Get list of all merchants the user has spent money at.
    Use this when user asks 'list all merchants', 'where have I spent money', 'what stores', etc.
    """
    client = _bq_client()
    
    print(f"DEBUG MERCHANTS LIST: Getting all merchants for user='{user_email}'")

    query = f"""
        SELECT 
            `Merchant Name` AS merchant,
            SUM(Total) AS total,
            COUNT(*) AS visit_count
        FROM `{FULL_TABLE_ID}`
        WHERE LOWER(`User Email`) = LOWER(@user_email)
          AND Total IS NOT NULL
        GROUP BY merchant
        ORDER BY total DESC
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
            ]
        )
    )

    rows = list(job.result())
    
    print(f"DEBUG MERCHANTS LIST: Found {len(rows)} merchants")

    if not rows:
        return {
            "status": "no_data",
            "message": "No merchants found. You haven't recorded any spending yet.",
            "merchants": []
        }
    
    total_spent = sum(float(r.total) for r in rows)

    return {
        "status": "success",
        "total_merchants": len(rows),
        "total_spent": total_spent,
        "message": f"You've spent money at {len(rows)} merchant(s):",
        "merchants": [
            {"merchant": r.merchant, "total": float(r.total), "visits": r.visit_count}
            for r in rows
        ],
    }


# ============================================================
# 2. REGISTER TOOLS WITH ADK
# ============================================================

total_merchant_tool = FunctionTool(func=get_total_spend_for_merchant)
total_category_tool = FunctionTool(func=get_total_spend_for_category)
total_spending_tool = FunctionTool(func=get_total_spending)
monthly_summary_tool = FunctionTool(func=get_monthly_summary)
category_breakdown_tool = FunctionTool(func=get_spending_by_category)
all_merchants_tool = FunctionTool(func=get_all_merchants)


# ============================================================
# 3. ADK AGENT DEFINITION
# ============================================================

GEMINI_MODEL_ID = "gemini-2.0-flash"

expense_agent = Agent(
    model=GEMINI_MODEL_ID,
    name="expense_agent",
    instruction="""You are a helpful financial assistant that answers questions about a user's spending and expenses.

You have access to the following tools to query their expense data:

1. **get_total_spend_for_merchant**: Use when user asks about a specific store/merchant
   Example: "How much did I spend at Starbucks?" or "How much at Coffee Shop?"

2. **get_total_spend_for_category**: Use when user asks about a category
   Example: "How much did I spend on food?" or "What's my grocery spending?"
   Note: The tool handles fuzzy matching, so "food" will match "Food & Beverage"

3. **get_total_spending**: Use when user asks about total/overall spending
   Example: "How much did I spend overall?" or "What's my total spending?"
   - Pass no parameters for all-time total
   - Pass year for yearly total
   - Pass year and month for monthly total

4. **get_monthly_summary**: Use when user wants a detailed breakdown for a specific month
   Example: "Show me my November 2025 breakdown"

5. **get_spending_by_category**: Use when user wants to see all categories
   Example: "What categories do I spend on?" or "Show me breakdown by category"

6. **get_all_merchants**: Use when user wants to see all merchants/stores they've spent at
   Example: "List all merchants" or "Where have I spent money?" or "What stores have I been to?"

IMPORTANT RULES:
- The user's email is provided at the start of their message in [User email: xxx] format. Extract and use it.
- Always use the appropriate tool - never make up numbers.
- Be flexible with user queries - understand intent even if wording is different.
- For "list merchants" or "where did I spend", use get_all_merchants.
- For specific merchant queries like "how much at X", use get_total_spend_for_merchant.
- Give concise, friendly responses with the spending amounts.
- If no data found, say so politely.
""",
    tools=[
        total_merchant_tool, 
        total_category_tool, 
        total_spending_tool,
        monthly_summary_tool,
        category_breakdown_tool,
        all_merchants_tool
    ],
)


# ============================================================
# 4. RUNNER + SESSION SERVICE
# ============================================================

_session_service: Optional[InMemorySessionService] = None
_runner: Optional[Runner] = None

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
    
    existing_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )
    
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

    # Step 3: Create the user message with email context
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
        final_text = "Sorry, I couldn't answer that. Try asking about a merchant, category, or your total spending."

    return final_text