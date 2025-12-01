# Spend Analyzer - AI-Powered Expense Tracking with Multi-Agent System

An intelligent expense tracking application that uses a **multi-agent AI system** to automatically extract, categorize, and analyze your spending from receipt images. Built as a capstone project for the **5-Day AI Agents Intensive Course with Google (Nov 2025)**.

---

## Problem Statement

Managing personal expenses is tedious and time-consuming:

- **Manual data entry** from receipts is error-prone and slow
- **Categorizing expenses** requires consistent effort
- **Tracking spending patterns** across merchants is difficult
- **Querying historical data** requires spreadsheet skills

---

## Solution

**Spend Analyzer** automates the entire expense tracking workflow using a **multi-agent AI system**:

1. **Upload a receipt image** → AI extracts all details automatically
2. **Smart categorization** → AI categorizes expenses using LLM + historical patterns
3. **Natural language queries** → Ask questions like "How much did I spend at Starbucks?"
4. **Visual reports** → Generate charts showing spending patterns

### Value Proposition

| Before                            | After (with Spend Analyzer)               |
| --------------------------------- | ----------------------------------------- |
| 5-10 min manual entry per receipt | < 10 seconds automatic extraction         |
| Inconsistent categories           | AI-powered consistent categorization      |
| Complex spreadsheet queries       | Natural language: "Show my food spending" |
| No spending insights              | Automatic charts and trends               |

---

### Agent Details

| Agent                    | Type           | Purpose                                      | Technology              |
| ------------------------ | -------------- | -------------------------------------------- | ----------------------- |
| **OCR Agent**            | Sequential     | Extract text/data from receipt images        | Azure Form Recognizer   |
| **Categorization Agent** | LLM + Loop     | Classify expenses with confidence refinement | Gemini 2.5 Flash        |
| **Orchestrator Agent**   | Coordinator    | Manage pipeline flow and state               | Python                  |
| **ADK Expense Agent**    | Conversational | Answer natural language spending queries     | Google ADK + Gemini 2.0 |

---

## Key Features

### 1. Smart Receipt Processing

- Upload receipt images (JPG, PNG, PDF)
- Automatic extraction of merchant, date, items, total
- AI-powered expense categorization

### 2. Natural Language Queries

- "How much did I spend at Walmart?"
- "What's my total spending on groceries?"
- "Show me my November 2025 summary"

### 3. Visual Reports

- Pie charts: Top merchants by spending
- Line charts: Monthly expense trends

### 4. Secure & Personalized

- Google OAuth authentication
- Per-user data isolation
- Session-based state management

---

### Detailed Concept Breakdown

#### Multi-Agent System (Sequential)

```
User uploads receipt
        │
        ▼
┌─────────────────┐
│  OCR Agent      │  ──► Extracts: merchant, date, items, total
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Categorization  │  ──► Classifies: Food, Transport, Shopping, etc.
│     Agent       │
│  (with Loop)    │  ──► Refines confidence until threshold met
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orchestrator   │  ──► Saves to BigQuery, updates memory
└─────────────────┘
```

#### Loop Agent (Confidence Refinement)

```python
# In categorization_agent.py
while confidence < self.confidence_threshold and iterations < max_iterations:
    # Refine category based on rules
    if total > 200:
        category = f"High Value - {category}"
        confidence += 0.1
    iterations += 1
```

#### Long-term Memory

```python
# MerchantMemoryService queries BigQuery for historical patterns
stats = self.memory.get_stats(user_email, merchant_name)
# Returns: {"frequency": 15, "avg_spend": 12.34}

# Boosts confidence for frequent merchants
if stats["frequency"] >= 3:
    confidence = min(1.0, confidence + 0.1)
```

#### Custom Tools (ADK)

```python
# Three BigQuery tools for the ADK agent
total_merchant_tool = FunctionTool(func=get_total_spend_for_merchant)
total_category_tool = FunctionTool(func=get_total_spend_for_category)
monthly_summary_tool = FunctionTool(func=get_monthly_summary)
```

---

## Tech Stack

| Component          | Technology                                     |
| ------------------ | ---------------------------------------------- |
| **Backend**        | Python 3.12, Flask                             |
| **AI/ML**          | Google ADK, Gemini 2.0 Flash, Gemini 2.5 Flash |
| **OCR**            | Azure Form Recognizer                          |
| **Database**       | Google BigQuery                                |
| **Storage**        | Google Cloud Storage                           |
| **Authentication** | Google OAuth 2.0                               |
| **Charts**         | Matplotlib                                     |
| **Frontend**       | HTML, Bootstrap 5, Jinja2                      |

---

## Setup Instructions

### Prerequisites

- Python 3.12+
- Google Cloud account with:
  - BigQuery API enabled
  - Cloud Storage API enabled
  - Service account with appropriate permissions
- Azure account with Form Recognizer resource
- Google OAuth credentials

### 1. Clone the Repository

```bash
git clone https://github.com/AashrithaKondaveetii/Spend-Analyzer-Agent.git
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Google Cloud
PROJECT_ID=your-gcp-project-id
DATASET_ID=receipts_dataset
TABLE_ID=receipts
FULL_TABLE_ID=your-project.receipts_dataset.receipts
BUCKET_NAME=your-receipt-bucket
REPORT_BUCKET_NAME=your-report-bucket
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Google AI API (Gemini)
GOOGLE_API_KEY=your-google-ai-api-key
GOOGLE_GENAI_USE_VERTEXAI=false

# Azure Form Recognizer
AZURE_FORM_RECOGNIZER_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_KEY=your-azure-key

# Google OAuth
CLIENT_ID=your-oauth-client-id
CLIENT_SECRET=your-oauth-client-secret
REDIRECT_CALLBACK=http://127.0.0.1:5000/callback
AUTHORIZATION_BASE_URL=https://accounts.google.com/o/oauth2/auth
TOKEN_URL=https://accounts.google.com/o/oauth2/token
```

### 5. Run the Application

```bash
python app.py
```

The application will be available at `http://127.0.0.1:5000`

---

## Usage

### 1. Login

Click "Login" to authenticate with your Google account.

### 2. Upload Receipt

- Click "Upload a Receipt"
- Select a receipt image
- View extracted details and AI-assigned category

### 3. Ask Questions

Use the chat interface on the home page:

- "How much did I spend at Starbucks?"
- "What's my grocery spending this month?"
- "Show me my spending summary for November 2025"

### 4. View Reports

Click "Generate Report" to see:

- Top 5 merchants by spending (pie chart)
- Monthly expense trends (line chart)

---

## Future Enhancements

- [ ] **Budget Advisor Agent** - Personalized savings recommendations
- [ ] **Voice Interface** - Hands-free expense logging
- [ ] **Multi-currency Support** - International receipt handling
- [ ] **Export to CSV/PDF** - Download expense reports

---

## Authors

**Aashritha Kondaveeti**
**Sumana Sanyasipura Nagaraju**

Built as part of the [5-Day AI Agents Intensive Course with Google]
