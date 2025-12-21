from src.services.face_service import FaceService
from src.services.weather_service import WeatherService
from src.services.stats_service import StatsService
from src.config import Settings
from typing import Optional, Dict, List


class RecommendService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.face = FaceService()
        self.weather = WeatherService()
        self.stats = StatsService()

    def recommend_from_image(
        self,
        img_bytes: bytes,
        selected_menu_id: Optional[str]
    ) -> Dict:

    # 1) 얼굴 → age
        try:
            age = self.face.detect_age(img_bytes)
        except Exception:
            return {
                "error": "FACE_NOT_DETECTED",
                "message": "얼굴을 인식할 수 없습니다. 얼굴이 잘 보이게 다시 촬영해주세요."
            }

        age_group = self.face.to_age_group(age)

        # 2. 현재 날씨
        weather_now = self.weather.get_current_weather_from_db()

        # 3. 메뉴 + 통계 전체 조회
        menus = self.stats.get_all_menus_with_stats(age_group)

        # 4. 점수 계산
        results = []
        for m in menus:
            stat_score = m["order_count"] * 5
            weather_score = self.calc_weather_score(m["menu_id"], weather_now)

            total_score = stat_score + weather_score

            results.append({
                "menu_id": m["menu_id"],
                "name": m["name"],
                "price": m["price"],
                "image": m["image"],
                "score": total_score
            })

        # 5. 점수 내림차순 정렬
        results.sort(key=lambda x: x["score"], reverse=True)

        return {
            "menus": results,
            "_debug": {
                "age": age,
                "age_group": age_group,
                "weather": weather_now
            }
        }

    def calc_weather_score(
        self,
        menu_key: str,
        weather: Optional[Dict]
    ) -> int:
        if not weather:
            return 0

        score = 0
        temp = weather["temperature"]
        sky = weather["weather"]

        if temp <= 10 and "hot" in menu_key:
            score += 3

        if temp >= 25 and "ice" in menu_key:
            score += 3

        if sky in ("rain", "snow") and "hot" in menu_key:
            score += 2

        return score
