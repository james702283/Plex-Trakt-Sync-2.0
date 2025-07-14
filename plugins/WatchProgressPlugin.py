from .SyncPlugin import SyncPlugin
from tqdm import tqdm
from state import SYNC_CANCEL_REQUESTED

class WatchProgressPlugin(SyncPlugin):

    def run(self):
        sync_direction = self.config.get("SYNC_DIRECTION", "plex_to_trakt")
        self.log("[INFO] --- Running Watch Progress Sync ---")

        if sync_direction in ["trakt_to_plex", "bidirectional"]:
            self._sync_trakt_to_plex()
        
        if sync_direction in ["plex_to_trakt", "bidirectional"]:
             self.log("[INFO] Plex to Trakt progress sync (scrobbling) is handled by clients, not by this batch sync process.")
        
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
        
        for trakt_item in tqdm(progress_items, desc="Syncing playback progress", leave=False, file=self.TqdmToLog()):
            if SYNC_CANCEL_REQUESTED: break
            
            item_type = trakt_item.get('type')
            ids = {}
            if item_type == 'episode':
                ids = trakt_item.get('episode', {}).get('ids', {})
            elif item_type == 'movie':
                ids = trakt_item.get('movie', {}).get('ids', {})
            
            if not ids: continue
            
            progress = trakt_item.get('progress', 0)
            
            guid_map = {
                'imdb': f"imdb://{ids.get('imdb')}", 
                'tmdb': f"tmdb://{ids.get('tmdb')}",
                'tvdb': f"tvdb://{ids.get('tvdb')}"
            }
            
            plex_item = None
            for guid in guid_map.values():
                if guid in plex_lookup:
                    plex_item = plex_lookup[guid]; break
            
            if plex_item and plex_item.duration and progress < 95: # Don't update fully watched items
                new_view_offset = int((plex_item.duration * progress) / 100)
                # Only update if progress differs by more than 30 seconds
                if abs(new_view_offset - (plex_item.viewOffset or 0)) > 30000: 
                    try:
                        plex_item.updateProgress(new_view_offset)
                        self.log(f"[PLEX] Updated progress for '{plex_item.title}' to {progress}%.")
                    except Exception as e:
                        self.log(f"[ERROR] Failed to update progress for '{plex_item.title}': {e}")