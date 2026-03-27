# utils/error_handler.py
from utils.logger import log_info

def handle_error(e):
    log_info(f"❌ ERROR: {str(e)}")
