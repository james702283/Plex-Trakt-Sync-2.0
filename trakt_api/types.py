from enum import Enum

class MediaType(str, Enum):
    MOVIE = "movie"
    SHOW = "show"
    EPISODE = "episode"
