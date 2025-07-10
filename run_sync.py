import traceback
from state import SYNC_CANCEL_REQUESTED

def run_plugins(plex, trakt, config, log, TqdmToLog):
    if not config.get("PLEX_LIBRARIES"):
        log("[WARN] No Plex libraries configured for sync. Aborting.")
        return

    plugin_map = {
        "SYNC_WATCH_HISTORY": "plugins.SyncWatchedPlugin.SyncWatchedPlugin",
        "SYNC_RATINGS": "plugins.SyncRatingsPlugin.SyncRatingsPlugin",
        "SYNC_WATCHLIST": "plugins.WatchListPlugin.WatchListPlugin",
        "SYNC_WATCH_PROGRESS": "plugins.WatchProgressPlugin.WatchProgressPlugin",
    }

    for feature_flag, plugin_path in plugin_map.items():
        if SYNC_CANCEL_REQUESTED:
            log("[CANCEL] Sync cancelled by user. Halting further plugins.")
            break
        
        if config.get(feature_flag, False):
            try:
                parts = plugin_path.split('.')
                module_path = ".".join(parts[:-1])
                class_name = parts[-1]
                module = __import__(module_path, fromlist=[class_name])
                PluginClass = getattr(module, class_name)
                
                plugin_instance = PluginClass(plex, trakt, config, log, TqdmToLog=TqdmToLog)
                plugin_instance.run()

            except Exception as e:
                log(f"[ERROR] Unhandled exception in {plugin_path}: {e}")
                log(traceback.format_exc())
        else:
            log(f"[INFO] Skipping {feature_flag.replace('_', ' ')} as it's not enabled in settings.")