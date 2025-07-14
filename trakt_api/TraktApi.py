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
        
        self._is_authenticated = False
        if oauth_token_data and 'access_token' in oauth_token_data:
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
        self.log("[INFO] Fetching full watched history from Trakt API via paginated history endpoint...")
        watched_movies_imdb = set()
        watched_episodes_trakt = set()
        
        try:
            page = 1
            while True:
                url = urljoin(TRAKT_API_URL, f"sync/history/movies?page={page}&limit=1000&extended=full")
                response = requests.get(url, headers=self._get_headers(), timeout=30)
                if response.status_code == 404: break 
                response.raise_for_status()
                data = response.json()
                if not data: break
                
                # --- ADDED: Pagination Logging ---
                page_count = response.headers.get('X-Pagination-Page-Count', '?')
                self.log(f"[INFO] Fetched page {page}/{page_count} of movie history, found {len(data)} items.")

                for item in data:
                    if item.get('movie', {}).get('ids', {}).get('imdb'):
                        watched_movies_imdb.add(item['movie']['ids']['imdb'])
                if 'X-Pagination-Page-Count' in response.headers and page >= int(response.headers['X-Pagination-Page-Count']): break
                page += 1
                time.sleep(0.5)
        except Exception as e:
            self.log(f"[ERROR] Failed while fetching watched movie history: {e}")

        try:
            page = 1
            while True:
                url = urljoin(TRAKT_API_URL, f"sync/history/shows?page={page}&limit=1000&extended=full")
                response = requests.get(url, headers=self._get_headers(), timeout=30)
                if response.status_code == 404: break
                response.raise_for_status()
                data = response.json()
                if not data: break
                
                # --- ADDED: Pagination Logging ---
                page_count = response.headers.get('X-Pagination-Page-Count', '?')
                self.log(f"[INFO] Fetched page {page}/{page_count} of show history, found {len(data)} items.")

                for item in data:
                    if item.get('episode', {}).get('ids', {}).get('trakt'):
                        watched_episodes_trakt.add(item['episode']['ids']['trakt'])
                if 'X-Pagination-Page-Count' in response.headers and page >= int(response.headers['X-Pagination-Page-Count']): break
                page += 1
                time.sleep(0.5)
        except Exception as e:
            self.log(f"[ERROR] Failed while fetching watched episode history: {e}")

        self.log(f"[INFO] Found {len(watched_movies_imdb)} movies and {len(watched_episodes_trakt)} episodes in Trakt history.")
        return watched_movies_imdb, watched_episodes_trakt

    @retry()
    def find_show_by_tvdb_id(self, tvdb_id):
        # --- ADDED: This method was missing, causing the crash. ---
        self.log(f"[INFO] Searching for show with TVDB ID: {tvdb_id}")
        url = urljoin(TRAKT_API_URL, f"search/tvdb/{tvdb_id}?type=show")
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0].get('show') # The API returns a list, we want the 'show' object from the first result.
        return None

    @retry()
    def get_ratings(self, media_type='all'):
        url = urljoin(TRAKT_API_URL, f"sync/ratings/{media_type}?extended=full")
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
        url = urljoin(TRAKT_API_URL, "sync/history")
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def add_ratings(self, payload):
        url = urljoin(TRAKT_API_URL, "sync/ratings")
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def add_to_watchlist(self, payload):
        url = urljoin(TRAKT_API_URL, "sync/watchlist")
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def remove_from_watchlist(self, payload):
        url = urljoin(TRAKT_API_URL, "sync/watchlist/remove")
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def get_collection(self, media_type):
        url = urljoin(TRAKT_API_URL, f"sync/collection/{media_type}?extended=full")
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def add_to_collection(self, payload):
        url = urljoin(TRAKT_API_URL, "sync/collection")
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def remove_from_collection(self, payload):
        url = urljoin(TRAKT_API_URL, "sync/collection/remove")
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @retry()
    def get_user_lists(self):
        url = urljoin(TRAKT_API_URL, "users/me/lists")
        response = requests.get(url, headers=self._get_headers(), timeout=20)
        response.raise_for_status()
        return response.json()
        
    @retry()
    def get_liked_lists(self):
        all_lists = []
        page = 1
        while True:
            url = urljoin(TRAKT_API_URL, f"users/likes/lists?page={page}&limit=100")
            response = requests.get(url, headers=self._get_headers(), timeout=20)
            if response.status_code == 404: break
            response.raise_for_status()
            data = response.json()
            if not data: break
            all_lists.extend(data)
            if 'X-Pagination-Page-Count' in response.headers and page >= int(response.headers['X-Pagination-Page-Count']):
                break
            page += 1
            time.sleep(0.5)
        return all_lists

    @retry()
    def get_list_items(self, list_id, username='me'):
        all_items = []
        page = 1
        while True:
            url = urljoin(TRAKT_API_URL, f"users/{username}/lists/{list_id}/items?page={page}&limit=1000&extended=full")
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            if response.status_code == 404: break
            response.raise_for_status()
            data = response.json()
            if not data: break
            all_items.extend(data)
            if 'X-Pagination-Page-Count' in response.headers and page >= int(response.headers['X-Pagination-Page-Count']):
                break
            page += 1
            time.sleep(0.5)
        return all_items
        
    def get_watched_history_for_ui(self):
        self.log("[UI] Fetching recent history for UI display...")
        all_items = []
        page = 1
        max_pages = 2 
        
        while page <= max_pages:
            try:
                url = urljoin(TRAKT_API_URL, f"sync/history?page={page}&limit=100&extended=full")
                response = requests.get(url, headers=self._get_headers(), timeout=20)
                if response.status_code == 404: break
                response.raise_for_status()
                data = response.json()
                if not data: break
                all_items.extend(data)
                if 'X-Pagination-Page-Count' in response.headers and page >= int(response.headers['X-Pagination-Page-Count']):
                    break
                page += 1
            except Exception as e:
                self.log(f"[ERROR] Failed while fetching UI history page {page}: {e}")
                break 

        ui_items = []
        for item in all_items:
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
                self.log(f"[WARN] Failed to process a history item for UI. Error: {e}")
        return ui_items