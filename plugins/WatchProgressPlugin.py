import traceback
from .SyncPlugin import SyncPlugin
from tqdm import tqdm
# --- FIX: Import from the correct state.py file ---
from state import SYNC_CANCEL_REQUESTED

class WatchProgressPlugin(SyncPlugin):

    def run(self):
        sync_direction = self.config.get("SYNC_DIRECTION", "plex_to_trakt")
        self.log("[INFO] --- Running Watch Progress Sync ---")

        if sync_direction in ["trakt_to_plex", "bidirectional"]:
            self._sync_trakt_to_plex()
        
        if sync_direction in ["plex_to_trakt", "bidirectional"]:
             self.log("[INFO] Plex to Trakt progress sync is not part of this batch process.")
        
        self.log("[INFO] --- Finished Watch Progress Sync ---")

    def _sync_trakt_to_plex(self):
        if SYNC_CANCEL_REQUESTED: return
        self.log("[TRAKT->PLEX] Syncing watch progress from Trakt to Plex.")
        try:
            progress_items = self.trakt.get_watch_progress()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt watch progress: {e}"); return

        library_ids = self.config.get("PLEX_LIBRARIES", [])
        plex_items = self.plex.get_all_items_from_libraries(library_ids)
        plex_lookup = {g.id: item for item in plex_items for g in item.guids}
        
        for trakt_item in tqdm(progress_items, desc="Syncing playback progress", leave=False):
            if SYNC_CANCEL_REQUESTED: break
            
            ids = trakt_item[trakt_item['type']]['ids']
            progress = trakt_item.get('progress', 0)
            
            guid_map = {
                'imdb': f"imdb://{ids.get('imdb')}", 'tmdb': f"tmdb://{ids.get('tmdb')}",
                'tvdb': f"tvdb://{ids.get('tvdb')}"
            }
            
            plex_item = None
            for guid in guid_map.values():
                if guid in plex_lookup:
                    plex_item = plex_lookup[guid]; break
            
            if plex_item and plex_item.duration:
                new_view_offset = int((plex_item.duration * progress) / 100)
                if abs(new_view_offset - plex_item.viewOffset) > 30000:
                    try:
                        plex_item.updateProgress(new_view_offset)
                        self.log(f"[PLEX] Updated progress for '{plex_item.title}' to {progress}%.")
                    except Exception as e:
                        self.log(f"[ERROR] Failed to update progress for '{plex_item.title}': {e}")