from flask import Blueprint, request, jsonify
from src.services.stats_service import StatsService

bp = Blueprint("order", __name__, url_prefix="/api/order")


@bp.route("/complete", methods=["POST"])
def complete_order():
    data = request.get_json(force=True)

    age_group = data.get("age_group")
    items = data.get("items", [])

    if not age_group or not items:
        return jsonify({"error": "INVALID_PAYLOAD"}), 400

    stats = StatsService()

    for item in items:
        menu_id = item.get("menu_id")
        qty = item.get("qty", 0)

        if not menu_id or qty <= 0:
            continue

        for _ in range(qty):
            stats.increment_menu_by_menu_id(age_group, menu_id)


    return jsonify({"result": "OK"})
