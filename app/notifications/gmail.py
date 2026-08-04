import asyncio
import html
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.notifications.assignment import TaskAssignmentNotification

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


class GmailAssignmentNotifier:
    def __init__(
        self,
        *,
        username: str,
        app_password: str,
        from_name: str,
        timeout_seconds: float,
    ) -> None:
        self._username = username
        self._app_password = app_password
        self._from_name = from_name
        self._timeout_seconds = timeout_seconds

    async def notify_task_assigned(
        self,
        notification: TaskAssignmentNotification,
    ) -> None:
        message = self._build_message(notification)
        await asyncio.to_thread(self._send_message, message)

    def _build_message(self, notification: TaskAssignmentNotification) -> EmailMessage:
        due_date = (
            notification.due_date.isoformat()
            if notification.due_date is not None
            else "No due date"
        )
        message = EmailMessage()
        message["Subject"] = "A task has been assigned to you"
        message["From"] = formataddr((self._from_name, self._username))
        message["To"] = notification.assignee_email
        message.set_content(
            f"Hello {notification.assignee_name},\n\n"
            f"{notification.assigned_by_name} assigned a task to you.\n\n"
            f"Task: {notification.task_title}\n"
            f"Project: {notification.project_name}\n"
            f"Due date: {due_date}\n\n"
            "Please sign in to Task Hub to review it.\n"
        )
        message.add_alternative(
            "<p>Hello "
            f"{html.escape(notification.assignee_name)},</p>"
            "<p>"
            f"{html.escape(notification.assigned_by_name)} assigned a task to you."
            "</p>"
            "<dl>"
            f"<dt>Task</dt><dd>{html.escape(notification.task_title)}</dd>"
            f"<dt>Project</dt><dd>{html.escape(notification.project_name)}</dd>"
            f"<dt>Due date</dt><dd>{html.escape(due_date)}</dd>"
            "</dl>"
            "<p>Please sign in to Task Hub to review it.</p>",
            subtype="html",
        )
        return message

    def _send_message(self, message: EmailMessage) -> None:
        tls_context = ssl.create_default_context()
        with smtplib.SMTP(
            GMAIL_SMTP_HOST,
            GMAIL_SMTP_PORT,
            timeout=self._timeout_seconds,
        ) as client:
            client.ehlo()
            client.starttls(context=tls_context)
            client.ehlo()
            client.login(self._username, self._app_password)
            client.send_message(message)
