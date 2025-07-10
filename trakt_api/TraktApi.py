import trakt
import trakt.sync
import trakt.users
from trakt.tv import TVShow
from trakt.errors import TraktException
import requests 
import time
from datetime import datetime
from .decorators import retry

TRAKT_API_URL = "https://api.trakt.tv"

class TraktApi:
    def __init__(self, client_id, client_secret, log, oauth_token_data=None):
        self.log = log
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_token_data = oauth_token_data
        
        trakt.core.CLIENT_ID = client_id
        trakt.core.CLIENT_SECRET = client_secret
        
        self._is_authenticated = False
        if oauth_token_data and 'access_token' in oauth_token_data:
            trakt.core.OAUTH_TOKEN = oauth_token_data['access_token']
            try:
                self._try_auth()
            except Exception as e:
                self.log(f"[WARN] TraktApi: Failed to authenticate with existing token: {e}. Re-authorization may be needed.")
                self._is_authenticated = False

    def _get_headers(self):
        if not self.oauth_token_data or not self.oauth_token_data.get('access_token'):
            raise Exception("Trakt is not authenticated.")
        return {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.client_id,
            'Authorization': f"Bearer {self.oauth_token_data['access_token']}"
        }

    @retry()
    def _try_auth(self):
        trakt.users.User('me').username 
        self.log("[INFO] TraktApi: Successfully authenticated with existing token.")
        self._is_authenticated = True

    def initiate_device_auth(self):
        url = f"{TRAKT_API_URL}/oauth/device/code"
        payload = {"client_id": self.client_id}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def check_device_auth(self, device_code):
        url = f"{TRAKT_API_URL}/oauth/device/token"
        payload = {"code": device_code, "client_id": self.client_id, "client_secret": self.client_secret}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200: return response.json()
        elif response.status_code == 400: return None
        else: response.raise_for_status(); return None

    @retry()
    def get_watched_history(self):
        me = trakt.users.User('me')
        watched_movies_imdb = {m.ids['ids'].get('imdb') for m in me.watched_movies if m.ids and m.ids.get('ids') and m.ids['ids'].get('imdb')}
        
        watched_episodes_trakt = set()
        if me.watched_shows:
            for show_item in me.watched_shows:
                if not hasattr(show_item, 'seasons'): continue
                for season in show_item.seasons:
                    for ep in season.episodes:
                        if ep.ids and ep.ids.get('ids') and ep.ids['ids'].get('trakt'):
                             watched_episodes_trakt.add(ep.ids['ids']['trakt'])
        return watched_movies_imdb, watched_episodes_trakt

    def get_watched_history_for_ui(self):
        url = f"{TRAKT_API_URL}/sync/history?limit=200&extended=full"
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        history_data = response.json()

        ui_items = []
        for item in history_data:
            try:
                item_type = item.get('type')
                watched_at = item.get('watched_at')
                if item_type == 'movie':
                    movie_data = item.get('movie', {})
                    ui_items.append({"type": "movie", "title": movie_data.get('title'), "year": movie_data.get('year'), "ids": movie_data.get('ids', {}), "watched_at": watched_at})
                elif item_type == 'episode':
                    show_data = item.get('show', {})
                    episode_data = item.get('episode', {})
                    ui_items.append({"type": "episode", "show_title": show_data.get('title'), "season_number": episode_data.get('season'), "episode_number": episode_data.get('number'), "episode_title": episode_data.get('title'), "ids": show_data.get('ids', {}), "watched_at": watched_at})
            except Exception as e:
                self.log(f"[WARN] Failed to process a history item. Error: {e}")
        return ui_items

    @retry()
    def get_ratings(self, rating_type='all'):
        url = f"{TRAKT_API_URL}/sync/ratings/{rating_type}?extended=full"
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def get_watchlist(self):
        url = f"{TRAKT_API_URL}/sync/watchlist?extended=full"
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def get_watch_progress(self):
        url = f"{TRAKT_API_URL}/sync/playback?extended=full"
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def add_to_history(self, payload):
        return trakt.sync.add_to_history(payload)
        
    @retry()
    def add_ratings(self, payload):
        return trakt.sync.add_ratings(payload)

    @retry()
    def add_to_watchlist(self, payload):
        return trakt.sync.add_to_watchlist(payload)

    @retry()
    def remove_from_watchlist(self, payload):
        return trakt.sync.remove_from_watchlist(payload)
        
    @retry()
    def scrobble(self, payload):
         return trakt.sync.scrobble(**payload)

    @retry()
    def find_show_by_tvdb_id(self, tvdb_id):
        search_results = trakt.sync.search_by_id(tvdb_id, id_type='tvdb', media_type='show')
        return search_results[0] if search_results else None