from .SyncPlugin import SyncPlugin
from tqdm import tqdm
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
            trakt_ratings = self.trakt.get_ratings()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt ratings: {e}")
            return
        
        trakt_movie_ratings = {item['movie']['ids'].get('imdb'): item['rating'] for item in trakt_ratings if item.get('type') == 'movie' and item.get('movie', {}).get('ids', {}).get('imdb')}
        trakt_show_ratings = {item['show']['ids'].get('tvdb'): item['rating'] for item in trakt_ratings if item.get('type') == 'show' and item.get('show', {}).get('ids', {}).get('tvdb')}

        payload = {"movies": [], "shows": []}
        library_ids = self.config.get("PLEX_LIBRARIES", [])
        plex_items = self.plex.get_all_items_from_libraries(library_ids)

        for item in tqdm(plex_items, desc="Scanning Plex for ratings to sync", leave=False, file=self.TqdmToLog()):
            if SYNC_CANCEL_REQUESTED: break
            if item.userRating is None: continue
            
            plex_rating = int(item.userRating)
            
            if item.type == 'movie':
                imdb_id = next((g.id.split('//')[1] for g in item.guids if 'imdb' in g.id), None)
                if imdb_id and trakt_movie_ratings.get(imdb_id) != plex_rating:
                    payload["movies"].append({"ids": {"imdb": imdb_id}, "rating": plex_rating})
            elif item.type == 'show':
                tvdb_id_str = next((g.id.split('//')[1] for g in item.guids if 'tvdb' in g.id), None)
                if tvdb_id_str:
                    try:
                        tvdb_id = int(tvdb_id_str)
                        if trakt_show_ratings.get(tvdb_id) != plex_rating:
                            payload["shows"].append({"ids": {"tvdb": tvdb_id}, "rating": plex_rating})
                    except (ValueError, TypeError):
                        continue

        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return
        if payload["movies"] or payload["shows"]:
            self.log(f"[PLEX->TRAKT] Found {len(payload['movies'])} movies and {len(payload['shows'])} shows with new or changed ratings to sync to Trakt.")
            try:
                self.trakt.add_ratings(payload)
                self.log("[SUCCESS] Submitted ratings to Trakt.")
            except Exception as e:
                self.log(f"[ERROR] Failed to submit ratings to Trakt: {e}")
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

        plex_lookup_movies = {next((g.id.split('//')[1] for g in item.guids if 'imdb' in g.id), None): item for item in plex_items if item.type == 'movie'}
        plex_lookup_shows = {next((g.id.split('//')[1] for g in item.guids if 'tvdb' in g.id), None): item for item in plex_items if item.type == 'show'}

        for trakt_rating in tqdm(trakt_ratings, desc="Applying Trakt ratings to Plex", leave=False, file=self.TqdmToLog()):
            if SYNC_CANCEL_REQUESTED: break
            
            item_type = trakt_rating.get('type')
            rating = trakt_rating.get('rating')
            plex_item = None
            
            if item_type == 'movie':
                imdb_id = trakt_rating.get('movie', {}).get('ids', {}).get('imdb')
                if imdb_id and imdb_id in plex_lookup_movies:
                    plex_item = plex_lookup_movies[imdb_id]
            elif item_type == 'show':
                tvdb_id_str = str(trakt_rating.get('show', {}).get('ids', {}).get('tvdb'))
                if tvdb_id_str and tvdb_id_str in plex_lookup_shows:
                    plex_item = plex_lookup_shows[tvdb_id_str]

            if plex_item and plex_item.userRating != rating:
                try:
                    self.log(f"[TRAKT->PLEX] Rating '{plex_item.title}' as {rating}/10 on Plex.")
                    plex_item.rate(rating)
                except Exception as e:
                    self.log(f"[ERROR] Failed to rate '{plex_item.title}' in Plex: {e}")