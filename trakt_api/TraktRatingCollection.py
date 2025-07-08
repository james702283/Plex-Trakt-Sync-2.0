# trakt_api/TraktRatingCollection.py

class TraktRatingCollection:
    def __init__(self):
        self.ratings = {}  # { (item_type, id): rating }

    def set_rating(self, item_type, trakt_id, rating):
        self.ratings[(item_type, trakt_id)] = rating

    def get_rating(self, item_type, trakt_id):
        return self.ratings.get((item_type, trakt_id))
