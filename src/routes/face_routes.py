from flask import Blueprint, request, jsonify
from src.services.face_service import FaceService

face_bp = Blueprint("face", __name__, url_prefix="/api/face")
svc = FaceService()


@face_bp.route("/age", methods=["POST"])
def detect_age():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    img_bytes = request.files["file"].read()

    age = svc.detect_age(img_bytes)
    age_group = svc.to_age_group(age)

    return jsonify({
        "age": age,
        "age_group": age_group
    })
