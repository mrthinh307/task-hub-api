from collections.abc import Sequence

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_product_service
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", response_model=Sequence[ProductResponse])
async def get_products(
    skip: int = 0,
    limit: int = 100,
    service: ProductService = Depends(get_product_service),
):
    """Retrieve list of products with pagination."""
    return await service.get_products(skip=skip, limit=limit)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int, service: ProductService = Depends(get_product_service)
):
    """Get product by ID."""
    return await service.get_product_by_id(product_id)


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate, service: ProductService = Depends(get_product_service)
):
    """Create new product."""
    return await service.create_product(product_in)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_in: ProductUpdate,
    service: ProductService = Depends(get_product_service),
):
    """Update existing product."""
    return await service.update_product(product_id, product_in)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int, service: ProductService = Depends(get_product_service)
):
    """Delete product."""
    await service.delete_product(product_id)
