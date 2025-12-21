from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict

from src.db.sqlite import get_db


class WeatherService:
    def __init__(self):
        self.tz = ZoneInfo("Asia/Seoul")

    def get_current_weather_from_db(self) -> Optional[Dict]:
        """
        현재 KST 기준 시간에 해당하는 weather_hourly 레코드 조회
        (없으면 None)
        """
        now = datetime.now(self.tz)
        key = now.strftime("%Y-%m-%d %H")  # ← 핵심

        db = get_db()
        row = db.execute(
            """
            SELECT datetime, temperature, weather
            FROM weather_hourly
            WHERE datetime = ?
            """,
            (key,),
        ).fetchone()

        if not row:
            return None

        return {
            "datetime": row["datetime"],
            "temperature": row["temperature"],
            "weather": row["weather"],
        }
