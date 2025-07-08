# plugins/SyncWatchedPlugin.py
import traceback
import time
from .SyncPlugin import SyncPlugin
from tqdm import tqdm
from trakt.tv import TVShow
from trakt.errors import TraktException

class SyncWatchedPlugin(SyncPlugin):
    def run(self):
        self.log("[INFO] Starting watched history sync with robust logic...")
        
        try:
            trakt_movie_ids, trakt_episode_ids = self.trakt.get_watched_history()
            self.log(f"[INFO] Found {len(trakt_movie_ids)} watched movies and {len(trakt_episode_ids)} watched episodes on Trakt.")
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt watched history: {e}")
            return [], [] # Return empty lists on error

        movies_to_sync = []
        episodes_to_sync = []
        library_ids = self.config.get("PLEX_LIBRARIES", [])

        if not library_ids:
            self.log("[WARN] No Plex libraries configured. Please select libraries in settings.")
            return [], [] # Return empty lists if no libraries

        for section_id_str in library_ids:
            section = self.plex.server.library.sectionByID(int(section_id_str))
            self.log(f"--- Processing Plex Library: '{section.title}' ({section.type}) ---")
            all_plex_items = section.all()
            progress_bar = tqdm(all_plex_items, desc=f"Scanning '{section.title}'", unit="item", dynamic_ncols=True, leave=False)

            if section.type == 'movie':
                for movie in progress_bar:
                    try:
                        if not movie.isPlayed: continue
                        imdb_id = next((guid.id.split('//')[1] for guid in movie.guids if 'imdb' in guid.id), None)
                        if not imdb_id or imdb_id in trakt_movie_ids: continue
                        movies_to_sync.append({"watched_at": movie.lastViewedAt.strftime('%Y-%m-%dT%H:%M:%S.000Z'), "ids": {"imdb": imdb_id}})
                    except Exception as e:
                        self.log(f"\n[ERROR] Skipping movie '{getattr(movie, 'title', 'N/A')}': {e}")

            elif section.type == 'show':
                for plex_show in progress_bar:
                    try:
                        show_tvdb_id = next((guid.id.split('//')[1] for guid in plex_show.guids if 'tvdb' in guid.id), None)
                        if not show_tvdb_id: continue

                        summary_show = self.trakt.find_show_by_tvdb_id(show_tvdb_id)
                        if not summary_show: continue
                        
                        trakt_show = TVShow(slug=summary_show.slug)
                        if not trakt_show or not trakt_show.seasons: continue

                        for plex_episode in plex_show.watched():
                            trakt_episode = next((ep for season in trakt_show.seasons if season.season == plex_episode.seasonNumber for ep in season.episodes if ep.number == plex_episode.index), None)
                            
                            if trakt_episode and trakt_episode.trakt not in trakt_episode_ids:
                                episodes_to_sync.append({"watched_at": plex_episode.lastViewedAt.strftime('%Y-%m-%dT%H:%M:%S.000Z'), "ids": {"trakt": trakt_episode.trakt}})
                    except Exception as e:
                        self.log(f"\n[ERROR] Skipping show '{plex_show.title}': {e}")

        # --- BATCH SUBMISSION LOGIC ---
        if movies_to_sync or episodes_to_sync:
            self.log(f"\n[INFO] Found {len(movies_to_sync)} movies and {len(episodes_to_sync)} episodes to sync.")
            batch_size = 500
            
            # Submit episodes in batches
            for i in range(0, len(episodes_to_sync), batch_size):
                batch = episodes_to_sync[i:i + batch_size]
                self.log(f"--- Submitting batch of {len(batch)} episodes ({i+len(batch)}/{len(episodes_to_sync)}) ---")
                response = self.trakt.add_to_history({"episodes": batch})
                self.log(f"Trakt response: {response}")
                time.sleep(1) # Pause between batches

            # Submit movies in batches
            for i in range(0, len(movies_to_sync), batch_size):
                batch = movies_to_sync[i:i + batch_size]
                self.log(f"--- Submitting batch of {len(batch)} movies ({i+len(batch)}/{len(movies_to_sync)}) ---")
                response = self.trakt.add_to_history({"movies": batch})
                self.log(f"Trakt response: {response}")
                time.sleep(1)

        else:
            self.log("\n[INFO] Sync complete. No new items to sync.")
        
        # --- MODIFIED: Return the lists of items that were queued for syncing ---
        return movies_to_sync, episodes_to_sync