from datetime import UTC, datetime, timedelta
import asyncio
from uuid import uuid4

from app.actions.models import ActionAuthorization, ActionStatus, PendingAction
from app.actions.store import ActiveActionExistsError, PendingActionStore
from app.tools.base import ToolSafetyLevel


class ActionConfirmationService:
    def __init__(self, store: PendingActionStore | None = None, ttl_seconds: int = 300) -> None:
        self._store = store or PendingActionStore()
        self._ttl_seconds = ttl_seconds
        self._transition_lock = asyncio.Lock()

    async def create_pending_action(self, tool_name: str, arguments: dict[str, object], safety_level: ToolSafetyLevel) -> PendingAction:
        now = datetime.now(UTC)
        action = PendingAction(
            id=f"act_{uuid4().hex}",
            tool_name=tool_name,
            arguments=arguments,
            safety_level=safety_level.value,
            status=ActionStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
        )
        return await self._store.create(action)

    async def get_active_action(self) -> PendingAction | None:
        action = await self._store.active()
        if action and action.status == ActionStatus.PENDING and datetime.now(UTC) >= action.expires_at:
            action.status = ActionStatus.EXPIRED
            await self._store.update(action)
        return action

    async def approve_action(self, action_id: str) -> ActionAuthorization | None:
        async with self._transition_lock:
            action = await self._store.get(action_id)
            if action is None or action.status != ActionStatus.PENDING:
                return None
            if datetime.now(UTC) >= action.expires_at:
                action.status = ActionStatus.EXPIRED
                await self._store.update(action)
                return None
            now = datetime.now(UTC)
            action.status = ActionStatus.APPROVED
            action.approved_at = now
            await self._store.update(action)
            return ActionAuthorization(action_id=action.id, tool_name=action.tool_name, approved_at=now)

    async def reject_action(self, action_id: str) -> bool:
        async with self._transition_lock:
            action = await self._store.get(action_id)
            if action is None or action.status != ActionStatus.PENDING:
                return False
            action.status = ActionStatus.REJECTED
            await self._store.update(action)
            return True

    async def mark_executed(self, action_id: str) -> PendingAction | None:
        action = await self._store.get(action_id)
        if action is None or action.status != ActionStatus.APPROVED:
            return None
        action.status = ActionStatus.EXECUTED
        action.executed_at = datetime.now(UTC)
        return await self._store.update(action)

    async def mark_failed(self, action_id: str, error: str) -> PendingAction | None:
        action = await self._store.get(action_id)
        if action is None or action.status != ActionStatus.APPROVED:
            return None
        action.status = ActionStatus.FAILED
        action.error = error
        return await self._store.update(action)

    async def get_action(self, action_id: str) -> PendingAction | None:
        return await self._store.get(action_id)
