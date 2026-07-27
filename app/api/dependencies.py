from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, get_redis
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import UserRepository
from app.services.product_service import ProductService
from app.services.user_service import UserService


# Repository Dependencies
def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


def get_product_repository(
    session: AsyncSession = Depends(get_db),
) -> ProductRepository:
    return ProductRepository(session)


# Service Dependencies
def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repo)


def get_product_service(
    repo: ProductRepository = Depends(get_product_repository),
    redis: Redis = Depends(get_redis),
) -> ProductService:
    return ProductService(repo, redis)
