import json
from typing import Dict, List, Optional

from openai import OpenAI


class ChatGPTService:
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def score_menus(
        self,
        age_group: str,
        weather: Optional[Dict],
        menu_names: List[str],
    ) -> Dict[str, int]:
        """
        메뉴별 적합도 점수 계산 (0~5)
        GPT는 약간의 추천자과 그를 포함한 '점수 계산기' 역할만 수행
        """

        system_prompt = (
            "You are a scoring engine for a cafe kiosk system.\n"
            "Your task is to score each menu from 0 to 5 based on suitability.\n"
            "Return ONLY valid JSON.\n"
            "No explanations. No extra text."
        )

        user_payload = {
            "age_group": age_group,
            "weather": weather,
            "menus": menu_names,
            "instruction": (
                "Score each menu from 0 (very unsuitable) to 5 (very suitable). "
                "Return JSON in the format:\n"
                "{ \"menu_name\": score }"
            )
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                temperature=0.2,
            )

            content = response.choices[0].message.content
            scores = json.loads(content)

            # 안전장치: 점수 범위 강제
            validated_scores: Dict[str, int] = {}
            for menu in menu_names:
                value = scores.get(menu, 0)
                if not isinstance(value, int):
                    value = 0
                validated_scores[menu] = max(0, min(5, value))

            return validated_scores

        except Exception as e:
            # GPT 실패 시 → 전부 0점 처리 (서비스 안전성)
            return {menu: 0 for menu in menu_names}
