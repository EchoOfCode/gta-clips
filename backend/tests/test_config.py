from app.config import Settings


def test_settings_default_values():
    s = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/testdb")
    assert s.api_port == 18090
    assert s.app_name == "GTA Clip Engine"
    assert s.media_root == "/media"


def test_settings_port_parsing():
    s = Settings(
        database_url="postgresql+psycopg://user:pass@localhost:5432/testdb",
        API_PORT="19090",
    )
    assert s.api_port == 19090


def test_settings_provider_status_flags():
    s_unconf = Settings(
        database_url="postgresql+psycopg://user:pass@localhost:5432/testdb"
    )
    assert not s_unconf.is_youtube_configured
    assert not s_unconf.is_twitch_configured

    s_conf = Settings(
        database_url="postgresql+psycopg://user:pass@localhost:5432/testdb",
        youtube_api_key="valid-key",
        twitch_client_id="cid",
        twitch_client_secret="csecret",
    )
    assert s_conf.is_youtube_configured
    assert s_conf.is_twitch_configured


def test_settings_secret_masking_in_repr():
    secret_db = "postgresql+psycopg://user:SUPER_SECRET_PASSWORD@localhost:5432/testdb"
    s = Settings(
        database_url=secret_db,
        internal_api_key="SUPER_SECRET_INTERNAL_KEY",
        youtube_api_key="SECRET_YOUTUBE_KEY",
        twitch_client_secret="SECRET_TWITCH_SECRET",
    )
    repr_str = repr(s)
    assert "SUPER_SECRET_PASSWORD" not in repr_str
    assert "SUPER_SECRET_INTERNAL_KEY" not in repr_str
    assert "SECRET_YOUTUBE_KEY" not in repr_str
    assert "SECRET_TWITCH_SECRET" not in repr_str
    assert "***MASKED***" in repr_str
