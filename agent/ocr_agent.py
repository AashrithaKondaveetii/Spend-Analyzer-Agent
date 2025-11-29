import logging
from datetime import datetime, date
import re


class OcrExtractionAgent:
    """
    Agent 1: Runs Azure Form Recognizer OCR and returns structured receipt data.
    """

    def __init__(self, document_analysis_client):
        self.client = document_analysis_client
        self.logger = logging.getLogger(__name__)

    def run(self, file_obj):
        """
        Run OCR on the given file-like object.

        Returns: list[dict] with keys:
        - merchant_name
        - transaction_date
        - num_items
        - total
        - ocr_confidence
        """
        self.logger.info("OcrExtractionAgent: starting OCR analysis")

        poller = self.client.begin_analyze_document("prebuilt-receipt", document=file_obj)
        result = poller.result()

        # -----------------------------
        # OCR CONFIDENCE CHECK
        # -----------------------------
        confidences = []
        for page in result.pages:
            for line in page.lines:
                if hasattr(line, "confidence"):
                    confidences.append(line.confidence)

        avg_conf = sum(confidences) / len(confidences) if confidences else 1.0

        if avg_conf < 0.70:
            self.logger.warning(f"Low OCR confidence {avg_conf:.2f}. Retrying once.")
            poller_retry = self.client.begin_analyze_document("prebuilt-receipt", document=file_obj)
            result = poller_retry.result()

        receipts_data = []

        # -------------------------------------------------------
        # GET FULL TEXT (Azure doesn't store it in receipt.content)
        # -------------------------------------------------------
        raw_text_lines = []
        for page in result.pages:
            for line in page.lines:
                if hasattr(line, "content"):
                    raw_text_lines.append(line.content)

        full_text = "\n".join(raw_text_lines)
        print("\n========== AZURE RAW TEXT ==========\n", full_text, "\n====================================\n")

        # -----------------------------
        # PARSE RECEIPTS
        # -----------------------------
        for receipt in result.documents:
            data = {}

            # Merchant
            merchant_field = receipt.fields.get("MerchantName")
            data["merchant_name"] = merchant_field.value if merchant_field else "N/A"

            # Transaction Date
            date_field = receipt.fields.get("TransactionDate")
            if date_field and date_field.value:
                val = date_field.value
                if isinstance(val, date):
                    data["transaction_date"] = datetime.combine(val, datetime.min.time())
                else:
                    data["transaction_date"] = val
            else:
                data["transaction_date"] = "N/A"

            # Items count
            items_field = receipt.fields.get("Items")
            items = items_field.value if items_field else []
            data["num_items"] = len(items)

            # ------------------------------------
            #          TOTAL EXTRACTION
            # ------------------------------------
            total_amount = None

            # 1. Azure Total field (highest priority)
            total_field = receipt.fields.get("Total")
            if total_field and total_field.value:
                try:
                    total_amount = float(total_field.value)
                except:
                    pass

            # 2. Azure Subtotal field (old system behavior)
            if not total_amount:
                subtotal_field = receipt.fields.get("Subtotal")
                if subtotal_field and subtotal_field.value:
                    try:
                        total_amount = float(subtotal_field.value)
                    except:
                        pass

            # 3. Regex fallback from raw text
            if not total_amount:
                for line in full_text.split("\n"):
                    match = re.search(
                        r"(TOTAL|AMOUNT|BALANCE)\s*[:\-]?\s*([0-9]+\.[0-9]{2})",
                        line,
                        re.IGNORECASE,
                    )
                    if match:
                        total_amount = float(match.group(2))
                        break

            # 4. Item-sum fallback (last resort)
            if not total_amount:
                item_sum = 0.0
                if items:
                    for item in items:
                        price_field = item.value.get("Price") if hasattr(item, "value") else None
                        if price_field and price_field.value:
                            try:
                                item_sum += float(price_field.value)
                            except:
                                pass

                if item_sum > 0:
                    self.logger.info(f"No total found; using item sum = {item_sum}")
                    total_amount = round(item_sum, 2)

            data["total"] = total_amount if total_amount else 0.0

            # OCR Confidence
            data["ocr_confidence"] = getattr(receipt, "confidence", avg_conf)

            self.logger.info(
                "OcrExtractionAgent: extracted receipt - merchant=%s, date=%s, total=%s, confidence=%s",
                data["merchant_name"], data["transaction_date"], data["total"], data["ocr_confidence"]
            )

            receipts_data.append(data)

        return receipts_data
