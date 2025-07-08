# plugins/SyncPlugin.py

class SyncPlugin:
    def __init__(self, plex, trakt, config, log):
        self.plex = plex
        self.trakt = trakt
        self.config = config
        self.log = log

    def run(self):
        raise NotImplementedError("Each plugin must implement the run() method.")