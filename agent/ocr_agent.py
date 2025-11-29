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
        - transaction_date (datetime or 'N/A')
        - num_items
        - total
        - ocr_confidence
        """
        self.logger.info("OcrExtractionAgent: starting OCR analysis")
        poller = self.client.begin_analyze_document("prebuilt-receipt", document=file_obj)
        result = poller.result()
        
        confidences = []
        for page in result.pages:
            for line in page.lines:
                if hasattr(line, "content") and hasattr(line, "confidence"):
                    confidences.append(line.confidence)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0

        if avg_confidence < 0.70:
            self.logger.warning(
                f"OcrExtractionAgent: Low OCR confidence ({avg_confidence}). Retrying once..."
            )
            # Re-run OCR once more
            poller_retry = self.client.begin_analyze_document("prebuilt-receipt", document=file_obj)
            result = poller_retry.result()


        receipts_data = []

        for receipt in result.documents:
            data = {}

            # Merchant name
            merchant_name_field = receipt.fields.get("MerchantName")
            merchant_name = merchant_name_field.value if merchant_name_field else "N/A"
            data["merchant_name"] = merchant_name

            # Transaction date normalization
            transaction_date_field = receipt.fields.get("TransactionDate")
            if transaction_date_field and transaction_date_field.value:
                value = transaction_date_field.value
                if isinstance(value, date):
                    transaction_date = datetime.combine(value, datetime.min.time())
                elif isinstance(value, datetime):
                    transaction_date = value
                else:
                    transaction_date = "N/A"
            else:
                transaction_date = "N/A"
            data["transaction_date"] = transaction_date

            # Number of items
            items_field = receipt.fields.get("Items")
            items = items_field.value if items_field else []
            data["num_items"] = len(items)

            # Total / subtotal
            # subtotal_field = receipt.fields.get("Subtotal")
            # total = subtotal_field.value if subtotal_field else "N/A"
            # data["total"] = total
            
            full_text = receipt.content if hasattr(receipt, "content") else ""
            total_amount = None
            print("\n=== AZURE RAW TEXT ===\n", full_text, "\n========================\n")
            
            
            for line in full_text.split("\n"):
                line = line.strip()
                match = re.search(r"TOTAL\s+([0-9]+\.[0-9]{2})", line, re.IGNORECASE)
                if match:
                    total_amount = float(match.group(1))
                    break
            if not total_amount:
                try:
                    item_sum = sum([float(item["price"]) for item in data.get("items", [])])
                    data["total"] = round(item_sum, 2)
                    self.logger.info(f"No total found; using item sum = {item_sum}")
                except:
                    data["total"] = None
                    self.logger.warning("Total could not be extracted or computed.")
            else:
                data["total"] = total_amount

            # Overall OCR confidence (best-effort) - accuracy metric
            ocr_confidence = getattr(receipt, "confidence", None)
            data["ocr_confidence"] = ocr_confidence

            
            self.logger.info(
                "OcrExtractionAgent: extracted receipt - merchant=%s, date=%s, total=%s, confidence=%s",
                merchant_name, transaction_date, data.get("total"), ocr_confidence
            )

            receipts_data.append(data)

        return receipts_data
