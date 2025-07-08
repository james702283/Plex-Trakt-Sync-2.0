# run_sync.py
import traceback
from plugins.SyncWatchedPlugin import SyncWatchedPlugin

def run_plugins(plex, trakt, config, log):
    if not config.get("PLEX_LIBRARIES"):
        log("[WARN] No Plex libraries configured for sync. Aborting.")
        return [], []

    plugin = SyncWatchedPlugin(plex, trakt, config, log)
    log(f"--- Running Plugin: {plugin.__class__.__name__} ---")
    try:
        # Capture and return the results from the plugin for cache updating
        movies_synced, episodes_synced = plugin.run()
        log(f"--- Finished Plugin: {plugin.__class__.__name__} ---")
        return movies_synced, episodes_synced
    except Exception as e:
        log(f"[ERROR] Unhandled exception in plugin: {e}")
        log(traceback.format_exc())
        return [], []