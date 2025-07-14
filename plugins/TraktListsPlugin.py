from .SyncPlugin import SyncPlugin
from tqdm import tqdm
from state import SYNC_CANCEL_REQUESTED
import re

class TraktListsPlugin(SyncPlugin):
    def run(self):
        self.log("[INFO] --- Running Custom Trakt Lists Sync ---")
        
        try:
            trakt_lists = self.trakt.get_user_lists()
        except Exception as e:
            self.log(f"[ERROR] Could not fetch custom lists from Trakt: {e}")
            return
        
        if not trakt_lists:
            self.log("[INFO] No custom lists found on your Trakt profile.")
            return
        
        self.log(f"[INFO] Found {len(trakt_lists)} custom lists to sync to Plex.")

        library_ids = self.config.get("PLEX_LIBRARIES", [])
        if not library_ids:
            self.log("[WARN] No Plex libraries configured. Skipping list sync.")
            return

        plex_items = self.plex.get_all_items_from_libraries(library_ids)
        plex_lookup = {g.id: item for item in plex_items for g in item.guids if g.id}
        
        for trakt_list in tqdm(trakt_lists, desc="Syncing Custom Lists", leave=False, file=self.TqdmToLog()):
            if SYNC_CANCEL_REQUESTED: break
            
            list_name = trakt_list.get('name', f"Trakt List {trakt_list.get('ids', {}).get('trakt')}")
            list_id = trakt_list.get('ids', {}).get('trakt')
            if not list_id: continue
            
            try:
                # Use default username 'me' for personal lists
                list_items = self.trakt.get_list_items(list_id)
            except Exception as e:
                self.log(f"[ERROR] Could not fetch items for list '{list_name}': {e}")
                continue
            
            items_for_collection = self._match_items(list_items, plex_lookup)
            self._manage_plex_collection(list_name, items_for_collection, int(library_ids[0]))

        self.log("[INFO] --- Finished Custom Trakt Lists Sync ---")
    
    def _match_items(self, trakt_items, plex_lookup):
        items_for_collection = []
        for trakt_item in trakt_items:
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
        return items_for_collection

    def _manage_plex_collection(self, name, items, library_id):
        collection_name = re.sub(r'[^\w\s-]', '', name).strip()
        if not collection_name: collection_name = "Untitled Trakt List"

        if not items:
            self.log(f"[INFO] No matched Plex items for list '{name}'. Skipping collection creation."); return
        
        target_library = self.plex.server.library.sectionByID(library_id)
        try:
            collection = self.plex.get_collection(collection_name, target_library)
            if not collection:
                self.log(f"[PLEX] Creating '{collection_name}' collection for list '{name}'.")
                self.plex.create_collection(collection_name, target_library, items)
                return

            plex_set = {item.ratingKey for item in collection.items()}
            trakt_set = {item.ratingKey for item in items}
            
            to_add = [i for i in items if i.ratingKey in (trakt_set - plex_set)]
            to_remove = [self.plex.get_item_by_rating_key(key) for key in (plex_set - trakt_set)]

            if to_add:
                collection.addItems(to_add); self.log(f"[PLEX] Added {len(to_add)} items to '{collection_name}'.")
            if to_remove:
                collection.removeItems([i for i in to_remove if i]); self.log(f"[PLEX] Removed {len(to_remove)} items from '{collection_name}'.")
        except Exception as e:
            self.log(f"[ERROR] Failed to manage Plex collection for list '{name}': {e}")