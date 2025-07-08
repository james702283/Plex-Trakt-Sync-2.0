# trakt_api/trakt_set.py

from trakt_api.TraktItem import TraktItem
from trakt_api.TraktLookup import TraktLookup

class TraktSet:
    def __init__(self, history):
        self.items = []
        self.lookup = TraktLookup()

        for entry in history:
            item_type = entry.get("type")
            item_data = entry.get(item_type)
            if not item_data:
                continue

            trakt_id = item_data.get("ids", {}).get("trakt")
            title = item_data.get("title")
            year = item_data.get("year")

            item = TraktItem(
                item_type=item_type,
                trakt_id=trakt_id,
                title=title,
                year=year
            )

            if item_type == "episode":
                episode_data = entry.get("episode")
                show_data = entry.get("show")
                if episode_data and show_data:
                    show_title = show_data.get("title")
                    season = episode_data.get("season")
                    number = episode_data.get("number")
                    ep_trakt_id = episode_data.get("ids", {}).get("trakt")
                    show_id = show_data.get("ids", {}).get("trakt")
                    
                    show_item = self.lookup.get_by_id(show_id)
                    if not show_item:
                        show_item = TraktItem(
                            item_type="show",
                            trakt_id=show_id,
                            title=show_title
                        )
                        self.lookup.add(show_item)

                    show_item.add_episode(season, number, {
                        "trakt_id": ep_trakt_id,
                        "watched_at": entry.get("watched_at")
                    })

            self.items.append(item)
            self.lookup.add(item)

    def get(self, title):
        return self.lookup.get_by_title(title)

    def __iter__(self):
        return iter(self.items)
