# trakt_api/TraktItem.py

class TraktItem:
    def __init__(self, item_type, trakt_id=None, slug=None, title=None, year=None, seasons=None, episodes=None):
        self.item_type = item_type  # 'movie' or 'show'
        self.trakt_id = trakt_id
        self.slug = slug
        self.title = title
        self.year = year
        self.seasons = seasons or {}  # {season_number: {episode_number: metadata}}
        self.episodes = episodes or []

    def get_episode(self, season, number):
        return self.seasons.get(season, {}).get(number)

    def add_episode(self, season, number, metadata):
        if season not in self.seasons:
            self.seasons[season] = {}
        self.seasons[season][number] = metadata
