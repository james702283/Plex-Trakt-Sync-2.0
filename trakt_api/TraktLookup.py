# trakt_api/TraktLookup.py

from trakt_api.TraktItem import TraktItem

class TraktLookup:
    def __init__(self):
        self.lookup_by_title = {}
        self.lookup_by_trakt_id = {}

    def add(self, item: TraktItem):
        if item.title:
            self.lookup_by_title[item.title.lower()] = item
        if item.trakt_id:
            self.lookup_by_trakt_id[item.trakt_id] = item

    def get_by_title(self, title):
        return self.lookup_by_title.get(title.lower())

    def get_by_id(self, trakt_id):
        return self.lookup_by_trakt_id.get(trakt_id)
