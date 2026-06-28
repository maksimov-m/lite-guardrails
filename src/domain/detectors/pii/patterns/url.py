from src.domain.detectors.pii.patterns.base import PiiPattern

KNOWN_TLDS = (
    r"ru|рф|com|net|org|io|dev|me|info|biz|co|edu|gov|app|online|store|"
    r"site|tech|pro|su|ua|by|kz"
)


class UrlPattern(PiiPattern):
    name = "url"
    regex = (
        r"https?://[^\s]+"
        r"|www\.[^\s]+"
        rf"|(?<![\w@.\-])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
        rf"(?:{KNOWN_TLDS})\b(?:/[^\s]*)?"
    )
