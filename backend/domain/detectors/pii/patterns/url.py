from backend.domain.detectors.pii.patterns.base import PiiPattern

KNOWN_TLDS = (
    r"ru|рф|com|net|org|io|dev|me|info|biz|co|edu|gov|app|online|store|"
    r"site|tech|pro|su|ua|by|kz"
)

# Знаки, которыми URL не должен ЗАКАНЧИВАТЬСЯ: пунктуация предложения
# (точка/запятая/двоеточие/…) и закрывающие скобки-кавычки, «прилипшие» к ссылке.
# Внутри URL они допустимы (напр. порт example.com:8080) — ограничение только на
# последний символ, поэтому тело матчим жадно, а хвостовую пунктуацию отбрасываем.
_TRAILING = r"""[^\s.,;:!?)\]}>"'»«]"""


class UrlPattern(PiiPattern):
    name = "url"
    regex = (
        rf"https?://[^\s]*{_TRAILING}"
        rf"|www\.[^\s]*{_TRAILING}"
        rf"|(?<![\w@.\-])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
        rf"(?:{KNOWN_TLDS})\b(?:/[^\s]*{_TRAILING})?"
    )
