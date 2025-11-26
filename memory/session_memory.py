class SessionMemoryService:
    """
    Lightweight wrapper over Flask session to keep per-user pipeline state.
    """

    def __init__(self, flask_session):
        self.s = flask_session
        # Initialize default keys if missing
        if "session_id" not in self.s:
            # You can later replace this with a proper UUID if needed
            self.s["session_id"] = self.s.get("_id", None)
        if "ocr_outputs" not in self.s:
            self.s["ocr_outputs"] = {}
        if "pending_stage" not in self.s:
            self.s["pending_stage"] = None

    def get_state(self):
        return {
            "session_id": self.s.get("session_id"),
            "last_receipt_summary": self.s.get("last_receipt_summary"),
            "pending_stage": self.s.get("pending_stage"),
            "ocr_outputs": self.s.get("ocr_outputs", {}),
        }

    def set_pending_stage(self, stage: str | None):
        self.s["pending_stage"] = stage

    def update_after_receipt(self, receipt_summary: dict):
        """
        Store last processed receipt summary and keep OCR outputs keyed by merchant + timestamp.
        """
        self.s["last_receipt_summary"] = receipt_summary
        ocr_outputs = self.s.get("ocr_outputs", {})
        key = f"{receipt_summary.get('merchant_name', 'unknown')}_{receipt_summary.get('transaction_date', 'na')}"
        ocr_outputs[key] = {
            "merchant_name": receipt_summary.get("merchant_name"),
            "transaction_date": str(receipt_summary.get("transaction_date")),
            "total": receipt_summary.get("total"),
            "category": receipt_summary.get("category"),
            "ocr_confidence": receipt_summary.get("ocr_confidence"),
            "classification_confidence": receipt_summary.get("classification_confidence"),
        }
        self.s["ocr_outputs"] = ocr_outputs
