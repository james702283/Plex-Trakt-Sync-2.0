import traceback
from .SyncPlugin import SyncPlugin
from tqdm import tqdm
# --- FIX: Import from the correct state.py file ---
from state import SYNC_CANCEL_REQUESTED

class WatchListPlugin(SyncPlugin):
    WATCHLIST_COLLECTION_NAME = "Trakt Watchlist"

    def run(self):
        sync_direction = self.config.get("SYNC_DIRECTION", "plex_to_trakt")
        self.log("[INFO] --- Running Watchlist Sync ---")

        if sync_direction in ["trakt_to_plex", "bidirectional"]:
            self._sync_trakt_to_plex()
        
        if sync_direction in ["plex_to_trakt", "bidirectional"]:
            self._sync_plex_to_trakt()
        
        self.log("[INFO] --- Finished Watchlist Sync ---")

    def _sync_trakt_to_plex(self):
        if SYNC_CANCEL_REQUESTED: return
        self.log("[TRAKT->PLEX] Syncing Trakt watchlist to a Plex collection.")
        try:
            watchlist = self.trakt.get_watchlist()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt watchlist: {e}"); return
        
        library_ids = self.config.get("PLEX_LIBRARIES", [])
        plex_items = self.plex.get_all_items_from_libraries(library_ids)
        
        plex_lookup = {g.id: item for item in plex_items for g in item.guids}
        
        items_for_collection = []
        for trakt_item in tqdm(watchlist, desc="Matching Trakt watchlist to Plex", leave=False):
            if SYNC_CANCEL_REQUESTED: break
            ids = trakt_item[trakt_item['type']]['ids']
            guid_map = {
                'imdb': f"imdb://{ids.get('imdb')}", 'tmdb': f"tmdb://{ids.get('tmdb')}",
                'tvdb': f"tvdb://{ids.get('tvdb')}"
            }
            for guid in guid_map.values():
                if guid in plex_lookup:
                    items_for_collection.append(plex_lookup[guid]); break
        
        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return
        self._manage_plex_collection(items_for_collection, library_ids)

    def _sync_plex_to_trakt(self):
        if SYNC_CANCEL_REQUESTED: return
        self.log("[PLEX->TRAKT] Syncing Plex watchlist to Trakt.")
        self.log("[INFO] Plex to Trakt watchlist sync is not yet implemented in this version.")


    def _manage_plex_collection(self, items_for_collection, library_ids):
        if not items_for_collection:
            self.log("[INFO] No matched items to create or modify a collection."); return
        
        target_library = self.plex.server.library.sectionByID(int(library_ids[0]))
        try:
            collection = self.plex.get_collection(self.WATCHLIST_COLLECTION_NAME, target_library)
            if not collection:
                self.log(f"[PLEX] Creating '{self.WATCHLIST_COLLECTION_NAME}' collection...")
                self.plex.create_collection(self.WATCHLIST_COLLECTION_NAME, target_library, items_for_collection)
                return

            plex_set = {item.ratingKey for item in collection.items()}
            trakt_set = {item.ratingKey for item in items_for_collection}
            
            to_add_keys = trakt_set - plex_set
            to_remove_keys = plex_set - trakt_set

            if to_add_keys:
                items_to_add = [i for i in items_for_collection if i.ratingKey in to_add_keys]
                collection.addItems(items_to_add)
                self.log(f"[PLEX] Added {len(items_to_add)} items to collection.")
            
            if to_remove_keys:
                items_to_remove = [self.plex.get_item_by_rating_key(key) for key in to_remove_keys]
                collection.removeItems(items_to_remove)
                self.log(f"[PLEX] Removed {len(items_to_remove)} items from collection.")
        except Exception as e:
            self.log(f"[ERROR] Failed to manage Plex collection: {e}")