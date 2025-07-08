from helpers.PlexItem import PlexItem

class PlexItemParser:
    def __init__(self, log):
        self.log = log

    def parse(self, item):
        try:
            title = getattr(item, "title", None)
            guid = getattr(item, "guid", None)
            rating_key = getattr(item, "ratingKey", None)
            media_type = getattr(item, "type", None)
            season = getattr(item, "seasonIndex", None) or getattr(item, "seasonNumber", None)
            episode = getattr(item, "index", None)
            last_watched = getattr(item, "lastViewedAt", None)

            return PlexItem(
                title=title,
                guid=str(guid) if guid else None,
                rating_key=rating_key,
                media_type=media_type,
                season=season,
                episode=episode,
                last_watched=last_watched.isoformat() if last_watched else None
            )
        except Exception as e:
            self.log(f"[Parser] Failed to parse item: {e}")
            return None
