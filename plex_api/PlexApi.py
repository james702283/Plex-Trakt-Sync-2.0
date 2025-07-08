# plex_api/PlexApi.py
import uuid
import requests
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized

class PlexApi:
    def __init__(self, baseurl, token, log):
        self._baseurl = baseurl
        self._token = token
        self.log = log
        self._server = None

    @property
    def server(self):
        if self._server is None:
            if not self._baseurl or not self._token:
                raise ValueError("Plex URL and Token must be configured to access the server.")
            try:
                self._server = PlexServer(self._baseurl, self._token)
            except Unauthorized:
                raise Exception("Plex token is invalid or has expired.")
            except Exception as e:
                raise Exception(f"Failed to connect to Plex server: {e}")
        return self._server

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