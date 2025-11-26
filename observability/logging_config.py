import logging

def setup_logging():
    """
    Configure basic logging format for the whole app.
    Call this once in app.py after creating the Flask app.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
