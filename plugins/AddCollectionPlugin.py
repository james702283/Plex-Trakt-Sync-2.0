from .SyncPlugin import SyncPlugin
from tqdm import tqdm
from state import SYNC_CANCEL_REQUESTED

class AddCollectionPlugin(SyncPlugin):
    def run(self):
        self.log("[INFO] --- Running Add to Trakt Collection Sync ---")
        
        library_ids = self.config.get("PLEX_LIBRARIES", [])
        if not library_ids:
            self.log("[WARN] No Plex libraries configured. Skipping.")
            return

        self.log("[INFO] Fetching current Trakt collection...")
        try:
            # Trakt returns imdb as a string and tvdb as an integer. We will treat them as strings for consistency.
            trakt_movies = {item['movie']['ids'].get('imdb') for item in self.trakt.get_collection('movies') if item.get('movie')}
            trakt_shows = {str(item['show']['ids'].get('tvdb')) for item in self.trakt.get_collection('shows') if item.get('show')}
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt collection: {e}")
            return
            
        plex_items = self.plex.get_all_items_from_libraries(library_ids)
        movies_to_add, shows_to_add = [], []

        for item in tqdm(plex_items, desc="Scanning Plex libraries to add to collection", leave=False, file=self.TqdmToLog()):
            if SYNC_CANCEL_REQUESTED: break
            
            if item.type == 'movie':
                imdb_id = next((g.id.split('//')[1] for g in item.guids if 'imdb' in g.id), None)
                if imdb_id and imdb_id not in trakt_movies:
                    movies_to_add.append({"ids": {"imdb": imdb_id}})
                    trakt_movies.add(imdb_id) # Avoid duplicates in the same run
            elif item.type == 'show':
                tvdb_id = next((g.id.split('//')[1] for g in item.guids if 'tvdb' in g.id), None)
                # FIX: Consistently compare strings to strings
                if tvdb_id and tvdb_id not in trakt_shows:
                    shows_to_add.append({"ids": {"tvdb": tvdb_id}})
                    trakt_shows.add(tvdb_id) # Avoid duplicates

        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return
        
        if movies_to_add or shows_to_add:
            self.log(f"[INFO] Found {len(movies_to_add)} movies and {len(shows_to_add)} shows to add to Trakt collection.")
            payload = {"movies": movies_to_add, "shows": shows_to_add}
            try:
                self.trakt.add_to_collection(payload)
                self.log("[SUCCESS] Submitted new items to Trakt collection.")
            except Exception as e:
                self.log(f"[ERROR] Failed to add items to Trakt collection: {e}")
        else:
            self.log("[INFO] Trakt collection is already up-to-date with your Plex libraries.")

        self.log("[INFO] --- Finished Add to Trakt Collection Sync ---")