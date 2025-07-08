class PlexGuidResolver:
    def __init__(self, log):
        self.log = log

    def extract_guid(self, item):
        try:
            if hasattr(item, "guid") and item.guid:
                return str(item.guid)
            else:
                self.log(f"[Resolver] No GUID found for item: {getattr(item, 'title', 'Unknown')}")
                return None
        except Exception as e:
            self.log(f"[Resolver] Error extracting GUID: {e}")
            return None
