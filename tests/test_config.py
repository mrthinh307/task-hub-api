import pytest
from pydantic import SecretStr, ValidationError
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


def test_task_list_cache_uses_bounded_configurable_ttl() -> None:
    settings = SettingsWithoutDotenv(DATABASE_URL=TEST_DATABASE_URL)

    assert settings.TASK_LIST_CACHE_TTL_SECONDS == 60

    configured = SettingsWithoutDotenv(
        DATABASE_URL=TEST_DATABASE_URL,
        TASK_LIST_CACHE_TTL_SECONDS=120,
    )

    assert configured.TASK_LIST_CACHE_TTL_SECONDS == 120


def test_task_list_cache_rejects_invalid_ttl() -> None:
    with pytest.raises(ValidationError):
        SettingsWithoutDotenv(
            DATABASE_URL=TEST_DATABASE_URL,
            TASK_LIST_CACHE_TTL_SECONDS=0,
        )


def test_email_notifications_are_disabled_by_default() -> None:
    settings = SettingsWithoutDotenv(DATABASE_URL=TEST_DATABASE_URL)

    assert settings.EMAIL_NOTIFICATIONS_ENABLED is False


def test_enabled_email_notifications_require_gmail_credentials() -> None:
    with pytest.raises(ValidationError, match="GMAIL_SMTP_USERNAME"):
        SettingsWithoutDotenv(
            DATABASE_URL=TEST_DATABASE_URL,
            EMAIL_NOTIFICATIONS_ENABLED=True,
        )


def test_enabled_email_notifications_accept_gmail_credentials() -> None:
    settings = SettingsWithoutDotenv(
        DATABASE_URL=TEST_DATABASE_URL,
        EMAIL_NOTIFICATIONS_ENABLED=True,
        GMAIL_SMTP_USERNAME="taskhub@gmail.com",
        GMAIL_SMTP_APP_PASSWORD=SecretStr("app-password"),
    )

    assert str(settings.GMAIL_SMTP_USERNAME) == "taskhub@gmail.com"
    assert settings.GMAIL_SMTP_APP_PASSWORD is not None
    assert settings.GMAIL_SMTP_APP_PASSWORD.get_secret_value() == "app-password"
