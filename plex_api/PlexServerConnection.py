# plex_api/PlexServerConnection.py

from plexapi.server import PlexServer
from plex_api.PlexLibrarySection import PlexLibrarySection

class PlexServerConnection:
    def __init__(self, base_url, token, log=None):
        self.base_url = base_url
        self.token = token
        self.log = log or []
        self.server = self.connect()

    def connect(self):
        try:
            server = PlexServer(self.base_url, self.token)
            self.log.append("[info] Connected to Plex server successfully.")
            return server
        except Exception as e:
            self.log.append(f"[error] Failed to connect to Plex server: {e}")
            raise

    def get_sections(self):
        try:
            sections = self.server.library.sections()
            return [PlexLibrarySection(section) for section in sections]
        except Exception as e:
            self.log.append(f"[error] Failed to fetch library sections: {e}")
            return []
