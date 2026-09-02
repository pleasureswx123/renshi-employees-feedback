from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from module_feedback.entity.vo.questionnaire_question_vo import QuestionnaireVoModel

MAX_CODE_LENGTH = 64


class IndicatorDraftModel(QuestionnaireVoModel):
    """问卷指标及其题目标识绑定。"""

    indicator_id: int | None = Field(default=None, description='指标ID')
    indicator_code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    indicator_name: str = Field(min_length=1, max_length=100, description='指标名称')
    description: str | None = Field(default=None, max_length=5000, description='指标说明')
    weight: Decimal = Field(ge=0, le=100, max_digits=12, decimal_places=4, description='指标权重百分比')
    sort_order: int = Field(ge=1, description='指标顺序')
    question_codes: list[str] = Field(default_factory=list, max_length=500, description='绑定题目标识')

    @field_validator('indicator_name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('指标名称不能为空')
        return normalized

    @field_validator('description')
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator('question_codes')
    @classmethod
    def validate_question_codes(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or len(value) > MAX_CODE_LENGTH or not all(char.isalnum() or char in '_-' for char in value):
                raise ValueError('指标绑定包含非法题目标识')
        return values

    @model_validator(mode='after')
    def validate_bindings(self) -> 'IndicatorDraftModel':
        if len(self.question_codes) != len(set(self.question_codes)):
            raise ValueError('同一指标不能重复绑定同一道题')
        return self
