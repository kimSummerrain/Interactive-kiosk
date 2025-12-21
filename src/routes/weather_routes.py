from flask import Blueprint
from src.services.weather_service import WeatherService

weather_bp = Blueprint("weather", __name__, url_prefix="/api/weather")


@weather_bp.get("/now")
def weather_now():
    svc = WeatherService()
    data = svc.get_current_weather_from_db()
    return {"weather": data}
