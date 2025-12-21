# src/services/stats_service.py
from src.db.sqlite import get_db


class StatsService:

    def increment_menu_by_menu_id(self, age_group: str, menu_id: str) -> None:
        db = get_db()

        row = db.execute(
            "SELECT menu_index FROM menus WHERE menu_id = ?",
            (menu_id,),
        ).fetchone()

        if not row:
            return

        idx = row["menu_index"]
        col = f"menu_{idx}"

        db.execute(
            f"""
            UPDATE age_menu_stats
            SET {col} = {col} + 1
            WHERE age_group = ?
            """,
            (age_group,),
        )
        db.commit()


    def get_menu_stats(self, age_group: str) -> dict:
        db = get_db()
        row = db.execute(
            "SELECT * FROM age_menu_stats WHERE age_group = ?",
            (age_group,),
        ).fetchone()

        return dict(row) if row else {}


    def get_all_menus_with_stats(self, age_group: str):
        db = get_db()

        stats = db.execute(
            "SELECT * FROM age_menu_stats WHERE age_group = ?",
            (age_group,),
        ).fetchone()

        if not stats:
            return []

        menus = db.execute(
            """
            SELECT menu_id, menu_index, name, price, image_path
            FROM menus
            ORDER BY menu_index
            """
        ).fetchall()

        result = []
        for m in menus:
            idx = m["menu_index"]

            result.append({
                "menu_id": m["menu_id"],
                "name": m["name"],
                "price": m["price"],
                "image": f"/static/{m['image_path']}",
                "order_count": stats[f"menu_{idx}"]
            })

        return result
