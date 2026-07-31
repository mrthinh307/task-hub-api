from collections.abc import Awaitable, Callable

from app.core.logging import logger

PostCommitCallback = Callable[[], Awaitable[None]]


class PostCommitActions:
    def __init__(self) -> None:
        self._callbacks: list[PostCommitCallback] = []

    def add(self, callback: PostCommitCallback) -> None:
        self._callbacks.append(callback)

    async def run(self) -> None:
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            try:
                await callback()
            except Exception:
                logger.exception("Post-commit action failed.")


def get_post_commit_actions() -> PostCommitActions:
    return PostCommitActions()
