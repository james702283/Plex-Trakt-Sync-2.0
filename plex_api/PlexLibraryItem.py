# plex_api/PlexLibraryItem.py

from plexapi.video import Movie, Episode, Show

class PlexLibraryItem:
    def __init__(self, item):
        self.item = item
        self.guid = self.get_guid()
        self.rating = self.get_rating()
        self.watched = self.get_watched()
        self.last_watched = self.get_last_watched()

    def get_guid(self):
        try:
            return self.item.guid
        except AttributeError:
            return None

    def get_rating(self):
        try:
            return self.item.rating
        except AttributeError:
            return None

    def get_watched(self):
        try:
            return self.item.isWatched
        except AttributeError:
            return False

    def get_last_watched(self):
        try:
            if hasattr(self.item, "lastViewedAt") and self.item.lastViewedAt:
                return self.item.lastViewedAt.isoformat()
        except Exception:
            pass
        return None

    def to_dict(self):
        return {
            "title": self.item.title,
            "type": self.item.type,
            "guid": self.guid,
            "watched": self.watched,
            "rating": self.rating,
            "last_watched": self.last_watched,
        }
