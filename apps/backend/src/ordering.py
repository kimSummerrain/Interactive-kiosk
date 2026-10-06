"""Single-store catalog, expiring quotes and transactional stock operations."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def canonical(data):
    return {**data, "items": sorted(
        [{**i, "option_ids": sorted(i["option_ids"])} for i in data["items"]],
        key=lambda i: (i["menu_id"], i["option_ids"]))}


def fingerprint(data):
    return hashlib.sha256(json.dumps(canonical(data), sort_keys=True).encode()).hexdigest()


def initialize_catalog(db):
    columns = {row[1] for row in db.execute("PRAGMA table_info(menus)")}
    if "available" not in columns:
        db.execute("ALTER TABLE menus ADD COLUMN available INTEGER NOT NULL DEFAULT 1")
    if "stock" not in columns:
        db.execute("ALTER TABLE menus ADD COLUMN stock INTEGER")
    # Preserve old order snapshots while allowing different options on the same menu.
    if "line_no" not in {row[1] for row in db.execute("PRAGMA table_info(order_items)")}:
        db.execute("ALTER TABLE order_items RENAME TO old_order_items")
        db.execute("""CREATE TABLE order_items (
            order_id INTEGER NOT NULL REFERENCES orders(id), line_no INTEGER NOT NULL,
            menu_id TEXT NOT NULL, name TEXT NOT NULL, price INTEGER NOT NULL,
            qty INTEGER NOT NULL, options TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY(order_id,line_no))""")
        db.execute("""INSERT INTO order_items(order_id,line_no,menu_id,name,price,qty)
            SELECT order_id,rowid,menu_id,name,price,qty FROM old_order_items""")
        db.execute("DROP TABLE old_order_items")
    db.execute("""CREATE TABLE IF NOT EXISTS menu_options (
        menu_id TEXT NOT NULL REFERENCES menus(menu_id), option_id TEXT NOT NULL,
        name TEXT NOT NULL, price INTEGER NOT NULL, available INTEGER NOT NULL,
        PRIMARY KEY(menu_id,option_id))""")
    db.execute("""CREATE TABLE IF NOT EXISTS quotes (
        id TEXT PRIMARY KEY, expires_at TEXT NOT NULL, payload_hash TEXT NOT NULL,
        snapshot TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY, menu_id TEXT NOT NULL REFERENCES menus(menu_id),
        order_id INTEGER REFERENCES orders(id), delta INTEGER NOT NULL,
        reason TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(order_id,menu_id,reason))""")


class CatalogMixin:
    def add_menu(self, payload):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM menus WHERE menu_id=?", (payload.menu_id,)).fetchone():
                self.error(409, "이미 등록된 메뉴 ID입니다.")
            index = db.execute("SELECT COALESCE(MAX(menu_index),0)+1 FROM menus").fetchone()[0]
            db.execute("""INSERT INTO menus(menu_id,menu_index,name,price,image_path,stock,available)
                VALUES (?,?,?,?,?,?,?)""", (payload.menu_id, index, payload.name, payload.price,
                                           None, payload.stock, payload.available))
        return next(m for m in self.menus() if m["menu_id"] == payload.menu_id)

    def error(self, status, message):
        # Deferred import avoids the storage/mixin import cycle.
        from src.storage import StoreError
        raise StoreError(status, message)

    def update_menu(self, menu_id, payload):
        changes = payload.model_dump(exclude_unset=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM menus WHERE menu_id=?", (menu_id,)).fetchone():
                self.error(404, "메뉴를 찾을 수 없습니다.")
            if "stock" in changes:
                before = db.execute("SELECT stock FROM menus WHERE menu_id=?", (menu_id,)).fetchone()[0]
                after = changes["stock"]
                if before is not None and after is not None:
                    db.execute("""INSERT INTO stock_movements(menu_id,delta,reason,created_at)
                        VALUES (?,?,?,?)""", (menu_id, after-before, "owner_adjustment",
                                              datetime.now(timezone.utc).isoformat()))
            db.execute(f"UPDATE menus SET {','.join(k+'=?' for k in changes)} WHERE menu_id=?",
                       [*changes.values(), menu_id])
        return next(m for m in self.menus() if m["menu_id"] == menu_id)

    def save_option(self, menu_id, payload):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM menus WHERE menu_id=?", (menu_id,)).fetchone():
                self.error(404, "메뉴를 찾을 수 없습니다.")
            db.execute("""INSERT INTO menu_options VALUES (?,?,?,?,?)
                ON CONFLICT(menu_id,option_id) DO UPDATE SET
                name=excluded.name,price=excluded.price,available=excluded.available""",
                       (menu_id, payload.option_id, payload.name, payload.price, payload.available))
        return payload.model_dump()

    def price_items(self, db, data):
        items, quantities = [], {}
        for item in data["items"]:
            menu = db.execute("SELECT * FROM menus WHERE menu_id=?", (item["menu_id"],)).fetchone()
            if not menu or not menu["available"]:
                self.error(422, "판매하지 않는 메뉴가 포함되어 있습니다.")
            options = []
            for option_id in sorted(item["option_ids"]):
                option = db.execute("""SELECT option_id,name,price FROM menu_options
                    WHERE menu_id=? AND option_id=? AND available=1""", (item["menu_id"], option_id)).fetchone()
                if not option:
                    self.error(422, "해당 메뉴에 사용할 수 없는 옵션입니다.")
                options.append(dict(option))
            quantities[menu["menu_id"]] = quantities.get(menu["menu_id"], 0) + item["qty"]
            if menu["stock"] is not None and quantities[menu["menu_id"]] > menu["stock"]:
                self.error(409, "판매 가능 수량이 부족합니다.")
            items.append(dict(menu_id=menu["menu_id"], name=menu["name"],
                              price=menu["price"] + sum(o["price"] for o in options),
                              qty=item["qty"], options=options))
        return dict(items=items, total=sum(i["price"] * i["qty"] for i in items))

    def quote(self, payload):
        data = payload.model_dump(mode="json")
        if data["quote_id"] is not None:
            self.error(422, "견적 생성 시 quote_id를 지정하지 마세요.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = self.price_items(db, canonical(data))
            now = datetime.now(timezone.utc)
            expires = (now + timedelta(minutes=5)).isoformat()
            quote_id = str(uuid4())
            db.execute("DELETE FROM quotes WHERE expires_at < ?", (now.isoformat(),))
            db.execute("INSERT INTO quotes VALUES (?,?,?,?)", (quote_id, expires, fingerprint(data),
                                                               json.dumps(result, sort_keys=True)))
        return dict(quote_id=quote_id, expires_at=expires, **result)

    def validate_quote(self, db, data, snapshot):
        if not data["quote_id"]:
            if any(i["option_ids"] for i in data["items"]):
                self.error(422, "옵션 주문은 견적을 먼저 확인하세요.")
            return  # Compatibility for the existing kiosk prototype.
        row = db.execute("SELECT * FROM quotes WHERE id=?", (data["quote_id"],)).fetchone()
        original = {**data, "quote_id": None}
        if not row or row["expires_at"] <= datetime.now(timezone.utc).isoformat():
            self.error(409, "견적이 만료되었습니다. 다시 확인하세요.")
        if row["payload_hash"] != fingerprint(original) or json.loads(row["snapshot"]) != snapshot:
            self.error(409, "주문 또는 가격이 변경되었습니다. 새 견적을 확인하세요.")

    def change_stock(self, db, order_id, items, restore=False):
        quantities = {}
        for item in items:
            quantities[item["menu_id"]] = quantities.get(item["menu_id"], 0) + item["qty"]
        for menu_id, qty in quantities.items():
            if restore:
                debit = db.execute("SELECT delta FROM stock_movements WHERE order_id=? AND menu_id=? AND reason='order'",
                                   (order_id, menu_id)).fetchone()
                if not debit:
                    continue
                delta = -debit["delta"]
            else:
                delta = -qty
            reason = "cancel" if restore else "order"
            menu = db.execute("SELECT stock FROM menus WHERE menu_id=?", (menu_id,)).fetchone()
            if menu["stock"] is None:
                continue
            cursor = db.execute("""INSERT OR IGNORE INTO stock_movements
                (menu_id,order_id,delta,reason,created_at) VALUES (?,?,?,?,?)""",
                (menu_id, order_id, delta, reason, datetime.now(timezone.utc).isoformat()))
            if cursor.rowcount:
                db.execute("UPDATE menus SET stock=stock+? WHERE menu_id=?", (delta, menu_id))
