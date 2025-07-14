from .SyncPlugin import SyncPlugin
from tqdm import tqdm
from state import SYNC_CANCEL_REQUESTED

class ClearCollectedPlugin(SyncPlugin):
    def run(self):
        self.log("[INFO] --- Running Clear Trakt Collection ---")
        self.log("[WARN] This will remove ALL movies and shows from your Trakt collection.")

        try:
            movies_to_remove = self.trakt.get_collection('movies')
            shows_to_remove = self.trakt.get_collection('shows')
        except Exception as e:
            self.log(f"[ERROR] Could not get Trakt collection to clear: {e}")
            return
            
        payload = {"movies": movies_to_remove, "shows": shows_to_remove}

        if not movies_to_remove and not shows_to_remove:
            self.log("[INFO] Your Trakt collection is already empty. Nothing to do.")
            return
            
        if SYNC_CANCEL_REQUESTED: self.log("[CANCEL] Sync cancelled by user."); return

        self.log(f"[INFO] Preparing to remove {len(movies_to_remove)} movies and {len(shows_to_remove)} shows from your collection.")
        
        try:
            self.trakt.remove_from_collection(payload)
            self.log("[SUCCESS] Successfully cleared your Trakt collection.")
        except Exception as e:
            self.log(f"[ERROR] An error occurred while clearing the collection: {e}")
        
        self.log("[INFO] --- Finished Clearing Trakt Collection ---")