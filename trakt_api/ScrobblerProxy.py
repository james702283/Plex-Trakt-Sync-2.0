# trakt_api/ScrobblerProxy.py

class ScrobblerProxy:
    def __init__(self, trakt):
        self.trakt = trakt
        self.enabled = True

    def scrobble(self, item_type, item_id, watched_at=None):
        if not self.enabled:
            return
        # Trakt scrobble API logic would go here
        pass

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
