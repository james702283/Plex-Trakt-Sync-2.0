# state.py
from threading import Lock

# --- MODIFIED: Expanded state for the new UI ---
# This dictionary holds the real-time status of a sync in progress.
## FIX: Added 'current_item_name' and 'library_progress_text' for the new UI.
SYNC_PROGRESS_STATS = {
    "status": "idle",
    "current_library": "N/A",
    "is_syncing": False,
    "current_item_name": "", # Holds the real-time name of the show/movie
    # For the top "Current Library" bar
    "item": {
        "name": "",
        "progress_percent": 0,
        "progress_text": ""
    },
    # For the second "Overall Progress" bar
    "overall": {
        "progress_percent": 0,
        "progress_text": "",
        "library_progress_text": "" # Holds the "(1/3)" text
    },
    # For the bottom graph and text
    "rate": {
        "value_raw": 0,
        "text": "0 items/s"
    },
    "time": {
        "elapsed": "00:00",
        "remaining": "00:00"
    }
}


# --- LIVE LOGGING ---
# This list stores the log lines that are displayed in the UI.
LIVE_LOG_LINES = []

# --- ACCURATE COUNTER ---
# This variable will be incremented for each item scanned.
ITEMS_PROCESSED_COUNT = 0

# --- SYNC CONTROL ---
# This flag is used to signal that a sync cancellation has been requested.
SYNC_CANCEL_REQUESTED = False

# --- THREADING LOCKS ---
# These locks prevent race conditions when multiple threads access the shared state.
sync_lock = Lock()
log_lock = Lock()
progress_lock = Lock()