from .SyncPlugin import SyncPlugin
from tqdm import tqdm
from state import SYNC_CANCEL_REQUESTED

class WatchListPlugin(SyncPlugin):
    # This is now ONLY used when syncing from Trakt TO Plex
    WATCHLIST_COLLECTION_NAME = "Trakt Watchlist" 

    def run(self):
        sync_direction = self.config.get("SYNC_DIRECTION", "plex_to_trakt")
        self.log("[INFO] --- Running Watchlist Sync ---")

        if sync_direction in ["trakt_to_plex", "bidirectional"]:
            self._sync_trakt_to_plex()
        
        if sync_direction in ["plex_to_trakt", "bidirectional"]:
            self._sync_plex_to_trakt_universal() # Use the new, improved method
        
        self.log("[INFO] --- Finished Watchlist Sync ---")

    def _sync_plex_to_trakt_universal(self):
        """
        NEW & IMPROVED: This method syncs the BUILT-IN Plex universal Watchlist to Trakt.
        It no longer requires a manual collection.
        """
        if SYNC_CANCEL_REQUESTED: return
        self.log("[PLEX->TRAKT] Syncing your built-in Plex Watchlist to Trakt.")
        
        try:
            plex_watchlist_items = self.plex.get_plex_watchlist()
            if not plex_watchlist_items:
                self.log("[INFO] Your Plex Watchlist is empty. Nothing to sync to Trakt.")
                return
        except Exception as e:
            self.log(f"[ERROR] Could not fetch the Plex Watchlist for sync: {e}")
            return
            
        try:
            trakt_watchlist_items = self.trakt.get_watchlist()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt watchlist for comparison: {e}"); return

        # Get the IDs from the Plex items
        plex_ids_imdb = {next((g.id.split('//')[1] for g in item.guids if 'imdb' in g.id), None) for item in plex_watchlist_items if item.type == 'movie'}
        plex_ids_tvdb = {next((g.id.split('//')[1] for g in item.guids if 'tvdb' in g.id), None) for item in plex_watchlist_items if item.type == 'show'}

        # Get the IDs from the Trakt items, ensuring we handle strings for comparison
        trakt_ids_imdb = {item['movie']['ids'].get('imdb') for item in trakt_watchlist_items if item.get('type') == 'movie'}
        trakt_ids_tvdb = {str(item['show']['ids'].get('tvdb')) for item in trakt_watchlist_items if item.get('type') == 'show'}
        
        movies_to_add = [{"ids": {"imdb": imdb_id}} for imdb_id in plex_ids_imdb if imdb_id and imdb_id not in trakt_ids_imdb]
        shows_to_add = [{"ids": {"tvdb": tvdb_id}} for tvdb_id in plex_ids_tvdb if tvdb_id and tvdb_id not in trakt_ids_tvdb]

        if movies_to_add or shows_to_add:
            self.log(f"[PLEX->TRAKT] Adding {len(movies_to_add)} movies and {len(shows_to_add)} shows to Trakt watchlist.")
            payload = {"movies": movies_to_add, "shows": shows_to_add}
            try:
                self.trakt.add_to_watchlist(payload)
            except Exception as e:
                self.log(f"[ERROR] Failed to add items to Trakt watchlist: {e}")
        else:
            self.log("[PLEX->TRAKT] Trakt watchlist is already in sync with your Plex Watchlist.")

        # For bidirectional sync, remove items from Trakt that are not in the Plex watchlist
        if self.config.get("SYNC_DIRECTION") == "bidirectional":
            movies_to_remove = [{"ids": {"imdb": imdb_id}} for imdb_id in trakt_ids_imdb if imdb_id and imdb_id not in plex_ids_imdb]
            shows_to_remove = [{"ids": {"tvdb": tvdb_id}} for tvdb_id in trakt_ids_tvdb if tvdb_id and str(tvdb_id) not in plex_ids_tvdb]
            if movies_to_remove or shows_to_remove:
                self.log(f"[PLEX->TRAKT] Removing {len(movies_to_remove)} movies and {len(shows_to_remove)} shows from Trakt watchlist.")
                payload = {"movies": movies_to_remove, "shows": shows_to_remove}
                try:
                    self.trakt.remove_from_watchlist(payload)
                except Exception as e:
                    self.log(f"[ERROR] Failed to remove items from Trakt watchlist: {e}")

    def _sync_trakt_to_plex(self):
        """
        This method syncs the Trakt watchlist TO a Plex collection named "Trakt Watchlist".
        This behavior remains the same for users who prefer this direction.
        """
        if SYNC_CANCEL_REQUESTED: return
        self.log(f"[TRAKT->PLEX] Syncing Trakt watchlist to a Plex collection named '{self.WATCHLIST_COLLECTION_NAME}'.")
        try:
            watchlist_items = self.trakt.get_watchlist()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt watchlist: {e}"); return
        
        library_ids = self.config.get("PLEX_LIBRARIES", [])
        if not library_ids:
            self.log("[WARN] No Plex libraries configured. Skipping Trakt->Plex watchlist sync.")
            return

        plex_items = self.plex.get_all_items_from_libraries(library_ids)
        plex_lookup = {g.id: item for item in plex_items for g in item.guids if g.id}
        
        items_for_collection = []
        for trakt_item in tqdm(watchlist_items, desc="Matching Trakt watchlist to Plex", leave=False, file=self.TqdmToLog()):
            if SYNC_CANCEL_REQUESTED: break
            
            item_type = trakt_item.get('type')
            ids = trakt_item.get(item_type, {}).get('ids', {})
            if not ids: continue
            
            guid_map = {
                'imdb': f"imdb://{ids.get('imdb')}", 'tmdb': f"tmdb://{ids.get('tmdb')}",
                'tvdb': f"tvdb://{ids.get('tvdb')}"
            }

            for guid in guid_map.values():
                if guid in plex_lookup:
                    items_for_collection.append(plex_lookup[guid]); break
        
        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return
        self._manage_plex_collection(items_for_collection, int(library_ids[0]))

    def _manage_plex_collection(self, items_for_collection, library_id):
        if not items_for_collection and self.config.get("SYNC_DIRECTION") != "bidirectional":
            self.log(f"[INFO] No matched items to create or update Plex collection '{self.WATCHLIST_COLLECTION_NAME}'."); return
        
        target_library = self.plex.server.library.sectionByID(library_id)
        try:
            collection = self.plex.get_collection(self.WATCHLIST_COLLECTION_NAME, target_library)
            if not collection:
                if items_for_collection:
                    self.log(f"[PLEX] Creating '{self.WATCHLIST_COLLECTION_NAME}' collection...")
                    self.plex.create_collection(self.WATCHLIST_COLLECTION_NAME, target_library, items_for_collection)
                else:
                    self.log(f"[INFO] No items to add, so skipping creation of '{self.WATCHLIST_COLLECTION_NAME}' collection.")
                return

            plex_set = {item.ratingKey for item in collection.items()}
            trakt_set = {item.ratingKey for item in items_for_collection}
            
            to_add = [i for i in items_for_collection if i.ratingKey in (trakt_set - plex_set)]
            to_remove = [self.plex.get_item_by_rating_key(key) for key in (plex_set - trakt_set)]

            if to_add:
                collection.addItems(to_add); self.log(f"[PLEX] Added {len(to_add)} items to '{self.WATCHLIST_COLLECTION_NAME}' collection.")
            if to_remove:
                collection.removeItems([i for i in to_remove if i is not None]); self.log(f"[PLEX] Removed {len(to_remove)} items from '{self.WATCHLIST_COLLECTION_NAME}' collection.")
        except Exception as e:
            self.log(f"[ERROR] Failed to manage Plex collection '{self.WATCHLIST_COLLECTION_NAME}': {e}")