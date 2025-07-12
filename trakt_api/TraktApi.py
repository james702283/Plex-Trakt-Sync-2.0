import trakt
import trakt.sync
import trakt.users
from trakt.tv import TVShow
from trakt.errors import TraktException
import requests 
import time
from datetime import datetime
from .decorators import retry
from urllib.parse import urljoin

TRAKT_API_URL = "https://api.trakt.tv/"

class TraktApi:
    def __init__(self, client_id, client_secret, log, oauth_token_data=None):
        self.log = log
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_token_data = oauth_token_data
        
        trakt.core.BASE_URL = TRAKT_API_URL
        trakt.core.CLIENT_ID = client_id
        trakt.core.CLIENT_SECRET = client_secret
        
        self._is_authenticated = False
        if oauth_token_data and 'access_token' in oauth_token_data:
            trakt.core.OAUTH_TOKEN = oauth_token_data['access_token']
            self._is_authenticated = True
            self.log("[INFO] TraktApi: Initialized with existing token.")
        else:
            self.log("[WARN] TraktApi: No existing OAuth token found.")

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
    def initiate_device_auth(self):
        url = urljoin(TRAKT_API_URL, "oauth/device/code")
        payload = {"client_id": self.client_id}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    @retry()
    def check_device_auth(self, device_code):
        url = urljoin(TRAKT_API_URL, "oauth/device/token")
        payload = {"code": device_code, "client_id": self.client_id, "client_secret": self.client_secret}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200: return response.json()
        elif response.status_code == 400: return None
        else: response.raise_for_status(); return None

    @retry()
    def get_watched_history(self):
        # --- DEFINITIVE FIX: The previous methods were unreliable. This version uses the paginated
        # /sync/history endpoint directly, which is the most stable way to get a complete list of all
        # watched plays. This prevents the app from receiving an incomplete history, which was the
        # root cause of the duplicate syncs.
        self.log("[INFO] Fetching full watched history from Trakt API via paginated history endpoint...")
        watched_movies_imdb = set()
        watched_episodes_trakt = set()
        
        # 1. Get all watched movie history pages
        try:
            page = 1
            while True:
                self.log(f"Fetching movie history page {page}...")
                url = urljoin(TRAKT_API_URL, f"sync/history/movies?page={page}&limit=1000&extended=full")
                response = requests.get(url, headers=self._get_headers(), timeout=30)
                if response.status_code == 404: break 
                response.raise_for_status()
                
                data = response.json()
                if not data: break
                
                for item in data:
                    if item.get('movie', {}).get('ids', {}).get('imdb'):
                        watched_movies_imdb.add(item['movie']['ids']['imdb'])
                
                if 'X-Pagination-Page-Count' in response.headers and page >= int(response.headers['X-Pagination-Page-Count']):
                    break
                page += 1
                time.sleep(0.5) # Be nice to the API
        except Exception as e:
            self.log(f"[ERROR] Failed while fetching watched movie history: {e}")

        # 2. Get all watched episode history pages
        try:
            page = 1
            while True:
                self.log(f"Fetching episode history page {page}...")
                url = urljoin(TRAKT_API_URL, f"sync/history/shows?page={page}&limit=1000&extended=full")
                response = requests.get(url, headers=self._get_headers(), timeout=30)
                if response.status_code == 404: break
                response.raise_for_status()

                data = response.json()
                if not data: break

                for item in data:
                    if item.get('episode', {}).get('ids', {}).get('trakt'):
                        watched_episodes_trakt.add(item['episode']['ids']['trakt'])

                if 'X-Pagination-Page-Count' in response.headers and page >= int(response.headers['X-Pagination-Page-Count']):
                    break
                page += 1
                time.sleep(0.5) # Be nice to the API
        except Exception as e:
            self.log(f"[ERROR] Failed while fetching watched episode history: {e}")

        self.log(f"[INFO] Found {len(watched_movies_imdb)} movies and {len(watched_episodes_trakt)} episodes in Trakt history.")
        return watched_movies_imdb, watched_episodes_trakt

    def get_watched_history_for_ui(self):
        url = urljoin(TRAKT_API_URL, "sync/history?limit=100&extended=full")
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
        url = urljoin(TRAKT_API_URL, f"sync/ratings/{rating_type}?extended=full")
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def get_watchlist(self):
        url = urljoin(TRAKT_API_URL, "sync/watchlist?extended=full")
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def get_watch_progress(self):
        url = urljoin(TRAKT_API_URL, "sync/playback?extended=full")
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