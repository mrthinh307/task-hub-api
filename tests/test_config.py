from pydantic_settings import SettingsConfigDict

from app.core.config import Settings

TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/test_db"


class SettingsWithoutDotenv(Settings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )


def test_auth_cookies_are_secure_by_default() -> None:
    settings = SettingsWithoutDotenv(DATABASE_URL=TEST_DATABASE_URL)

    assert settings.COOKIE_SECURE is True


def test_database_url_is_required() -> None:
    assert SettingsWithoutDotenv.model_fields["DATABASE_URL"].is_required()


def test_local_development_can_disable_secure_cookies(monkeypatch) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "false")

    settings = SettingsWithoutDotenv(DATABASE_URL=TEST_DATABASE_URL)

    assert settings.COOKIE_SECURE is False
