# metadata/tmdb_api.py
import requests

# A smaller poster size is efficient for the UI grid
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w342"
POSTER_PLACEHOLDER = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzMDAiIGhlaWdodD0iNDUwIiB2aWV3Qm94PSIwIDAgMzAwIDQ1MCIgYmFja2dyb3VuZC1jb2xvcj0iIzMzMzMzMyI+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmb250LXNpemU9IjI0cHgiIGZpbGw9IiM5OTk5OTkiPk5vIFBvc3RlcjwvdGV4dD48L3N2Zz4="

class TMDbApi:
    def __init__(self, api_key, log):
        self.api_key = api_key
        self.log = log
        self.session = requests.Session()
        self.session.params = {"api_key": self.api_key}

    def get_poster(self, media_type, imdb_id=None, tmdb_id=None):
        # --- Verbose logging for debugging ---
        self.log(f"[TMDB_API] Attempting to get poster for media_type='{media_type}', imdb_id='{imdb_id}', tmdb_id='{tmdb_id}'")

        if not self.api_key:
            self.log("[TMDB_API] No API key provided. Returning placeholder.")
            return POSTER_PLACEHOLDER

        # The 'find' endpoint is perfect for looking up with an external ID like IMDb's
        if imdb_id:
            url = f"https://api.themoviedb.org/3/find/{imdb_id}"
            params = {"external_source": "imdb_id"}
            try:
                response = self.session.get(url, params=params, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                results_key = "movie_results" if media_type == "movie" else "tv_results"
                results = data.get(results_key, [])
                
                if results and results[0].get("poster_path"):
                    poster_url = f"{TMDB_IMAGE_BASE_URL}{results[0]['poster_path']}"
                    self.log(f"[TMDB_API] Found poster via IMDb ID: {poster_url}")
                    return poster_url
                else:
                    self.log(f"[TMDB_API] No poster found via IMDb ID '{imdb_id}'.")

            except requests.RequestException as e:
                self.log(f"[WARN] TMDB API call failed for imdb_id {imdb_id}: {e}")
                return POSTER_PLACEHOLDER

        # Fallback or direct lookup if we have the tmdb_id
        elif tmdb_id:
            url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            try:
                response = self.session.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()
                if data.get("poster_path"):
                    poster_url = f"{TMDB_IMAGE_BASE_URL}{data['poster_path']}"
                    self.log(f"[TMDB_API] Found poster via TMDB ID: {poster_url}")
                    return poster_url
                else:
                    self.log(f"[TMDB_API] No poster found via TMDB ID '{tmdb_id}'.")
            except requests.RequestException as e:
                self.log(f"[WARN] TMDB API call failed for tmdb_id {tmdb_id}: {e}")
                return POSTER_PLACEHOLDER
        
        self.log(f"[TMDB_API] No valid ID provided for lookup. Returning placeholder.")
        return POSTER_PLACEHOLDER