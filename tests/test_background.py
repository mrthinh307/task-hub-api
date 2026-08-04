import asyncio
import threading
from functools import partial
from uuid import uuid4

import pytest

from app.core.background import BackgroundTaskDispatcher
from app.notifications import GmailAssignmentNotifier, TaskAssignmentNotification


@pytest.mark.asyncio
async def test_background_dispatcher_runs_and_drains_tasks() -> None:
    dispatcher = BackgroundTaskDispatcher()
    completed = asyncio.Event()

    async def callback() -> None:
        await asyncio.sleep(0)
        completed.set()

    dispatcher.submit(callback)
    await dispatcher.shutdown(timeout_seconds=1)

    assert completed.is_set()


@pytest.mark.asyncio
async def test_background_dispatcher_isolates_task_failures(caplog) -> None:
    dispatcher = BackgroundTaskDispatcher()

    async def callback() -> None:
        raise RuntimeError("email failed")

    dispatcher.submit(callback)
    await dispatcher.shutdown(timeout_seconds=1)

    assert "Background task failed." in caplog.text


@pytest.mark.asyncio
async def test_background_dispatcher_rejects_tasks_after_shutdown() -> None:
    dispatcher = BackgroundTaskDispatcher()
    await dispatcher.shutdown(timeout_seconds=1)

    async def callback() -> None:
        return None

    with pytest.raises(RuntimeError, match="shutting down"):
        dispatcher.submit(callback)


@pytest.mark.asyncio
async def test_shutdown_drains_blocked_thread_send_after_timeout(
    monkeypatch,
    caplog,
) -> None:
    send_started = threading.Event()
    release_send = threading.Event()

    def blocked_send_message(self, message) -> None:
        send_started.set()
        release_send.wait()

    monkeypatch.setattr(
        GmailAssignmentNotifier,
        "_send_message",
        blocked_send_message,
    )
    notifier = GmailAssignmentNotifier(
        username="taskhub@gmail.com",
        app_password="app-password",
        from_name="Task Hub",
        timeout_seconds=1,
    )
    notification = TaskAssignmentNotification(
        task_id=uuid4(),
        task_title="Review API",
        project_name="Task Hub",
        assignee_email="member@example.com",
        assignee_name="Team Member",
        assigned_by_name="Project Owner",
        due_date=None,
    )
    dispatcher = BackgroundTaskDispatcher()
    dispatcher.submit(
        partial(notifier.notify_task_assigned, notification)
    )
    assert await asyncio.to_thread(send_started.wait, 1)

    shutdown_task = asyncio.create_task(dispatcher.shutdown(timeout_seconds=0.01))
    await asyncio.sleep(0.05)

    timeout_was_logged = "after shutdown timeout" in caplog.text
    shutdown_was_pending = not shutdown_task.done()
    release_send.set()
    await asyncio.wait_for(shutdown_task, timeout=1)

    assert timeout_was_logged
    assert shutdown_was_pending
