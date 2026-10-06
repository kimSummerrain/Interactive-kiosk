import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from src.config import Settings
from src.schemas import MenuList, Order, OrderInput, OrderList, OrderResult, OrderStatus, OrderUpdate, Recommendation, SalesSummary
from src.services.face_service import FaceService
from src.schemas import HourlySales, MenuCreate, MenuUpdate, OptionInput
from src.storage import KST, Store, StoreError

BASE = Path(__file__).resolve().parent.parent


def create_app(database_path=None):
    settings = Settings.load()
    store = Store(database_path or settings.sqlite_db_path)
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "")
    security = HTTPBasic(auto_error=False)

    @asynccontextmanager
    async def lifespan(app):
        store.initialize(seed_path=BASE / "data" / "seed.db" if database_path is None else None)
        yield

    app = FastAPI(title="Interactive Kiosk API", version="1.0.0", lifespan=lifespan,
                  description="고객 앱의 메뉴·주문 API와 인증된 관리자 주문·매출 API")
    app.state.store = store
    app.add_middleware(CORSMiddleware,
                       allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if origin.strip()],
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"])
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    serve_web = os.getenv("SERVE_WEB", "true").lower() in ("true", "1", "yes")
    if serve_web:
        app.mount("/kiosk-static", StaticFiles(directory=BASE.parent / "frontend-app" / "kiosk" / "static"), name="kiosk-static")
        app.mount("/admin-static", StaticFiles(directory=BASE.parent / "frontend-web" / "admin" / "static"), name="admin-static")

    @app.exception_handler(StoreError)
    async def store_error(_request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    def admin(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
        if not password:
            raise HTTPException(503, "서버의 ADMIN_PASSWORD를 설정해 주세요.")
        valid_user = secrets.compare_digest((credentials.username if credentials else "").encode(), username.encode())
        valid_password = secrets.compare_digest((credentials.password if credentials else "").encode(), password.encode())
        if not (valid_user and valid_password):
            raise HTTPException(401, "관리자 아이디 또는 비밀번호가 올바르지 않습니다.")
        return username

    def period(start: Optional[date] = None, end: Optional[date] = None):
        today = datetime.now(KST).date()
        start, end = start or today, end or today
        if start > end or (end - start).days > 366 or end == date.max:
            raise HTTPException(422, "조회 기간은 시작일 이후 최대 366일로 지정해 주세요.")
        return start, end

    def kiosk():
        return FileResponse(BASE.parent / "frontend-app" / "kiosk" / "index.html")

    def admin_page():
        return FileResponse(BASE.parent / "frontend-web" / "admin" / "index.html")

    if serve_web:
        app.add_api_route("/", kiosk, include_in_schema=False)
        app.add_api_route("/kiosk", kiosk, include_in_schema=False)
        app.add_api_route("/admin", admin_page, include_in_schema=False)

    @app.get("/health", tags=["system"])
    def health():
        return {"ok": True}

    @app.get("/api/menus", response_model=MenuList, tags=["customer"])
    def menus():
        return {"menus": store.menus()}

    @app.get("/api/weather/now", tags=["customer"])
    def weather():
        return {"weather": store.weather()}

    @app.post("/api/recommend", response_model=Recommendation, tags=["customer"])
    def recommend(file: UploadFile = File(...)):
        try:
            if not (file.content_type or "").startswith("image/"):
                raise HTTPException(415, "이미지 파일을 선택해 주세요.")
            image = file.file.read(10 * 1024 * 1024 + 1)
            if not image or len(image) > 10 * 1024 * 1024:
                raise HTTPException(413, "비어 있지 않은 10MB 이하 이미지를 선택해 주세요.")
            service = FaceService()
            try:
                age = service.detect_age(image)
            except (ImportError, ModuleNotFoundError):
                raise HTTPException(503, "사진 추천이 준비되지 않았어요. 일반 메뉴로 주문해 주세요.")
            except ValueError:
                raise HTTPException(422, "얼굴을 인식하지 못했어요. 사진을 다시 선택해 주세요.")
            except Exception:
                raise HTTPException(503, "사진 추천을 잠시 사용할 수 없어요. 일반 메뉴로 주문해 주세요.")
            group = service.to_age_group(age)
            return {"age_group": group, "menus": store.recommended_menus(group)}
        finally:
            file.file.close()

    @app.post("/api/orders", response_model=OrderResult, tags=["customer"])
    def create_order(payload: OrderInput):
        return {"result": "OK", "order": store.create_order(payload)}

    @app.post("/api/order-quotes", tags=["customer"])
    def quote_order(payload: OrderInput):
        return store.quote(payload)

    @app.post("/api/orders/confirm", response_model=OrderResult, tags=["customer"])
    def confirm_order(payload: OrderInput):
        if payload.quote_id is None:
            raise HTTPException(422, "확인한 quote_id가 필요합니다.")
        if payload.payment_method != "counter":
            raise HTTPException(422, "현재는 현장 결제만 지원합니다.")
        return {"result": "OK", "order": store.create_order(payload)}

    @app.get("/api/owner/menus", response_model=MenuList, tags=["owner"], dependencies=[Depends(admin)])
    def owner_menus():
        return {"menus": store.menus()}

    @app.post("/api/owner/menus", status_code=201, tags=["owner"], dependencies=[Depends(admin)])
    def add_menu(payload: MenuCreate):
        return store.add_menu(payload)

    @app.patch("/api/owner/menus/{menu_id}", tags=["owner"], dependencies=[Depends(admin)])
    def edit_menu(menu_id: str, payload: MenuUpdate):
        return store.update_menu(menu_id, payload)

    @app.post("/api/owner/menus/{menu_id}/options", tags=["owner"], dependencies=[Depends(admin)])
    def edit_option(menu_id: str, payload: OptionInput):
        return store.save_option(menu_id, payload)

    @app.get("/api/owner/me", tags=["owner"])
    @app.get("/api/admin/me", tags=["admin"])
    def me(user=Depends(admin)):
        return {"username": user}

    @app.get("/api/owner/orders", response_model=OrderList, tags=["owner"], dependencies=[Depends(admin)])
    @app.get("/api/admin/orders", response_model=OrderList, tags=["admin"], dependencies=[Depends(admin)])
    def orders(dates=Depends(period), status: Optional[OrderStatus] = None,
               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        return store.orders(*dates, status, page, page_size)

    @app.get("/api/owner/orders/{order_id}", response_model=Order, tags=["owner"], dependencies=[Depends(admin)])
    @app.get("/api/admin/orders/{order_id}", response_model=Order, tags=["admin"], dependencies=[Depends(admin)])
    def order_detail(order_id: int):
        with store.connect() as db:
            return store.read_order(db, order_id)

    @app.patch("/api/owner/orders/{order_id}", response_model=Order, tags=["owner"], dependencies=[Depends(admin)])
    @app.patch("/api/admin/orders/{order_id}", response_model=Order, tags=["admin"], dependencies=[Depends(admin)])
    def update_order(order_id: int, payload: OrderUpdate):
        return store.update_order(order_id, payload)

    @app.get("/api/owner/sales", response_model=SalesSummary, tags=["owner"], dependencies=[Depends(admin)])
    @app.get("/api/admin/sales", response_model=SalesSummary, tags=["admin"], dependencies=[Depends(admin)])
    def sales(dates=Depends(period)):
        return store.summary(*dates)

    @app.get("/api/owner/sales/hourly", response_model=HourlySales, tags=["owner"], dependencies=[Depends(admin)])
    def hourly_sales(dates=Depends(period), start_hour: int = Query(0, ge=0, le=23),
                     end_hour: int = Query(24, ge=1, le=24),
                     menu_id: Optional[str] = Query(None, min_length=1, max_length=80)):
        if start_hour >= end_hour:
            raise HTTPException(422, "종료 시간은 시작 시간보다 커야 합니다.")
        return store.hourly_sales(*dates, start_hour, end_hour, menu_id)

    return app
