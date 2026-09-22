import logging
import sys

def setup_logging(app):
    """Setup structured logging for the Flask app."""
    # Remove default handlers
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
        
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)
    
    # Do not log PII, use request IDs if available
    app.logger.info("BankEase Application Started")
