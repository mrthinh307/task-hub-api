import asyncio
from collections.abc import Awaitable, Callable

from app.core.logging import logger

BackgroundCallback = Callable[[], Awaitable[None]]


class BackgroundTaskDispatcher:
    """Runs in-process tasks and drains them during application shutdown."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._accepting_tasks = True

    def submit(self, callback: BackgroundCallback) -> None:
        if not self._accepting_tasks:
            raise RuntimeError("Background task dispatcher is shutting down")

        task = asyncio.create_task(self._run(callback))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, callback: BackgroundCallback) -> None:
        try:
            await callback()
        except Exception:
            logger.exception("Background task failed.")

    async def shutdown(self, timeout_seconds: float) -> None:
        self._accepting_tasks = False
        tasks = set(self._tasks)
        if not tasks:
            return

        _, pending = await asyncio.wait(tasks, timeout=timeout_seconds)
        if not pending:
            return

        logger.warning(
            "Cancelling %d background task(s) after shutdown timeout.",
            len(pending),
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
