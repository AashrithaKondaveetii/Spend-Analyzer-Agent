import logging
from models import insert_into_bigquery, upload_to_bucket
from memory.session_memory import SessionMemoryService
from observability import metrics

class OrchestrationAgent:
    """
    Agent 3: Coordinates OCR (Agent 1) and Categorization (Agent 2),
    updates memory, and persists data.
    """

    def __init__(self, ocr_agent, categorization_agent):
        self.logger = logging.getLogger(__name__)
        self.ocr_agent = ocr_agent
        self.categorization_agent = categorization_agent

    def process_receipt(self, file_obj, user_email: str, flask_session, destination_blob_name: str):
        """
        Orchestrates the pipeline for a single uploaded receipt.

        Returns:
          (receipt_details_list, error_message_or_None)
        """
        start_time = metrics.record_receipt_start()
        session_memory = SessionMemoryService(flask_session)
        session_memory.set_pending_stage("uploading")

        try:
            # 1) Upload file to GCS
            self.logger.info("OrchestrationAgent: uploading file to bucket as %s", destination_blob_name)
            public_url = upload_to_bucket(file_obj, destination_blob_name)

            # Reset file pointer for OCR
            file_obj.seek(0)

            # 2) Run OCR via Agent 1
            self.logger.info("Orchestrator → OCR-Agent: Starting OCR extraction")
            session_memory.set_pending_stage("ocr")
            ocr_results = self.ocr_agent.run(file_obj)

            if not ocr_results:
                self.logger.warning("OrchestrationAgent: OCR returned no receipts")
                return [], "No receipt content detected. Please try another image."

            receipt_details = []

            for ocr_result in ocr_results:
                ocr_conf = ocr_result.get("ocr_confidence")
                metrics.record_ocr_confidence(ocr_conf)

                # Example of an internal A2A-style message (for logging/demo)
                if ocr_conf is not None and ocr_conf < 0.5:
                    self.logger.info(
                        "A2A message: CategorizationAgent -> OcrAgent: low confidence (%.2f), suggest retry with enhanced preprocessing",
                        ocr_conf
                    )
                    # In a more advanced version you could re-run OCR here
                    metrics.record_retry()

                # 3) Run categorization via Agent 2
                self.logger.info("Orchestrator → Categorization-Agent: Sending OCR output for categorization")
                session_memory.set_pending_stage("categorization")
                enriched = self.categorization_agent.run(user_email=user_email, ocr_result=ocr_result)
                self.logger.info("Categorization-Agent → Orchestrator: Returning validated receipt data")


                # 4) Add persistent fields
                enriched["Receipt URL"] = public_url
                enriched["User Email"] = user_email

                # 5) Persist into BigQuery (uses existing function)
                insert_into_bigquery({
                    "Merchant Name": enriched["merchant_name"],
                    "Transaction Date": enriched["transaction_date"],
                    "Number of Items": enriched["num_items"],
                    "Category": enriched["category"],
                    "Total": enriched["total"],
                    "Receipt URL": enriched["Receipt URL"],
                    "User Email": enriched["User Email"],
                })

                # 6) Update session memory
                session_memory.update_after_receipt(enriched)

                # Prepare for template (keep keys like your old template uses)
                receipt_details.append({
                    "Merchant Name": enriched["merchant_name"],
                    "Transaction Date": enriched["transaction_date"],
                    "Number of Items": enriched["num_items"],
                    "Total": enriched["total"],
                    "Receipt URL": enriched["Receipt URL"],
                    "User Email": enriched["User Email"],
                    "Category": enriched["category"],
                    "OCR Confidence": enriched["ocr_confidence"],
                    "Classification Confidence": enriched["classification_confidence"],
                })

            session_memory.set_pending_stage(None)
            return receipt_details, None

        except Exception as e:
            self.logger.exception("OrchestrationAgent: error while processing receipt")
            return [], f"Error processing receipt: {e}"

        finally:
            metrics.record_receipt_end(start_time)
            self.logger.info("OrchestrationAgent: metrics snapshot: %s", metrics.snapshot())
