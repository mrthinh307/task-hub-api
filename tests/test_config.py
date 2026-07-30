from pydantic_settings import SettingsConfigDict

from app.core.config import Settings


class SettingsWithoutDotenv(Settings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )


def test_auth_cookies_are_secure_by_default() -> None:
    settings = SettingsWithoutDotenv()

    assert settings.COOKIE_SECURE is True
    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://task_hub:task_hub_dev_password"
        "@localhost:5432/task_hub"
    )


def test_local_development_can_disable_secure_cookies(monkeypatch) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "false")

    settings = SettingsWithoutDotenv()

    assert settings.COOKIE_SECURE is False
