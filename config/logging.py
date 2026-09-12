import logging
import sys

def setup_logging(log_level: str = "INFO"):
    #Clear any existing handlers
    logger = logging.getLogger("HealthLink")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()

    #Create Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    #Simple, clean text formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger



