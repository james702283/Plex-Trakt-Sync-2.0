# plex_api/PlexLibrarySection.py

from plex_api.PlexLibraryItem import PlexLibraryItem

class PlexLibrarySection:
    def __init__(self, section):
        self.section = section
        self.title = section.title
        self.type = section.TYPE
        self.key = section.key

    def get_items(self):
        """
        Returns a list of PlexLibraryItem instances.
        """
        items = []
        for video in self.section.all():
            try:
                items.append(PlexLibraryItem(video))
            except Exception as e:
                print(f"[error] Failed to wrap item in section {self.title}: {e}")
        return items
