class RunConfig:
    def __init__(self, sync_direction, dry_run, libraries):
        self.sync_direction = sync_direction
        self.dry_run = dry_run
        self.libraries = libraries or []

    @classmethod
    def from_config(cls, config):
        return cls(
            sync_direction=config.get("SYNC_DIRECTION", "plex_to_trakt"),
            dry_run=config.get("DRY_RUN", False),
            libraries=config.get("PLEX_LIBRARIES", []),
        )
