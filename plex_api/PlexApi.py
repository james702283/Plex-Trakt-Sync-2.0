import uuid
import requests
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound

class PlexApi:
    def __init__(self, baseurl, token, log):
        self._baseurl = baseurl
        self._token = token
        self.log = log
        self._server = None

    @property
    def server(self):
        if self.is_configured and self._server is None:
            try:
                self._server = PlexServer(self._baseurl, self._token, timeout=30)
            except Unauthorized:
                raise Exception("Plex token is invalid or has expired.")
            except Exception as e:
                raise Exception(f"Failed to connect to Plex server: {e}")
        return self._server
        
    @property
    def is_configured(self):
        return bool(self._baseurl and self._token)

    def get_pin(self, client_identifier):
        headers = {
            "X-Plex-Product": "Plex-Trakt-Sync-v4",
            "X-Plex-Client-Identifier": client_identifier,
            "Accept": "application/json",
        }
        url = "https://plex.tv/api/v2/pins"
        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def check_pin(self, pin_id, client_identifier):
        headers = {
            "X-Plex-Product": "Plex-Trakt-Sync-v4",
            "X-Plex-Client-Identifier": client_identifier,
            "Accept": "application/json",
        }
        url = f"https://plex.tv/api/v2/pins/{pin_id}"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {"auth_token": data.get('authToken'), "authorized": bool(data.get('authToken'))}
        elif response.status_code == 404:
            return {"error": "PIN expired or claimed.", "race_condition": True}
        else:
            response.raise_for_status()

    def get_libraries(self):
        return [{"id": s.key, "title": s.title, "type": s.type} for s in self.server.library.sections() if s.type in ['movie', 'show']]

    def get_library_items(self, section_key):
        return self.server.library.sectionByID(section_key).all()

    def get_item_by_rating_key(self, rating_key):
        try:
            return self.server.fetchItem(rating_key)
        except NotFound:
            return None

    def get_collection(self, title, library):
        try:
            return library.collection(title)
        except NotFound:
            return None

    def create_collection(self, title, library, items_to_add):
        if items_to_add:
            return library.createCollection(title=title, items=items_to_add)
        self.log(f"[WARN] No items provided to create collection '{title}'.")
        return None

    def get_all_items_from_libraries(self, library_keys):
        all_items = []
        for key in library_keys:
            try:
                all_items.extend(self.server.library.sectionByID(int(key)).all())
            except Exception as e:
                self.log(f"[WARN] Could not fetch items from library {key}: {e}")
        return all_items

    ## FIX: This function is now 100% accurate. It counts every movie and episode.
    def get_total_item_count(self, library_keys):
        if not self.is_configured:
            return 0
        
        total_count = 0
        for key in library_keys:
            try:
                section = self.server.library.sectionByID(int(key))
                if section.type == 'movie':
                    total_count += section.totalSize
                elif section.type == 'show':
                    # For shows, we must count the episodes to be accurate
                    self.log(f"Counting episodes in '{section.title}'...")
                    total_count += len(section.search(libtype='episode'))
            except Exception as e:
                self.log(f"[WARN] Could not get size of library {key}: {e}")
        return total_count