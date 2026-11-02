### 1.
Prompt : 
A FastAPI endpoint GET /couriers/{id}/orders?page= for Tawseel returning a courier's orders for today, newest first, 20 per page, including the cash-on-delivery amount.
------------------------------------------------------------------------------------------------------
Ai Code : 
  1  from datetime import date, datetime, time
  2  from decimal import Decimal
  3  from typing import List
  4  from uuid import UUID
  5  
  6  from fastapi import APIRouter, Depends, HTTPException, Query, status
  7  from pydantic import BaseModel, Field
  8  from sqlalchemy import desc, func, select
  9  from sqlalchemy.ext.asyncio import AsyncSession
 10  
 11  # --- Pydantic Schemas ---
 12  
 13  
 14  class OrderOut(BaseModel):
 15      id: UUID
 16      customer_name: str
 17      delivery_address: str
 18      status: str
 19      cash_on_delivery_amount: Decimal = Field(
 20          ...,
 21          description="Amount to collect upon delivery (0.00 if prepaid)",
 22          decimal_places=2,
 23      )
 24      created_at: datetime
 25  
 26      class Config:
 27          from_attributes = True
 28  
 29  
 30  class PaginatedOrdersResponse(BaseModel):
 31      items: List[OrderOut]
 32      total: int
 33      page: int
 34      page_size: int
 35      total_pages: int
 36  
 37  
 38  # --- Router & Dependency Setup ---
 39  
 40  router = APIRouter(prefix="/couriers", tags=["Couriers"])
 41  
 42  # Replace with your actual database session dependency
 43  async def get_db() -> AsyncSession:
 44      raise NotImplementedError
 45  
 46  
 47  # --- Endpoint ---
 48  
 49  
 50  @router.get("/{id}/orders", response_model=PaginatedOrdersResponse, status_code=status.HTTP_200_OK, summary="Get courier orders for today",)
 51  async def get_courier_today_orders(id: UUID, page: int = Query(default=1, ge=1, description="Page number"), db: AsyncSession = Depends(get_db),):
 52      page_size = 20
 53      offset = (page - 1) * page_size
 54  
 55      # Define the start and end timestamps for the current day
 56      today_start = datetime.combine(date.today(), time.min)
 57      today_end = datetime.combine(date.today(), time.max)
 58  
 59      # Base filter criteria
 60      filters = [Order.courier_id == id, Order.created_at >= today_start, Order.created_at <= today_end,]
 61  
 62      # Total record count for pagination metadata
 63      count_query = select(func.count(Order.id)).where(*filters)
 64      total_result = await db.execute(count_query)
 65      total_count = total_result.scalar_one()
 66  
 67      # Query items: ordered by creation time descending, limited to 20
 68      items_query = (
 69          select(Order)
 70          .where(*filters)
 71          .order_by(desc(Order.created_at))
 72          .offset(offset)
 73          .limit(page_size)
 74      )
 75      items_result = await db.execute(items_query)
 76      orders = items_result.scalars().all()
 77  
 78      total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
 79  
 80      return PaginatedOrdersResponse(
 81          items=orders,
 82          total=total_count,
 83          page=page,
 84          page_size=page_size,
 85          total_pages=total_pages,
 86      )

(Original AI output, unedited. 86 lines. Saved as commit 067eeb7.)
original code commit : https://github.com/mohamedfawzy29/ai-fluency-w3/commit/067eeb7
------------------------------------------------------------------------------------------------------
### 2.
Findings : 

1- blocker, security (line 51) : 
the endpoint that the ai created takes the courier_id from the Url without any authenticatoin or claims check and this make an idor for anyone who knows or can guess the id can read the data for this courier and its proven in the tests in the proofs section

2- blocker, invented api (lines 60,63,69)
the word (Order) is used in the filters and the queries but it's not exist or defined in the ai code so the first request always will fail with error and its proven in the tests in the proofs section too

3- nit, style (Line 6) : 
  (HTTPException) is imported but it's never used

4- nit, outdated (lines 26,27) : 
the class config is an old style in pydentic 1 versions but we use pydantic 2.14 and this will cause a PydanticDeprecatedSince20 warninng and the new form is model_config = ConfigDict(from_attributes=True)
------------------------------------------------------------------------------------------------------
### 3.
Proof : 

setup : the ai code does not define (Order) and (get_db) raise a notImplentedError and i wrote a test harness an in memory sqlLite (Order model) and (app.dependency_overrides) for (get_db) the test only job is to let the original endpoint run

command & enviroment : 
- py -m pytest -v --tb=short test_courier_orders.py
- Python 3.12.10, FastAPI 0.162.0, Pydantic 2.14.2, SQLAlchemy 2.1.6, pytest 9.2.0.

