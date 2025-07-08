# plex/PlexLibraryItem.py
import datetime

class PlexLibraryItem:
    def __init__(self, item, plex_api):
        self.item = item
        self.plex_api = plex_api

    @property
    def title(self):
        return self.item.title

    @property
    def isWatched(self):
        return self.item.isPlayed

    @property
    def lastViewedAt(self):
        return self.item.lastViewedAt

    @property
    def seasonNumber(self):
        return self.item.seasonNumber

    @property
    def index(self):
        return self.item.index

    @property
    def guids(self):
        # This property smartly extracts and provides the GUIDs
        return self.item.guids

    def episodes(self):
        # This method will yield our custom PlexLibraryItem objects
        for ep in self.item.episodes():
            yield PlexLibraryItem(ep, self.plex_api)