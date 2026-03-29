from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator


class SourceRecord(BaseModel):
    product_id: Union[int, str]
    source_url: str
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    source_title: Optional[str] = None
    parsed_text_raw: str
    parsed_characteristics_raw: Optional[str] = None
    is_selected: Optional[bool] = True


class LLMProductCard(BaseModel):
    vk_title: str
    vk_full_description: str
    vk_short_description: Optional[str] = None
    name_ru: Optional[str] = None
    name_en: Optional[str] = None
    plant_type: Optional[str] = None
    series_name: Optional[str] = None
    color: Optional[str] = None
    flower_size: Optional[str] = None
    plant_size: Optional[str] = None
    growth_power: Optional[str] = None
    pot_volume: Optional[str] = None
    placement: Optional[str] = None
    lighting: Optional[str] = None
    care_level: Optional[str] = None
    weather_resistance: Optional[str] = None
    features: Optional[str] = None
    suitable_for_beginners: Optional[bool] = None
    growth_type: Optional[str] = None
    fruit_weight: Optional[str] = None
    taste: Optional[str] = None
    use_case: Optional[str] = None
    care_notes: Optional[str] = None
    suitable_for_greenhouse: Optional[bool] = None
    suitable_for_open_ground: Optional[bool] = None

    @model_validator(mode="after")
    def fill_vk_short_description(self):
        if not self.vk_short_description:
            self.vk_short_description = self.vk_full_description[:220].strip()
        return self


class ProductDraftUpdate(BaseModel):
    vk_title: str
    vk_short_description: str
    vk_full_description: str
    sales_tail_template: str
    vk_final_description: str
    name_ru: Optional[str] = None
    name_en: Optional[str] = None
    plant_type: Optional[str] = None
    series_name: Optional[str] = None
    color: Optional[str] = None
    flower_size: Optional[str] = None
    plant_size: Optional[str] = None
    growth_power: Optional[str] = None
    pot_volume: Optional[str] = None
    placement: Optional[str] = None
    lighting: Optional[str] = None
    care_level: Optional[str] = None
    weather_resistance: Optional[str] = None
    features: Optional[str] = None
    suitable_for_beginners: Optional[bool] = None
    growth_type: Optional[str] = None
    fruit_weight: Optional[str] = None
    taste: Optional[str] = None
    use_case: Optional[str] = None
    care_notes: Optional[str] = None
    suitable_for_greenhouse: Optional[bool] = None
    suitable_for_open_ground: Optional[bool] = None
    parsed_description_raw: str
    ai_description_structured: dict = Field(default_factory=dict)
    ai_description_vk: str
    ai_prompt_version: str
    status: str = "ai_ready"
