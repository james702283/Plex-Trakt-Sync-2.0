# state.py
from threading import Lock

# --- LIVE SYNC STATE ---
# This dictionary holds the real-time status of a sync in progress.
SYNC_PROGRESS_STATS = {"status": "idle", "current_library": "N/A"}

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