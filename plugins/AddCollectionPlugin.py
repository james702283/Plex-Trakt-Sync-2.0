# plugins/AddCollectionPlugin.py
from .SyncPlugin import SyncPlugin

class AddCollectionPlugin(SyncPlugin):
    def run(self):
        self.log.append("[INFO] [AddCollectionPlugin] Starting sync...")

        library_ids_to_sync = self.run_config.libraries
        if not library_ids_to_sync:
            self.log.append("[WARN] [AddCollectionPlugin] No Plex libraries selected to sync. Skipping.")
            return

        collection_payload = {"movies": [], "shows": []}

        for section_id in library_ids_to_sync:
            plex_items = self.plex.get_library_items(section_id)
            for item in plex_items:
                item_type = item.get('type')
                title = item.get('title')
                year = item.get('year')
                
                # Find the correct ID for Trakt (IMDb, TMDB, etc.)
                guid = item.get('guid')
                imdb_id = None
                if guid and 'imdb://' in guid:
                    imdb_id = guid.split('imdb://')[1]

                if not imdb_id:
                    self.log.append(f"[WARN] [AddCollectionPlugin] Skipping '{title}' because no IMDb ID was found.")
                    continue

                formatted_item = {
                    "title": title,
                    "year": year,
                    "ids": {"imdb": imdb_id}
                }

                if item_type == 'movie':
                    collection_payload["movies"].append(formatted_item)
                elif item_type == 'show':
                    # Syncing shows requires more complex logic to handle seasons/episodes
                    # For now, we'll just log the show itself.
                    self.log.append(f"[INFO] [AddCollectionPlugin] Found show '{title}'. Per-episode collection sync not yet implemented.")

        if collection_payload["movies"]:
            try:
                self.log.append(f"[INFO] [AddCollectionPlugin] Adding {len(collection_payload['movies'])} movies to Trakt collection...")
                response = self.trakt.add_to_collection(collection_payload)
                added = response.get('added', {})
                self.log.append(f"[SUCCESS] [AddCollectionPlugin] Trakt response: Added {added.get('movies', 0)} movies.")
            except Exception as e:
                self.log.append(f"[ERROR] [AddCollectionPlugin] Failed to add movies to collection: {e}")

        self.log.append("[INFO] [AddCollectionPlugin] Sync complete.")