import uuid
from datetime import datetime
from decimal import Decimal
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import DateTime, Numeric, String, Uuid
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

import courier_orders as co


class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    courier_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    customer_name: Mapped[str] = mapped_column(String)
    delivery_address: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    cash_on_delivery_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime)

@pytest_asyncio.fixture
async def session_factory(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(co, "Order", Order , raising=False)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()

@pytest_asyncio.fixture
async def courier_id(session_factory):
    cid = uuid.uuid4()
    async with session_factory() as s:
        s.add(Order(courier_id=cid, customer_name="mohammed Fawzy", delivery_address="12 , Tahrir street , Cairo , Egypt", status="assigned", cash_on_delivery_amount=Decimal("150.00"), created_at=datetime.now(),))
        await s.commit()
    return cid

@pytest_asyncio.fixture
async def client(session_factory):
    app = FastAPI()
    app.include_router(co.router)

    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[co.get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture
async def authed_client(session_factory, courier_id):
    """Same app, but the caller is authenticated as `courier_id`."""
    app = FastAPI()
    app.include_router(co.router)

    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[co.get_db] = override_get_db
    app.dependency_overrides[co.get_current_courier_id] = lambda: courier_id
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture
async def bare_client(monkeypatch):
    monkeypatch.delattr(co, "Order", raising=False)   # الكود الأصلي من غير Order
    app = FastAPI()
    app.include_router(co.router)
    app.dependency_overrides[co.get_db] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c



@pytest.mark.asyncio
async def test_F_orders_require_authentication(client, courier_id):
    response = await client.get(f"/couriers/{courier_id}/orders")
    assert response.status_code in (401, 403), f"got {response.status_code} : {response.text[:200]}"

@pytest.mark.asyncio
async def test_D_endpoint_works_without_defining_Order(bare_client):
    resp = await bare_client.get(f"/couriers/{uuid.uuid4()}/orders")
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_baseline_happy_path(authed_client, courier_id):
    resp = await authed_client.get(f"/couriers/{courier_id}/orders")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["customer_name"] == "mohammed Fawzy"

@pytest.mark.asyncio
async def test_F_courier_cannot_read_other_couriers_orders(authed_client):
    resp = await authed_client.get(f"/couriers/{uuid.uuid4()}/orders")
    assert resp.status_code == 403