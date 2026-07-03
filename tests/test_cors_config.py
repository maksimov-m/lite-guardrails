from backend.config import Settings


def test_cors_defaults_to_wildcard():
    s = Settings()
    assert s.cors_allow_origins_list == ["*"]
    assert s.cors_allow_methods_list == ["*"]
    assert s.cors_allow_headers_list == ["*"]


def test_cors_parses_csv_and_trims():
    s = Settings(cors_allow_origins="https://a.ru, https://b.ru ,")
    assert s.cors_allow_origins_list == ["https://a.ru", "https://b.ru"]


def test_cors_empty_falls_back_to_wildcard():
    s = Settings(cors_allow_origins="  ,  ")
    assert s.cors_allow_origins_list == ["*"]
