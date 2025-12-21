from flask import Blueprint, jsonify, request
from src.services.stats_service import StatsService

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")
svc = StatsService()


@stats_bp.route("/age/<age_group>", methods=["GET"])
def get_stats(age_group):
    data = svc.get_menu_stats(age_group)
    if not data:
        return jsonify({"error": "age_group not found"}), 404
    return jsonify(data)


@stats_bp.route("/click", methods=["POST"])
def click_menu():
    body = request.get_json()
    age_group = body.get("age_group")
    menu_id = body.get("menu_id")

    if not age_group or not menu_id:
        return jsonify({"error": "missing age_group or menu_id"}), 400

    svc.increment_menu_click(age_group, menu_id)
    return jsonify({"result": "ok"})
