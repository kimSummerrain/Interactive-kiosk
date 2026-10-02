"""SQLite transactions and immutable order snapshots; no HTTP framework context."""
import hashlib
import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
SEED_MENUS = [
    ("ame_hot", "핫아메리카노", 1500), ("ame_ice", "아이스아메리카노", 1800),
    ("latte_hot", "핫카페라떼", 2300), ("latte_ice", "아이스카페라떼", 2300),
    ("choco_hot", "핫초코라떼", 3200), ("choco_ice", "아이스초코라떼", 3200),
    ("straw_smoothie", "딸기스무디", 3500), ("blue_smoothie", "블루베리스무디", 3500),
    ("mango_smoothie", "망고스무디", 3500), ("yogurt_smoothie", "요거트스무디", 3500),
    ("chamomile_hot", "핫캐모마일티", 2800), ("chamomile_ice", "아이스캐모마일티", 2800),
    ("lemon_hot", "핫레몬티", 3200), ("lemon_ice", "아이스레몬티", 3200),
]


class StoreError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def category(menu_id):
    if "smoothie" in menu_id:
        return "smoothie"
    if any(key in menu_id for key in ("lemon", "chamomile", "tea", "earl", "grapefruit")):
        return "tea"
    return "coffee"


class Store:
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self, seed_path=None):
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() and seed_path and Path(seed_path).exists():
            shutil.copy2(seed_path, target)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS menus (
                    menu_id TEXT PRIMARY KEY, menu_index INTEGER NOT NULL,
                    name TEXT NOT NULL, price INTEGER NOT NULL, image_path TEXT);
                CREATE TABLE IF NOT EXISTS weather_hourly (
                    datetime TEXT PRIMARY KEY, temperature REAL, weather TEXT);
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE, payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL, order_mode TEXT NOT NULL,
                    payment_method TEXT NOT NULL, age_group TEXT,
                    payment_status TEXT NOT NULL DEFAULT 'unpaid',
                    status TEXT NOT NULL DEFAULT 'pending', total INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS order_items (
                    order_id INTEGER NOT NULL REFERENCES orders(id),
                    menu_id TEXT NOT NULL, name TEXT NOT NULL,
                    price INTEGER NOT NULL, qty INTEGER NOT NULL,
                    PRIMARY KEY (order_id, menu_id));
                CREATE INDEX IF NOT EXISTS orders_created_at ON orders(created_at);
                CREATE INDEX IF NOT EXISTS orders_status ON orders(status);
            """)
            if db.execute("SELECT COUNT(*) FROM menus").fetchone()[0] == 0:
                db.executemany("INSERT INTO menus VALUES (?,?,?,?,?)", [
                    (menu_id, index, name, price, f"images/{menu_id}.png")
                    for index, (menu_id, name, price) in enumerate(SEED_MENUS, 1)
                ])

    def menus(self):
        with self.connect() as db:
            return [dict(menu_id=row["menu_id"], name=row["name"], price=row["price"],
                         image=f"/static/{row['image_path']}", category=category(row["menu_id"]))
                    for row in db.execute("SELECT * FROM menus ORDER BY menu_index")]

    def weather(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM weather_hourly WHERE datetime=?",
                             (datetime.now(KST).strftime("%Y-%m-%d %H"),)).fetchone()
            return dict(row) if row else None

    def recommended_menus(self, age_group):
        menus = self.menus()
        weather = self.weather()
        with self.connect() as db:
            # New paid orders plus legacy aggregate history, if present.
            counts = {row["menu_id"]: row["qty"] for row in db.execute("""
                SELECT i.menu_id,SUM(i.qty) qty FROM order_items i JOIN orders o ON o.id=i.order_id
                WHERE o.age_group=? AND o.payment_status='paid' AND o.status!='cancelled'
                GROUP BY i.menu_id""", (age_group,))}
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='age_menu_stats'").fetchone():
                legacy = db.execute("SELECT * FROM age_menu_stats WHERE age_group=?", (age_group,)).fetchone()
                if legacy:
                    for row in db.execute("SELECT menu_id,menu_index FROM menus"):
                        key = f"menu_{row['menu_index']}"
                        counts[row["menu_id"]] = counts.get(row["menu_id"], 0) + (legacy[key] or 0 if key in legacy.keys() else 0)
        def score(menu):
            result = counts.get(menu["menu_id"], 0) * 5
            if weather and weather["temperature"] is not None:
                hot = "hot" in menu["menu_id"]
                cold = "ice" in menu["menu_id"] or menu["category"] == "smoothie"
                result += 3 if (weather["temperature"] <= 10 and hot) or (weather["temperature"] >= 25 and cold) else 0
                result += 2 if weather["weather"] in ("rain", "snow") and hot else 0
            return result
        return sorted(menus, key=score, reverse=True)

    @staticmethod
    def read_order(db, order_id):
        row = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            raise StoreError(404, "주문을 찾을 수 없습니다.")
        result = {key: row[key] for key in ("id", "created_at", "order_mode", "payment_method", "payment_status", "status", "total")}
        result["order_number"] = f"{row['id']:04d}"
        result["items"] = [dict(item) for item in db.execute(
            "SELECT menu_id,name,price,qty FROM order_items WHERE order_id=? ORDER BY rowid", (order_id,))]
        return result

    def create_order(self, payload):
        data = payload.model_dump(mode="json")
        canonical = {**data, "items": sorted(data["items"], key=lambda item: item["menu_id"])}
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id,payload_hash FROM orders WHERE request_id=?", (data["request_id"],)).fetchone()
            if existing:
                if existing["payload_hash"] != digest:
                    raise StoreError(409, "같은 요청 번호로 다른 주문을 보낼 수 없습니다.")
                return self.read_order(db, existing["id"])
            items = []
            for item in data["items"]:
                menu = db.execute("SELECT * FROM menus WHERE menu_id=?", (item["menu_id"],)).fetchone()
                if not menu:
                    raise StoreError(422, "판매하지 않는 메뉴가 포함되어 있습니다.")
                items.append((menu["menu_id"], menu["name"], menu["price"], item["qty"]))
            total = sum(price * qty for _, _, price, qty in items)
            cursor = db.execute("""INSERT INTO orders
                (request_id,payload_hash,created_at,order_mode,payment_method,age_group,total)
                VALUES (?,?,?,?,?,?,?)""", (data["request_id"], digest, datetime.now(KST).isoformat(timespec="seconds"),
                                           data["order_mode"], data["payment_method"], data["age_group"], total))
            order_id = cursor.lastrowid
            db.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", [(order_id, *item) for item in items])
            return self.read_order(db, order_id)

    @staticmethod
    def date_filter(start, end):
        return "created_at >= ? AND created_at < ?", [start.isoformat(), (end + timedelta(days=1)).isoformat()]

    def orders(self, start, end, status, page, page_size):
        where, params = self.date_filter(start, end)
        if status:
            where += " AND status=?"
            params.append(status)
        with self.connect() as db:
            total = db.execute(f"SELECT COUNT(*) FROM orders WHERE {where}", params).fetchone()[0]
            rows = db.execute(f"SELECT id FROM orders WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                              [*params, page_size, (page - 1) * page_size]).fetchall()
            return dict(orders=[self.read_order(db, row["id"]) for row in rows], total=total, page=page, page_size=page_size)

    def update_order(self, order_id, changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            order = self.read_order(db, order_id)
            status = changes.status or order["status"]
            payment = changes.payment_status or order["payment_status"]
            allowed = {"pending": {"pending", "preparing", "cancelled"}, "preparing": {"preparing", "completed", "cancelled"},
                       "completed": {"completed"}, "cancelled": {"cancelled"}}
            if status not in allowed[order["status"]]:
                raise StoreError(409, "현재 주문 상태에서 변경할 수 없습니다.")
            if status == "cancelled" and payment == "paid":
                raise StoreError(409, "결제 완료 주문의 취소는 환불 처리가 필요합니다. 현재는 미결제 주문만 취소할 수 있습니다.")
            if status == "completed" and payment != "paid":
                raise StoreError(409, "결제 확인 후 주문을 완료해 주세요.")
            db.execute("UPDATE orders SET status=?,payment_status=? WHERE id=?", (status, payment, order_id))
            return self.read_order(db, order_id)

    def summary(self, start, end):
        where, params = self.date_filter(start, end)
        with self.connect() as db:
            result = dict(db.execute(f"""SELECT COUNT(*) order_count,
                COALESCE(SUM(payment_status='paid' AND status!='cancelled'),0) paid_count,
                COALESCE(SUM(status IN ('pending','preparing')),0) pending_count,
                COALESCE(SUM(status='cancelled'),0) cancelled_count,
                COALESCE(SUM(CASE WHEN payment_status='paid' AND status!='cancelled' THEN total ELSE 0 END),0) revenue
                FROM orders WHERE {where}""", params).fetchone())
            result["daily"] = [dict(row) for row in db.execute(f"""SELECT substr(created_at,1,10) date,
                COUNT(*) orders,SUM(total) revenue FROM orders WHERE {where}
                AND payment_status='paid' AND status!='cancelled' GROUP BY substr(created_at,1,10) ORDER BY date""", params)]
            result["top_menus"] = [dict(row) for row in db.execute(f"""SELECT i.menu_id,MAX(i.name) name,
                SUM(i.qty) quantity,SUM(i.qty*i.price) revenue FROM order_items i JOIN orders o ON o.id=i.order_id
                WHERE {where} AND payment_status='paid' AND status!='cancelled'
                GROUP BY i.menu_id ORDER BY quantity DESC,i.menu_id LIMIT 10""", params)]
            return result
