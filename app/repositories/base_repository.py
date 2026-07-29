from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


class RepositoryBase[ModelType: Base]:
    """Shared model and session context for repository capabilities."""

    def __init__(
        self,
        model: type[ModelType],
        session: AsyncSession,
    ):
        self.model = model
        self.session = session

    async def _load_by_id(self, entity_id: Any) -> ModelType | None:
        return await self.session.get(self.model, entity_id)

    @staticmethod
    def _dump_input(
        obj_in: BaseModel | Mapping[str, Any],
        *,
        exclude_unset: bool,
    ) -> dict[str, Any]:
        if isinstance(obj_in, BaseModel):
            return obj_in.model_dump(exclude_unset=exclude_unset)
        return dict(obj_in)


class GetByIdRepository[ModelType: Base](RepositoryBase[ModelType]):
    """Capability for retrieving one model by primary key."""

    async def get_by_id(self, entity_id: Any) -> ModelType | None:
        return await self._load_by_id(entity_id)


class ListRepository[ModelType: Base](RepositoryBase[ModelType]):
    """Capability for paginated model listing."""

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class CreateRepository[
    ModelType: Base,
    CreateSchemaType: BaseModel,
](RepositoryBase[ModelType]):
    """Capability for creating a model from a typed schema or mapping."""

    async def create(
        self,
        obj_in: CreateSchemaType | Mapping[str, Any],
        *,
        refresh: bool = True,
    ) -> ModelType:
        create_data = self._dump_input(obj_in, exclude_unset=False)
        db_obj = self.model(**create_data)
        self.session.add(db_obj)
        await self.session.flush()
        if refresh:
            await self.session.refresh(db_obj)
        return db_obj


class UpdateRepository[
    ModelType: Base,
    UpdateSchemaType: BaseModel,
](RepositoryBase[ModelType]):
    """Capability for updating a model from explicitly provided fields."""

    async def update(
        self,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | Mapping[str, Any],
        *,
        refresh: bool = True,
    ) -> ModelType:
        update_data = self._dump_input(obj_in, exclude_unset=True)
        unknown_fields = [field for field in update_data if not hasattr(db_obj, field)]
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise ValueError(f"Unknown model fields: {fields}")

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        self.session.add(db_obj)
        await self.session.flush()
        if refresh:
            await self.session.refresh(db_obj)
        return db_obj


class DeleteRepository[ModelType: Base](RepositoryBase[ModelType]):
    """Capability for deleting one model by primary key."""

    async def delete(self, entity_id: Any) -> bool:
        db_obj = await self._load_by_id(entity_id)
        if db_obj is None:
            return False
        await self.session.delete(db_obj)
        await self.session.flush()
        return True


class BaseRepository[
    ModelType: Base,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
](
    GetByIdRepository[ModelType],
    ListRepository[ModelType],
    CreateRepository[ModelType, CreateSchemaType],
    UpdateRepository[ModelType, UpdateSchemaType],
    DeleteRepository[ModelType],
):
    """Convenience composition for repositories that need complete CRUD."""
