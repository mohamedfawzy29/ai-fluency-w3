from datetime import date, datetime, time
from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# --- Pydantic Schemas ---


class OrderOut(BaseModel):
    id: UUID
    customer_name: str
    delivery_address: str
    status: str
    cash_on_delivery_amount: Decimal = Field(
        ...,
        description="Amount to collect upon delivery (0.00 if prepaid)",
        decimal_places=2,
    )
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedOrdersResponse(BaseModel):
    items: List[OrderOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# --- Router & Dependency Setup ---

router = APIRouter(prefix="/couriers", tags=["Couriers"])

# Replace with your actual database session dependency
async def get_db() -> AsyncSession:
    raise NotImplementedError


# --- Endpoint ---


@router.get("/{id}/orders", response_model=PaginatedOrdersResponse, status_code=status.HTTP_200_OK, summary="Get courier orders for today",)
async def get_courier_today_orders(id: UUID, page: int = Query(default=1, ge=1, description="Page number"), db: AsyncSession = Depends(get_db),):
    page_size = 20
    offset = (page - 1) * page_size

    # Define the start and end timestamps for the current day
    today_start = datetime.combine(date.today(), time.min)
    today_end = datetime.combine(date.today(), time.max)

    # Base filter criteria
    filters = [Order.courier_id == id, Order.created_at >= today_start, Order.created_at <= today_end,]

    # Total record count for pagination metadata
    count_query = select(func.count(Order.id)).where(*filters)
    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()

    # Query items: ordered by creation time descending, limited to 20
    items_query = (
        select(Order)
        .where(*filters)
        .order_by(desc(Order.created_at))
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_query)
    orders = items_result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    return PaginatedOrdersResponse(
        items=orders,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )