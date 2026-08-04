import asyncio

import pytest

from app.core.background import BackgroundTaskDispatcher


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
