import json
import re

from models import LLMProductCard
from prompts import SYSTEM_PROMPT, build_prompt


class LLMClient:
    def __init__(self, api_key, model):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_product_description(self, sort_name, raw_text, product_type):
        prompt = build_prompt(sort_name, raw_text, product_type)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        return response.choices[0].message.content

    def extract_json_payload(self, content):
        raw_content = (content or "").strip()
        if not raw_content:
            raise ValueError("LLM вернул пустой ответ")

        try:
            return json.loads(raw_content)
        except json.JSONDecodeError:
            pass

        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_content, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1))

        start = raw_content.find("{")
        if start == -1:
            raise ValueError("В ответе LLM не найден JSON-объект")

        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(raw_content)):
            char = raw_content[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw_content[start : index + 1]
                    return json.loads(candidate)

        raise ValueError("Не удалось извлечь валидный JSON из ответа LLM")

    def build_product_card(self, sort_name, aggregated_sources_text, product_type="petunia"):
        last_error = None

        for attempt in range(1, 3):
            print(f"LLM: попытка {attempt} для сорта {sort_name}", flush=True)

            try:
                content = self.generate_product_description(
                    sort_name=sort_name,
                    raw_text=aggregated_sources_text,
                    product_type=product_type,
                )
                payload = self.extract_json_payload(content)

                return LLMProductCard(
                    vk_title=payload.get("vk_title") or sort_name,
                    vk_short_description=payload.get("vk_short_description"),
                    vk_full_description=payload.get("vk_full_description") or "",
                    name_ru=payload.get("name_ru"),
                    name_en=payload.get("name_en"),
                    plant_type=payload.get("plant_type"),
                    series_name=payload.get("series_name"),
                    color=payload.get("color"),
                    flower_size=payload.get("flower_size"),
                    plant_size=payload.get("plant_size"),
                    growth_power=payload.get("growth_power"),
                    pot_volume=payload.get("pot_volume"),
                    placement=payload.get("placement"),
                    lighting=payload.get("lighting"),
                    care_level=payload.get("care_level"),
                    weather_resistance=payload.get("weather_resistance"),
                    features=payload.get("features"),
                    suitable_for_beginners=payload.get("suitable_for_beginners"),
                    growth_type=payload.get("growth_type"),
                    fruit_weight=payload.get("fruit_weight"),
                    taste=payload.get("taste"),
                    use_case=payload.get("use_case"),
                    care_notes=payload.get("care_notes"),
                    suitable_for_greenhouse=payload.get("suitable_for_greenhouse"),
                    suitable_for_open_ground=payload.get("suitable_for_open_ground"),
                )
            except Exception as error:
                last_error = error
                print(
                    f"Ошибка LLM для {sort_name} на попытке {attempt}: {error}",
                    flush=True,
                )

        raise RuntimeError(f"LLM не вернул валидный JSON: {last_error}")
