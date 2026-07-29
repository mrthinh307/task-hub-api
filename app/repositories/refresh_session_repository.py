from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession
from app.repositories.base_repository import CreateRepository


class RefreshSessionCreate(BaseModel):
    user_id: UUID
    token_hash: str
    jti: UUID
    expires_at: datetime


class RefreshSessionRepository(
    CreateRepository[RefreshSession, RefreshSessionCreate],
):
    def __init__(self, session: AsyncSession):
        super().__init__(RefreshSession, session)

    async def create_session(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        jti: UUID,
        expires_at: datetime,
    ) -> RefreshSession:
        return await self.create(
            RefreshSessionCreate(
                user_id=user_id,
                token_hash=token_hash,
                jti=jti,
                expires_at=expires_at,
            ),
            refresh=False,
        )

    async def get_by_token_hash_for_update(
        self,
        token_hash: str,
    ) -> RefreshSession | None:
        stmt = (
            select(RefreshSession)
            .where(RefreshSession.token_hash == token_hash)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def rotate(
        self,
        current_session: RefreshSession,
        *,
        new_token_hash: str,
        new_jti: UUID,
        new_expires_at: datetime,
        revoked_at: datetime,
    ) -> RefreshSession:
        current_session.revoked_at = revoked_at
        replacement = await self.create_session(
            user_id=current_session.user_id,
            token_hash=new_token_hash,
            jti=new_jti,
            expires_at=new_expires_at,
        )
        current_session.replaced_by_id = replacement.id
        await self.session.flush()
        return replacement

    async def revoke_by_token_hash(
        self,
        token_hash: str,
        *,
        revoked_at: datetime,
    ) -> None:
        refresh_session = await self.get_by_token_hash_for_update(token_hash)
        if refresh_session is None or refresh_session.revoked_at is not None:
            return
        refresh_session.revoked_at = revoked_at
        await self.session.flush()
