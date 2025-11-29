import logging
from memory.merchant_memory import MerchantMemoryService
from observability import metrics
import os
import json
import vertexai
from vertexai.preview.generative_models import GenerativeModel

class CategorizationValidationAgent:
    """
    Agent 2: Categorizes the expense and runs a simple validation loop
    using past merchant history as long-term memory.
    """

    def __init__(self, confidence_threshold: float = 0.7):
        self.logger = logging.getLogger(__name__)
        self.memory = MerchantMemoryService()
        self.confidence_threshold = confidence_threshold

    # def _initial_category_guess(self, merchant_name: str) -> tuple[str, float]:
    #     """
    #     Very simple rule-based categorization – you can expand this later.
    #     Returns (category, confidence).
    #     """
    #     if not merchant_name or merchant_name == "N/A":
    #         return "Unknown", 0.3

    #     name_lower = merchant_name.lower()

    #     if any(x in name_lower for x in ["cafe", "coffee", "starbucks", "dunkin"]):
    #         return "Food & Beverage", 0.8
    #     if any(x in name_lower for x in ["mart", "market", "grocery", "walmart", "target"]):
    #         return "Groceries", 0.75
    #     if any(x in name_lower for x in ["uber", "lyft", "shell", "gas"]):
    #         return "Transport", 0.7

    #     return "Other", 0.6
    
    def _llm_category_guess(self, merchant_name: str, total: float) -> tuple[str, float]:
        try:
            from vertexai.preview.generative_models import GenerativeModel
            import vertexai
            import json, os, re

            vertexai.init(
                project=os.getenv("PROJECT_ID"),
                location="us-central1"
            )

            model = GenerativeModel("gemini-2.5-flash")

            prompt = f"""
    You are an expense classification API.
    You MUST return ONLY valid JSON.
    DO NOT include text, markdown, or explanations.

    Merchant: "{merchant_name}"
    Total: {total}

    Valid categories:
    Food & Beverage
    Groceries
    Transport
    Shopping
    Utilities
    Entertainment
    Health & Pharmacy
    Electronics
    Automotive
    Other

    Return ONLY in this exact format:
    {{"category":"Food & Beverage","confidence":0.85}}
    """

            response = model.generate_content(prompt)
            raw = response.text.strip()
            self.logger.info("Gemini RAW RESPONSE: %s", raw)

            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in Gemini output")

            data = json.loads(json_match.group())

            return data["category"], float(data["confidence"])

        except Exception as e:
            self.logger.exception("Gemini failed, fallback used")
            return "Other", 0.4


    def run(self, user_email: str, ocr_result: dict) -> dict:
        """
        Takes one OCR result dict and returns an enriched dict:

        {
          "merchant_name": ...,
          "transaction_date": ...,
          "num_items": ...,
          "total": ...,
          "category": ...,
          "classification_confidence": ...,
        }
        """
        merchant_name = ocr_result.get("merchant_name", "N/A")
        total = ocr_result.get("total")
        transaction_date = ocr_result.get("transaction_date")

        self.logger.info("CategorizationValidationAgent: starting categorization for %s", merchant_name)

        # Step 1: initial guess
        category, confidence = self._llm_category_guess(merchant_name, total)

        # Step 2: adjust using long-term memory from previous receipts
        stats = self.memory.get_stats(user_email, merchant_name)
        if stats:
            self.logger.info(
                "CategorizationValidationAgent: found merchant history: %s",
                stats
            )
            # Simple example: if frequent merchant, boost confidence
            if stats["frequency"] >= 3:
                confidence = min(1.0, confidence + 0.1)

        # Step 3: validation loop (simplified)
        iterations = 0
        max_iterations = 3
        while confidence < self.confidence_threshold and iterations < max_iterations:
            self.logger.info(
                "CategorizationValidationAgent: low confidence (%.2f), refining... iteration=%d",
                confidence, iterations
            )
            # Example refinement: if total is high, treat as "High Value Purchase"
            if total not in (None, "N/A") and float(total) > 200:
                category = f"High Value - {category}"
                confidence = min(1.0, confidence + 0.1)
            else:
                # Nothing more to refine in this simple demo
                confidence = self.confidence_threshold

            iterations += 1

        metrics.record_classification_confidence(confidence)

        enriched = {
            "merchant_name": merchant_name,
            "transaction_date": transaction_date,
            "num_items": ocr_result.get("num_items"),
            "total": total,
            "category": category,
            "ocr_confidence": ocr_result.get("ocr_confidence"),
            "classification_confidence": confidence,
        }

        self.logger.info(
            "CategorizationValidationAgent: final category=%s, confidence=%.2f",
            category, confidence
        )

        return enriched
