import time

# Very simple in-memory metrics for demo / logging purposes
_total_receipts = 0
_total_ocr_conf = 0.0
_total_cls_conf = 0.0
_total_retries = 0
_total_processing_time = 0.0

def record_receipt_start() -> float:
    return time.time()

def record_receipt_end(start_time: float):
    global _total_receipts, _total_processing_time
    _total_receipts += 1
    _total_processing_time += (time.time() - start_time)

def record_ocr_confidence(conf: float | None):
    global _total_ocr_conf
    if conf is not None:
        _total_ocr_conf += conf

def record_classification_confidence(conf: float | None):
    global _total_cls_conf
    if conf is not None:
        _total_cls_conf += conf

def record_retry():
    global _total_retries
    _total_retries += 1

def snapshot():
    """
    Returns a snapshot of current metrics for debugging/logging.
    """
    if _total_receipts == 0:
        avg_ocr = avg_cls = avg_time = 0.0
    else:
        avg_ocr = _total_ocr_conf / _total_receipts
        avg_cls = _total_cls_conf / _total_receipts
        avg_time = _total_processing_time / _total_receipts

    return {
        "total_receipts": _total_receipts,
        "avg_ocr_confidence": avg_ocr,
        "avg_classification_confidence": avg_cls,
        "avg_time_per_receipt_sec": avg_time,
        "total_retries": _total_retries,
    }
