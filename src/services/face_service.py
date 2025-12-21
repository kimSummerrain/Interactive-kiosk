import tempfile
from deepface import DeepFace


class FaceService:
    def detect_age(self, img_bytes: bytes) -> int:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as tmp:
            tmp.write(img_bytes)
            tmp.flush()

            result = DeepFace.analyze(
                img_path=tmp.name,
                actions=["age"],
                enforce_detection=True
            )

        if isinstance(result, list):
            result = result[0]

        return int(result["age"])

    def to_age_group(self, age: int) -> str:
        if age <= 40:
            return "10_40"
        else:
            return "41_50"