Test code (commit 2382807) :

https://github.com/mohamedfawzy29/ai-fluency-w3/commit/2382807

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
async def test_baseline_happy_path(client, courier_id):
    resp = await client.get(f"/couriers/{courier_id}/orders")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["customer_name"] == "mohammed Fawzy"

Output :

============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\moham\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: D:\DSC\Ai-Fluency\Week-3
plugins: anyio-4.15.1, asyncio-1.4.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 3 items

test_courier_orders.py::test_F_orders_require_authentication FAILED      [ 33%]
test_courier_orders.py::test_D_endpoint_works_without_defining_Order FAILED [ 66%]
test_courier_orders.py::test_baseline_happy_path PASSED                  [100%]

================================== FAILURES ===================================
____________________ test_F_orders_require_authentication _____________________
test_courier_orders.py:74: in test_F_orders_require_authentication
    assert response.status_code in (401, 403), f"got {response.status_code} : {response.text[:200]}"
E   AssertionError: got 200 : {"items":[{"id":"90d8a2a4-846b-4e34-8fc4-466445f843b1","customer_name":"mohammed Fawzy","delivery_address":"12 , Tahrir street , Cairo , Egypt","status":"assigned","cash_on_delivery_amount":"150.00","
E   assert 200 in (401, 403)
E    +  where 200 = <Response [200 OK]>.status_code
________________ test_D_endpoint_works_without_defining_Order _________________
test_courier_orders.py:78: in test_D_endpoint_works_without_defining_Order
    resp = await bare_client.get(f"/couriers/{uuid.uuid4()}/orders")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1768: in get
    return await self.request(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1629: in send
    response = await self._send_handling_auth(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_transports\asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\applications.py:1194: in __call__
    await super().__call__(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\applications.py:96: in __call__
    await self.middleware_stack(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\middleware\errors.py:186: in __call__
    raise exc
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\middleware\errors.py:164: in __call__
    await self.app(scope, receive, _send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\telemetry\_asgi.py:151: in __call__
    await self.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\middleware\exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:53: in wrapped_app
    raise exc
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\middleware\asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\routing.py:683: in __call__
    await self.middleware_stack(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:2811: in app
    await route.handle(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:1839: in handle
    await self.original_router.handle(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:2894: in handle
    await included_router._handle_selected(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:1865: in _handle_selected
    await original_route.handle(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:1328: in handle
    await effective_context.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:166: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:53: in wrapped_app
    raise exc
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:152: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:745: in app
    raw_response = await run_endpoint_function(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:372: in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
courier_orders.py:60: in get_courier_today_orders
    filters = [Order.courier_id == id, Order.created_at >= today_start, Order.created_at <= today_end,]
               ^^^^^
E   NameError: name 'Order' is not defined
============================== warnings summary ===============================
courier_orders.py:14
  D:\DSC\Ai-Fluency\Week-3\courier_orders.py:14: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.14/migration/
    class OrderOut(BaseModel):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED test_courier_orders.py::test_F_orders_require_authentication - Asserti...
FAILED test_courier_orders.py::test_D_endpoint_works_without_defining_Order
=================== 2 failed, 1 passed, 1 warning in 1.77s ====================


What it shows :

- test_F fails on the original code A request with no credentials returns
200 with the customer name delivery address and cash-on-delivery amount and This proves Finding 1 (IDOR / missing authentication)

- test_D fails with (NameError: name 'Order' is not defined) at courier_orders.py : 60 This proves Finding 2

- test_baseline passes so the harness is sound and the endpoint works once
(Order) exists

- The PydanticDeprecatedSince20 warning at courier_orders.py : 14 supports
  Finding 4
------------------------------------------------------------------------------------------------------
### 4.
Review Checklist : 

1. Does it do the right thing? 
i read the code against the specifications and run the happy path in my test harness the request returned 200 with total 1 and the correct customer name (test_baseline_happy_path passed), and the response included cash_on_delivery_amount (150.00) visible in the test_F output. 
By reading page_size is 20 as we want (line 52) and page has ge=1 to avoid the page = 0 case and the offset is (page - 1) * page_size (lines 51, 53) the sort is created_at descending (line 71) and the amount is typed as Decimal not float (lines 2, 19). 
Missing authentication (Finding 1) there is one question I didn't test so I am not reporting them as findings which timezone is (today) since date.today() uses the server's local time (lines 56-57)? 

2. Does everything it calls exist? 
No the word (Order) is never defined (lines 60, 63, 69, 71 give NameError in test_D) in Finding 2 
The other imports resolve the module loads under FastAPI 0.162.0 and Pydantic 2.14.2 and
SQLAlchemy 2.1.6 and (Query(ge=1)) (Field(decimal_places=2)) (scalar_one()) and (scalars().all()) ran without error in the happy-path test and (class Config) is deprecated in Finding 4

3. Is it safe? 
queries are built with SQLAlchemy column expressions with no raw SQL or string formatting 
(lines 60,76) so no SQL injection and (id) is typed UUID so a malformed id is rejected by validation But there is no authentication or ownership check with no credentials the endpoint returned 200 with customer name address and COD amount as we see in test_F and Finding 1

4. Does it already exist? 
i didn't understand where should i search

5. Is it efficient enough? 
two queries per request (a count and the page) both filtered with offset/limit in the database so no N+1 and nothing loaded whole into memory I did not measure anything and whether (courier_id, created_at) is indexed cannot be seen from this code

6. Style and naming, last: 
ruff reports an unused (HTTPException) (F401, line 6, Finding 3) and (typing.List) (UP035/UP006, lines 3 and 31) The parameter name (id) shadows the builtin (line 51) and ruff B008 on (Depends) (line 51) I dismissed so it's the standard FastAPI pattern
------------------------------------------------------------------------------------------------------
### 5.
Fix : 
i fixed Finding 1 (missing authentication / IDOR) the most important finding that can be proven by the test in section 3 the endpoint now depends on (get_current_courier_id) and it returns 403 when the id in the URL is not the authenticated courier's id now (get_current_courier_id) rejects every request with 401 until real token validation is connected so the endpoint fails closed and this fixes the contract only till validating a real token needs Tawseel's auth system which i don't have if admins should see any courier's orders the ownership check needs to change and i didn't fix Finding 2 (Order is not defined) because that needs the project's real (Order) model 
the proof for it is in section 3

Diff (git diff 067eeb7 -- courier_orders.py):

diff --git a/courier_orders.py b/courier_orders.py
index c6c6e30..b49a0a5 100644
--- a/courier_orders.py
+++ b/courier_orders.py
@@ -44,11 +44,29 @@ async def get_db() -> AsyncSession:
     raise NotImplementedError

+async def get_current_courier_id() -> UUID:
+    """Return the authenticated courier's id.
+
+    Fails closed: until real token validation is wired in, every request is rejected.
+    """
+    raise HTTPException(
+        status_code=status.HTTP_401_UNAUTHORIZED,
+        detail="Not authenticated",
+        headers={"WWW-Authenticate": "Bearer"},
+    )
+
+
 # --- Endpoint ---

 @router.get("/{id}/orders", response_model=PaginatedOrdersResponse, status_code=status.HTTP_200_OK, summary="Get courier orders for today",)
-async def get_courier_today_orders(id: UUID, page: int = Query(default=1, ge=1, description="Page number"), db: AsyncSession = Depends(get_db),):
+async def get_courier_today_orders(id: UUID, page: int = Query(default=1, ge=1, description="Page number"), db: AsyncSession = Depends(get_db), current_courier_id: UUID = Depends(get_current_courier_id),):
+    if id != current_courier_id:
+        raise HTTPException(
+            status_code=status.HTTP_403_FORBIDDEN,
+            detail="You can only view your own orders",
+        )
+    
     page_size = 20
     offset = (page - 1) * page_size

(END)

tests result : test_F_orders_require_authentication is unchanged from section 3 and now passes and i added an (authed_client) fixture (the caller is authenticated as the courier) and a test that another courier's id returns 403, the happy-path test now uses (authed_client) because the endpoint now needs an identity and test_D is deselected because the 401 now stops the request before it reaches (Order)

Command :
py -m pytest -v --tb=short test_courier_orders.py --deselect test_courier_orders.py::test_D_endpoint_works_without_defining_Order

Output:

E   AssertionError: got 200 : {"items":[{"id":"fc1cf936-399e-4e79-a3e6-1e1b562a7771","customer_name":"mohammed Fawzy","delivery_address":"12 , Tahrir street , Cairo , Egypt","status":"assigned","cash_on_delivery_amount":"150.00","
E   assert 200 in (401, 403)
E    +  where 200 = <Response [200 OK]>.status_code
__________________________________________________ test_D_endpoint_works_without_defining_Order ___________________________________________________
test_courier_orders.py:78: in test_D_endpoint_works_without_defining_Order
    resp = await bare_client.get(f"/couriers/{uuid.uuid4()}/orders")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1768: in get
    return await self.request(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1540: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1629: in send
    response = await self._send_handling_auth(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1657: in _send_handling_auth
    response = await self._send_handling_redirects(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1694: in _send_handling_redirects
    response = await self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_client.py:1730: in _send_single_request
    response = await transport.handle_async_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\httpx\_transports\asgi.py:170: in handle_async_request
    await self.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\applications.py:1194: in __call__
    await super().__call__(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\applications.py:96: in __call__
    await self.middleware_stack(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\middleware\errors.py:186: in __call__
    raise exc
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\middleware\errors.py:164: in __call__
    await self.app(scope, receive, _send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\telemetry\_asgi.py:151: in __call__
    await self.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\middleware\exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:53: in wrapped_app
    raise exc
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\middleware\asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\routing.py:683: in __call__
    await self.middleware_stack(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:2811: in app
    await route.handle(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:1839: in handle
    await self.original_router.handle(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:2894: in handle
    await included_router._handle_selected(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:1865: in _handle_selected
    await original_route.handle(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:1328: in handle
    await effective_context.app(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:166: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:53: in wrapped_app
    raise exc
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\starlette\_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:152: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:745: in app
    raw_response = await run_endpoint_function(
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\routing.py:372: in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
courier_orders.py:60: in get_courier_today_orders
    filters = [Order.courier_id == id, Order.created_at >= today_start, Order.created_at <= today_end,]
               ^^^^^
E   NameError: name 'Order' is not defined
================================================================ warnings summary =================================================================
courier_orders.py:14
  D:\DSC\Ai-Fluency\Week-3\courier_orders.py:14: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.14/migration/
    class OrderOut(BaseModel):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============================================================= short test summary info =============================================================
FAILED test_courier_orders.py::test_F_orders_require_authentication - AssertionError: got 200 : {"items":[{"id":"fc1cf936-399e-4e79-a3e6-1e1b562a7771","customer_name":"mohammed Fawzy","delivery_address":"12 , Tahr...
FAILED test_courier_orders.py::test_D_endpoint_works_without_defining_Order - NameError: name 'Order' is not defined
===================================================== 2 failed, 1 passed, 1 warning in 1.74s ======================================================
PS D:\DSC\Ai-Fluency\Week-3> py -m pytest -v --tb=short test_courier_orders.py | Out-File proof_output.txt -Encoding utf8   
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\pytest_asyncio\plugin.py:300: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
PS D:\DSC\Ai-Fluency\Week-3> git diff 067eeb7 -- courier_orders.py
PS D:\DSC\Ai-Fluency\Week-3> 
 *  History restored 

PS D:\DSC\Ai-Fluency\Week-3> 
 *  History restored 

PS D:\DSC\Ai-Fluency\Week-3> py -m pytest -v --tb=short test_courier_orders.py --deselect test_courier_orders.py::test_D_endpoint_works_without_defining_Order
C:\Users\moham\AppData\Local\Programs\Python\Python312\Lib\site-packages\pytest_asyncio\plugin.py:300: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loopscope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
=============================================================== test session starts ===============================================================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\moham\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: D:\DSC\Ai-Fluency\Week-3
plugins: anyio-4.15.1, asyncio-1.4.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 4 items / 1 deselected / 3 selected                                                                                                      

test_courier_orders.py::test_F_orders_require_authentication PASSED                                                                          [ 33%]
test_courier_orders.py::test_baseline_happy_path PASSED                                                                                      [ 66%]
test_courier_orders.py::test_F_courier_cannot_read_other_couriers_orders PASSED                                                              [100%]

================================================================ warnings summary =================================================================
courier_orders.py:14
  D:\DSC\Ai-Fluency\Week-3\courier_orders.py:14: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead.Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.14/migration/
    class OrderOut(BaseModel):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================================================== 3 passed, 1 deselected, 1 warning in 3.14s ====================================================
PS D:\DSC\Ai-Fluency\Week-3> 

Fix commit: https://github.com/mohamedfawzy29/ai-fluency-w3/commit/b2226e8
------------------------------------------------------------------------------------------------------
### 6.
AI_LOG.md : 

### 2026-11-02 · Gemini flash 3.8 · mohamedfawzy29
- **Task:** asked for a FastAPI endpoint GET /couriers/{id}/orders?page= for Tawseel (today's orders, newest first, 20 per page, with the cash-on-delivery amount)
- **What it produced:** https://github.com/mohamedfawzy29/ai-fluency-w3/commit/067eeb7
- **What was wrong:** security
- **How you caught it:** wrote a pytest test that calls the endpoint with no credentials and expects 401/403 on the original code it returned 200 with the customer's name address and COD amount and ruff also flagged the undefined (Order)
- **The fix:** https://github.com/mohamedfawzy29/ai-fluency-w3/commit/b2226e8
- **Lesson:** don't give AI all your trust: its code can look clean and pass the happy path while having no authentication so test what it skipped like a request with no credentials