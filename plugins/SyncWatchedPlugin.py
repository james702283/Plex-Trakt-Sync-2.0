import traceback
import time
from .SyncPlugin import SyncPlugin
from tqdm import tqdm
from trakt.tv import TVShow
from trakt.errors import TraktException, RateLimitException
import requests
from datetime import timezone
from tzlocal import get_localzone

from state import SYNC_CANCEL_REQUESTED, progress_lock
import state as app_state 

class SyncWatchedPlugin(SyncPlugin):

    def run(self):
        sync_direction = self.config.get("SYNC_DIRECTION", "plex_to_trakt")
        self.log("[INFO] --- Running Watched History Sync ---")

        if sync_direction in ["plex_to_trakt", "bidirectional"]:
            self._sync_plex_to_trakt()
        
        if sync_direction in ["trakt_to_plex", "bidirectional"]:
            self._sync_trakt_to_plex()
        
        self.log("[INFO] --- Finished Watched History Sync ---")

    def _sync_plex_to_trakt(self):
        if SYNC_CANCEL_REQUESTED: return
        self.log("[PLEX->TRAKT] Syncing watched history from Plex to Trakt.")
        
        try:
            trakt_movie_ids, trakt_episode_ids = self.trakt.get_watched_history()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt watched history: {e}")
            return

        movies_to_sync, episodes_to_sync = [], []
        library_ids = self.config.get("PLEX_LIBRARIES", [])
        
        local_tz = get_localzone()
        self.log(f"[INFO] Detected server timezone: {local_tz}")

        for section_id_str in library_ids:
            if SYNC_CANCEL_REQUESTED: break
            try:
                section = self.plex.server.library.sectionByID(int(section_id_str))
                all_plex_items = section.all()
                
                tqdm_out = self.TqdmToLog()
                progress_bar = tqdm(all_plex_items, desc=f"Scanning '{section.title}' for watched", unit="item", leave=False, file=tqdm_out)

                if section.type == 'movie':
                    for movie in progress_bar:
                        # --- FIX: Increment the "Items Scanned" counter ---
                        with progress_lock:
                            app_state.ITEMS_PROCESSED_COUNT += 1
                        if SYNC_CANCEL_REQUESTED: break
                        if not movie.isPlayed: continue
                        imdb_id = next((g.id.split('//')[1] for g in movie.guids if 'imdb' in g.id), None)
                        if imdb_id and imdb_id not in trakt_movie_ids:
                            aware_dt = movie.lastViewedAt.astimezone(local_tz).astimezone(timezone.utc)
                            watched_at_str = aware_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                            movies_to_sync.append({"watched_at": watched_at_str, "ids": {"imdb": imdb_id}})

                elif section.type == 'show':
                    for plex_show in progress_bar:
                        # --- FIX: Increment the "Items Scanned" counter ---
                        with progress_lock:
                            app_state.ITEMS_PROCESSED_COUNT += 1
                        if SYNC_CANCEL_REQUESTED: break
                        
                        show_tvdb_id = next((g.id.split('//')[1] for g in plex_show.guids if 'tvdb' in g.id), None)
                        if not show_tvdb_id: continue
                        
                        summary_show = self.trakt.find_show_by_tvdb_id(show_tvdb_id)
                        if not summary_show: continue
                        trakt_show = TVShow(slug=summary_show.slug)
                        if not hasattr(trakt_show, 'seasons'): continue
                        
                        for plex_episode in plex_show.watched():
                            if SYNC_CANCEL_REQUESTED: break
                            trakt_episode = next((ep for s in trakt_show.seasons for ep in s.episodes if s.season == plex_episode.seasonNumber and ep.number == plex_episode.index), None)
                            if trakt_episode and trakt_episode.trakt not in trakt_episode_ids:
                                aware_dt = plex_episode.lastViewedAt.astimezone(local_tz).astimezone(timezone.utc)
                                watched_at_str = aware_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                                episodes_to_sync.append({"watched_at": watched_at_str, "ids": {"trakt": trakt_episode.trakt}})
            except Exception as e:
                self.log(f"[ERROR] Could not process library ID {section_id_str}: {e}")

        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return
        if movies_to_sync or episodes_to_sync:
            self.log(f"[PLEX->TRAKT] Found {len(movies_to_sync)} movies and {len(episodes_to_sync)} episodes to sync to Trakt.")
            self._submit_to_trakt_history(movies_to_sync, "movies")
            self._submit_to_trakt_history(episodes_to_sync, "episodes")
        else:
            self.log("[PLEX->TRAKT] No new items to sync.")

    def _sync_trakt_to_plex(self):
        if SYNC_CANCEL_REQUESTED: return
        self.log("[TRAKT->PLEX] Syncing watched history from Trakt to Plex.")
        
        try:
            trakt_history = self.trakt.get_watched_history_for_ui()
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt watched history: {e}"); return

        library_ids = self.config.get("PLEX_LIBRARIES", [])
        plex_items = self.plex.get_all_items_from_libraries(library_ids)
        
        plex_lookup = {g.id: item for item in plex_items if not item.isPlayed for g in item.guids}
        
        items_to_mark = []
        tqdm_out = self.TqdmToLog()
        for trakt_item in tqdm(trakt_history, desc="Comparing Trakt history to Plex", leave=False, file=tqdm_out):
            if SYNC_CANCEL_REQUESTED: break
            ids = trakt_item.get('ids', {})
            plex_item = None
            
            guid_map = {
                'imdb': f"imdb://{ids.get('imdb')}", 'tmdb': f"tmdb://{ids.get('tmdb')}",
                'tvdb': f"tvdb://{ids.get('tvdb')}", 'trakt': f"trakt://{ids.get('trakt')}"
            }

            for id_type, guid in guid_map.items():
                if guid in plex_lookup:
                    plex_item = plex_lookup[guid]
                    break
            
            if plex_item:
                items_to_mark.append(plex_item)
                if 'imdb' in ids: del plex_lookup[guid_map['imdb']]
                
        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return
        if items_to_mark:
            self.log(f"[TRAKT->PLEX] Marking {len(items_to_mark)} items as watched on Plex.")
            tqdm_out_mark = self.TqdmToLog()
            for item in tqdm(items_to_mark, desc="Marking items on Plex", leave=False, file=tqdm_out_mark):
                if SYNC_CANCEL_REQUESTED: break
                try: item.markPlayed()
                except Exception as e: self.log(f"[ERROR] Failed to mark '{item.title}' as watched: {e}")
        else:
            self.log("[TRAKT->PLEX] Plex is already up to date.")

    def _submit_to_trakt_history(self, items, item_type):
        if not items: return
        batch_size = 500
        for i in range(0, len(items), batch_size):
            if SYNC_CANCEL_REQUESTED: break
            batch = items[i:i + batch_size]
            payload = {"movies" if item_type == "movies" else "episodes": batch}
            try:
                response = self.trakt.add_to_history(payload)
                self.log(f"Submitted batch of {len(batch)} {item_type} to Trakt.")
            except Exception as e:
                self.log(f"[ERROR] Failed to submit {item_type} batch to Trakt: {e}")
            time.sleep(1.1)