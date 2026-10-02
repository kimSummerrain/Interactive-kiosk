import tempfile
from pathlib import Path


class FaceService:
    def detect_age(self, img_bytes: bytes) -> int:
        # Ordinary menu/orders work without optional ML packages.
        from deepface import DeepFace
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(img_bytes)
            image_path = tmp.name
        try:
            result = DeepFace.analyze(
                img_path=image_path,
                actions=["age"],
                enforce_detection=True
            )
        finally:
            Path(image_path).unlink(missing_ok=True)

        if isinstance(result, list):
            result = result[0]

        return int(result["age"])

    def to_age_group(self, age: int) -> str:
        if age <= 40:
            return "10_40"
        else:
            return "41_50"
