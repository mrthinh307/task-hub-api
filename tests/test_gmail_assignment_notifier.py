from datetime import UTC, datetime
from email.message import EmailMessage
from types import TracebackType
from uuid import uuid4

import pytest

from app.notifications import GmailAssignmentNotifier, TaskAssignmentNotification


class FakeSmtpClient:
    def __init__(self) -> None:
        self.ehlo_calls = 0
        self.started_tls = False
        self.login_credentials: tuple[str, str] | None = None
        self.sent_message: EmailMessage | None = None

    def __enter__(self) -> "FakeSmtpClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def ehlo(self) -> None:
        self.ehlo_calls += 1

    def starttls(self, *, context: object) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_credentials = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.sent_message = message


@pytest.mark.asyncio
async def test_gmail_notifier_sends_english_multipart_email(monkeypatch) -> None:
    smtp_client = FakeSmtpClient()
    connection_args: list[tuple[str, int, float]] = []

    def create_smtp_client(
        host: str,
        port: int,
        *,
        timeout: float,
    ) -> FakeSmtpClient:
        connection_args.append((host, port, timeout))
        return smtp_client

    monkeypatch.setattr(
        "app.notifications.gmail.smtplib.SMTP",
        create_smtp_client,
    )
    notifier = GmailAssignmentNotifier(
        username="taskhub@gmail.com",
        app_password="app-password",
        from_name="Task Hub",
        timeout_seconds=7,
    )

    await notifier.notify_task_assigned(
        TaskAssignmentNotification(
            task_id=uuid4(),
            task_title="Review <API>",
            project_name="Task Hub",
            assignee_email="member@example.com",
            assignee_name="Team Member",
            assigned_by_name="Project Owner",
            due_date=datetime(2026, 8, 15, 10, tzinfo=UTC),
        )
    )

    assert connection_args == [("smtp.gmail.com", 587, 7)]
    assert smtp_client.ehlo_calls == 2
    assert smtp_client.started_tls is True
    assert smtp_client.login_credentials == ("taskhub@gmail.com", "app-password")
    message = smtp_client.sent_message
    assert message is not None
    assert message["Subject"] == "A task has been assigned to you"
    assert message["To"] == "member@example.com"
    assert message["From"] == "Task Hub <taskhub@gmail.com>"
    plain_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))
    assert plain_part is not None
    assert html_part is not None
    assert "Project Owner assigned a task to you." in plain_part.get_content()
    html_body = html_part.get_content()
    assert "Review &lt;API&gt;" in html_body
    assert "href=" not in html_body
