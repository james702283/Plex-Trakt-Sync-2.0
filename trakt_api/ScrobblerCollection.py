# trakt_api/ScrobblerCollection.py

class ScrobblerCollection:
    def __init__(self):
        self.collected = set()

    def mark_collected(self, key):
        self.collected.add(key)

    def is_collected(self, key):
        return key in self.collected
