import logging
from datetime import datetime, date

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
            subtotal_field = receipt.fields.get("Subtotal")
            total = subtotal_field.value if subtotal_field else "N/A"
            data["total"] = total

            # Overall OCR confidence (best-effort) - accuracy metric
            ocr_confidence = getattr(receipt, "confidence", None)
            data["ocr_confidence"] = ocr_confidence

            
            self.logger.info(
                "OcrExtractionAgent: extracted receipt - merchant=%s, date=%s, total=%s, confidence=%s",
                merchant_name, transaction_date, total, ocr_confidence
            )

            receipts_data.append(data)

        return receipts_data
