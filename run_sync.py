import traceback
from state import SYNC_CANCEL_REQUESTED

def run_plugins(plex, trakt, config, log, TqdmToLog):
    if not config.get("PLEX_LIBRARIES"):
        log("[WARN] No Plex libraries configured for sync. Aborting.")
        return

    # --- SPECIAL HANDLING FOR DESTRUCTIVE OPERATIONS ---
    # We run the Clear Collection plugin first if it's enabled.
    if config.get("CLEAR_TRAKT_COLLECTION", False):
        if SYNC_CANCEL_REQUESTED:
            log("[CANCEL] Sync cancelled before clearing collection.")
            return
        try:
            from plugins.ClearCollectedPlugin import ClearCollectedPlugin
            log("[INFO] --- Running Clear Trakt Collection ---")
            clear_plugin = ClearCollectedPlugin(plex, trakt, config, log, TqdmToLog=TqdmToLog)
            clear_plugin.run()
            log("[INFO] --- Finished Clearing Trakt Collection ---")
        except Exception as e:
            log(f"[ERROR] Unhandled exception in ClearCollectedPlugin: {e}")
            log(traceback.format_exc())

    # --- STANDARD SYNC PLUGINS ---
    plugin_map = {
        "SYNC_WATCH_HISTORY": "plugins.SyncWatchedPlugin.SyncWatchedPlugin",
        "SYNC_RATINGS": "plugins.SyncRatingsPlugin.SyncRatingsPlugin",
        "SYNC_WATCHLIST": "plugins.WatchListPlugin.WatchListPlugin",
        "SYNC_WATCH_PROGRESS": "plugins.WatchProgressPlugin.WatchProgressPlugin",
        "SYNC_TRAKT_COLLECTION": "plugins.AddCollectionPlugin.AddCollectionPlugin",
        "SYNC_CUSTOM_LISTS": "plugins.TraktListsPlugin.TraktListsPlugin",
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
                
                # The log messages are now handled within the plugin's run method for consistency.
                plugin_instance = PluginClass(plex, trakt, config, log, TqdmToLog=TqdmToLog)
                plugin_instance.run()

            except Exception as e:
                log(f"[ERROR] Unhandled exception in {plugin_path}: {e}")
                log(traceback.format_exc())
        else:
            # Provide info for skipped non-essential plugins that are disabled.
            log(f"[INFO] Skipping {feature_flag.replace('SYNC_', '').replace('_', ' ')} as it's not enabled in settings.")