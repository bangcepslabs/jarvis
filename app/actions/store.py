import asyncio

from app.actions.models import ActionStatus, PendingAction


class ActiveActionExistsError(Exception):
    """An action is already awaiting a decision."""


class PendingActionStore:
    def __init__(self) -> None:
        self._actions: dict[str, PendingAction] = {}
        self._active_id: str | None = None
        self._lock = asyncio.Lock()

    async def create(self, action: PendingAction) -> PendingAction:
        async with self._lock:
            active = self._active_unlocked()
            if active is not None:
                raise ActiveActionExistsError(active.id)
            self._actions[action.id] = action
            self._active_id = action.id
            return action

    async def get(self, action_id: str) -> PendingAction | None:
        async with self._lock:
            return self._actions.get(action_id)

    async def active(self) -> PendingAction | None:
        async with self._lock:
            action = self._active_unlocked()
            return action

    async def update(self, action: PendingAction) -> PendingAction:
        async with self._lock:
            self._actions[action.id] = action
            if action.status not in {ActionStatus.PENDING, ActionStatus.APPROVED} and self._active_id == action.id:
                self._active_id = None
            return action

    def _active_unlocked(self) -> PendingAction | None:
        if self._active_id is None:
            return None
        return self._actions.get(self._active_id)
