import traceback
from .SyncPlugin import SyncPlugin
from tqdm import tqdm
# --- FIX: Import from the correct state.py file ---
from state import SYNC_CANCEL_REQUESTED

class SyncRatingsPlugin(SyncPlugin):

    def run(self):
        sync_direction = self.config.get("SYNC_DIRECTION", "plex_to_trakt")
        self.log("[INFO] --- Running Ratings Sync ---")

        if sync_direction in ["plex_to_trakt", "bidirectional"]:
            self._sync_plex_to_trakt()
        
        if sync_direction in ["trakt_to_plex", "bidirectional"]:
            self._sync_trakt_to_plex()
        
        self.log("[INFO] --- Finished Ratings Sync ---")

    def _sync_plex_to_trakt(self):
        if SYNC_CANCEL_REQUESTED: return
        self.log("[PLEX->TRAKT] Syncing ratings from Plex to Trakt.")
        try:
            trakt_ratings_raw = self.trakt.get_ratings()
            trakt_ratings = {item[item['type']]['ids']['imdb']: item['rating'] for item in trakt_ratings_raw if item['type'] == 'movie'}
            trakt_ratings.update({f"tvdb_{item[item['type']]['ids']['tvdb']}": item['rating'] for item in trakt_ratings_raw if item['type'] == 'show' and item['show']['ids'].get('tvdb')})
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt ratings: {e}"); return
        
        payload = {"movies": [], "shows": []}
        library_ids = self.config.get("PLEX_LIBRARIES", [])
        plex_items = self.plex.get_all_items_from_libraries(library_ids)

        for item in tqdm(plex_items, desc="Scanning Plex for ratings", leave=False):
            if SYNC_CANCEL_REQUESTED: break
            if not hasattr(item, 'userRating'): continue
            plex_rating = int(item.userRating)
            
            if item.type == 'movie':
                imdb_id = next((g.id.split('//')[1] for g in item.guids if 'imdb' in g.id), None)
                if imdb_id and (imdb_id not in trakt_ratings or trakt_ratings[imdb_id] != plex_rating):
                    payload["movies"].append({"ids": {"imdb": imdb_id}, "rating": plex_rating})
            elif item.type == 'show':
                tvdb_id = next((g.id.split('//')[1] for g in item.guids if 'tvdb' in g.id), None)
                if tvdb_id and (f"tvdb_{tvdb_id}" not in trakt_ratings or trakt_ratings[f"tvdb_{tvdb_id}"] != plex_rating):
                    payload["shows"].append({"ids": {"tvdb": tvdb_id}, "rating": plex_rating})
        
        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return
        if payload["movies"] or payload["shows"]:
            self.log(f"[PLEX->TRAKT] Found {len(payload['movies'])} movies and {len(payload['shows'])} shows to rate on Trakt.")
            self.trakt.add_ratings(payload)
        else:
            self.log("[PLEX->TRAKT] No new Plex ratings to sync.")

    def _sync_trakt_to_plex(self):
        if SYNC_CANCEL_REQUESTED: return
        self.log("[TRAKT->PLEX] Syncing ratings from Trakt to Plex.")
        try:
            trakt_ratings = self.trakt.get_ratings()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt ratings: {e}"); return

        library_ids = self.config.get("PLEX_LIBRARIES", [])
        plex_items = self.plex.get_all_items_from_libraries(library_ids)
        
        for item in tqdm(plex_items, desc="Applying Trakt ratings to Plex", leave=False):
            if SYNC_CANCEL_REQUESTED: break
            if hasattr(item, 'userRating'): continue

            trakt_rating, matched_id = None, None
            item_data = None
            if item.type == 'movie':
                imdb_id = next((g.id.split('//')[1] for g in item.guids if 'imdb' in g.id), None)
                if imdb_id:
                    item_data = next((tr for tr in trakt_ratings if tr['type'] == 'movie' and tr['movie']['ids'].get('imdb') == imdb_id), None)
            elif item.type == 'show':
                tvdb_id = next((g.id.split('//')[1] for g in item.guids if 'tvdb' in g.id), None)
                if tvdb_id:
                    item_data = next((tr for tr in trakt_ratings if tr['type'] == 'show' and tr['show']['ids'].get('tvdb') == int(tvdb_id)), None)

            if item_data:
                try: item.rate(item_data['rating'])
                except Exception as e: self.log(f"[ERROR] Failed to rate '{item.title}' in Plex: {e}")