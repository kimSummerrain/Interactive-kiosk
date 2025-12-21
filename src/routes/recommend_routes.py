from flask import Blueprint, request, current_app
from src.services.recommend_service import RecommendService

recommend_bp = Blueprint("recommend", __name__, url_prefix="/api")


@recommend_bp.post("/recommend")
def recommend():
    """
    multipart/form-data:
      - file: 얼굴 사진
      - menu_id: (선택) 사용자가 방금 선택한 메뉴 ID (통계 +1 반영)
    return: JSON 추천 결과 (스키마 강제)
    """
    if "file" not in request.files:
        return {"error": "file is required (multipart/form-data)"}, 400

    img_bytes = request.files["file"].read()
    if not img_bytes:
        return {"error": "empty file"}, 400

    menu_id = request.form.get("menu_id")  # optional

    settings = current_app.config["SETTINGS"]
    svc = RecommendService(settings=settings)

    result = svc.recommend_from_image(img_bytes=img_bytes, selected_menu_id=menu_id)
    return result
