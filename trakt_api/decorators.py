# trakt_api/decorators.py
import time
from functools import wraps
from trakt.errors import RateLimitException, TraktInternalException

def retry(retries=5, delay=30):
    """A decorator to automatically retry a function call on specific Trakt exceptions."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Get the logger from the class instance (first argument)
            logger = args[0].log if args and hasattr(args[0], 'log') else print
            
            for i in range(1, retries + 1):
                try:
                    return fn(*args, **kwargs)
                except (RateLimitException, TraktInternalException) as e:
                    if i == retries:
                        logger(f"[ERROR] API call failed after {retries} retries: {e}")
                        raise
                    
                    wait_time = delay * i # Exponential backoff
                    logger(f"[WARN] API call failed with {type(e).__name__} (Attempt {i}/{retries}). Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        return wrapper
    return decorator