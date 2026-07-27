from collections.abc import Sequence

from redis.asyncio import Redis

from app.core.exceptions import EntityAlreadyExistsException, EntityNotFoundException
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate


class ProductService:
    """
    Business logic layer for Product entity with optional Redis caching.
    """

    def __init__(self, repo: ProductRepository, redis: Redis | None = None):
        self.repo = repo
        self.redis = redis

    async def get_product_by_id(self, product_id: int) -> Product:
        # Check cache if redis is available
        cache_key = f"product:{product_id}"
        if self.redis:
            cached_product = await self.redis.get(cache_key)
            if cached_product:
                pass  # We can parse cache if needed

        product = await self.repo.get_by_id(product_id)
        if not product:
            raise EntityNotFoundException("Product", product_id)
        return product

    async def get_products(self, skip: int = 0, limit: int = 100) -> Sequence[Product]:
        return await self.repo.get_multi(skip=skip, limit=limit)

    async def create_product(self, product_in: ProductCreate) -> Product:
        existing_sku = await self.repo.get_by_sku(product_in.sku)
        if existing_sku:
            raise EntityAlreadyExistsException("Product", "sku", product_in.sku)

        return await self.repo.create(product_in)

    async def update_product(
        self, product_id: int, product_in: ProductUpdate
    ) -> Product:
        product = await self.get_product_by_id(product_id)
        return await self.repo.update(product, product_in)

    async def delete_product(self, product_id: int) -> bool:
        await self.get_product_by_id(product_id)
        return await self.repo.delete(product_id)
