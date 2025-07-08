from enum import Enum

class PlexMediaType(str, Enum):
    MOVIE = "movie"
    SHOW = "show"
    EPISODE = "episode"
