from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

MIN_STAR_COUNT = 2
MAX_STAR_COUNT = 10


class QuestionnaireVoModel(BaseModel):
    """问卷接口模型公共配置。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra='forbid',
    )


def decimal_places(value: Decimal) -> int:
    """返回十进制数实际携带的小数位数。"""
    return max(0, -value.normalize().as_tuple().exponent)


class EmptyQuestionConfigModel(QuestionnaireVoModel):
    """不允许题型写入未定义配置。"""


class NumericInputConfigModel(QuestionnaireVoModel):
    """数字输入题特有配置。"""

    default_value: Decimal | None = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description='默认值',
    )


class SliderConfigModel(QuestionnaireVoModel):
    """滑动评分题特有配置。"""

    step: Decimal = Field(gt=0, max_digits=12, decimal_places=4, description='滑动步长')
    default_value: Decimal | None = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description='默认值',
    )


class TextQuestionConfigModel(QuestionnaireVoModel):
    """问答题特有配置。"""

    max_length: int = Field(default=1000, ge=1, le=5000, description='最大字数')


class QuestionOptionDraftModel(QuestionnaireVoModel):
    """单选题选项草稿。"""

    option_id: int | None = Field(default=None, description='选项ID')
    option_code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    option_label: str = Field(min_length=1, max_length=500, description='选项文本')
    score: Decimal = Field(default=Decimal('1'), ge=0, max_digits=12, decimal_places=4, description='选项分值，默认1分')
    requires_reason: bool = Field(default=False, description='选择后是否必须填写原因')
    sort_order: int = Field(ge=1, description='选项顺序')

    @field_validator('option_label')
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('选项文本不能为空')
        return normalized


class QuestionCommonDraftModel(QuestionnaireVoModel):
    """五种题型共用字段。"""

    question_id: int | None = Field(default=None, description='题目ID')
    question_code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    title: str = Field(min_length=1, max_length=2000, description='题目标题')
    description: str | None = Field(default=None, max_length=5000, description='题目说明')
    is_required: bool = Field(default=False, description='是否必答')
    is_scored: bool = Field(default=True, description='是否参与计分')
    sort_order: int = Field(ge=1, description='题目顺序')

    @field_validator('title')
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('题目标题不能为空')
        return normalized

    @field_validator('description')
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SingleChoiceQuestionDraftModel(QuestionCommonDraftModel):
    """单选题草稿。"""

    question_type: Literal['SINGLE_CHOICE'] = 'SINGLE_CHOICE'
    min_score: None = None
    max_score: None = None
    decimal_places: Literal[0] = 0
    config: EmptyQuestionConfigModel = Field(default_factory=EmptyQuestionConfigModel)
    options: list[QuestionOptionDraftModel] = Field(min_length=2, max_length=100)

    @model_validator(mode='after')
    def validate_options(self) -> 'SingleChoiceQuestionDraftModel':
        sort_orders = [item.sort_order for item in self.options]
        if sort_orders != list(range(1, len(self.options) + 1)):
            raise ValueError('同一题目的选项顺序必须从1开始连续排列')
        codes = [item.option_code for item in self.options]
        if len(codes) != len(set(codes)):
            raise ValueError('同一题目的选项标识不能重复')
        return self


class ScoreRangeQuestionDraftModel(QuestionCommonDraftModel):
    """数值区间评分题公共字段。"""

    min_score: Decimal = Field(ge=0, max_digits=12, decimal_places=4)
    max_score: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    decimal_places: int = Field(default=0, ge=0, le=4)
    options: list[QuestionOptionDraftModel] = Field(default_factory=list, max_length=0)

    @model_validator(mode='after')
    def validate_score_range(self) -> 'ScoreRangeQuestionDraftModel':
        if self.max_score <= self.min_score:
            raise ValueError('最高分必须大于最低分')
        if decimal_places(self.min_score) > self.decimal_places:
            raise ValueError('最低分精度不能超过允许小数位数')
        if decimal_places(self.max_score) > self.decimal_places:
            raise ValueError('最高分精度不能超过允许小数位数')
        return self


class StarRatingQuestionDraftModel(ScoreRangeQuestionDraftModel):
    """星级评分题草稿。"""

    question_type: Literal['STAR_RATING'] = 'STAR_RATING'
    decimal_places: Literal[0] = 0
    config: EmptyQuestionConfigModel = Field(default_factory=EmptyQuestionConfigModel)

    @model_validator(mode='after')
    def validate_star_range(self) -> 'StarRatingQuestionDraftModel':
        if self.min_score != self.min_score.to_integral_value() or self.max_score != self.max_score.to_integral_value():
            raise ValueError('星级评分的最低分和最高分必须是整数')
        star_count = int(self.max_score - self.min_score + 1)
        if star_count < MIN_STAR_COUNT or star_count > MAX_STAR_COUNT:
            raise ValueError('星级评分可选星数必须在2至10之间')
        return self


class NumericInputQuestionDraftModel(ScoreRangeQuestionDraftModel):
    """数字输入评分题草稿。"""

    question_type: Literal['NUMERIC_INPUT'] = 'NUMERIC_INPUT'
    config: NumericInputConfigModel = Field(default_factory=NumericInputConfigModel)

    @model_validator(mode='after')
    def validate_default_value(self) -> 'NumericInputQuestionDraftModel':
        default_value = self.config.default_value
        if default_value is None:
            return self
        if default_value < self.min_score or default_value > self.max_score:
            raise ValueError('数字输入题默认值必须位于评分区间内')
        if decimal_places(default_value) > self.decimal_places:
            raise ValueError('数字输入题默认值精度不能超过允许小数位数')
        return self


class SliderQuestionDraftModel(ScoreRangeQuestionDraftModel):
    """滑动评分题草稿。"""

    question_type: Literal['SLIDER'] = 'SLIDER'
    config: SliderConfigModel

    @model_validator(mode='after')
    def validate_slider_config(self) -> 'SliderQuestionDraftModel':
        step = self.config.step
        if step > self.max_score - self.min_score:
            raise ValueError('滑动评分步长不能大于评分区间')
        if decimal_places(step) > self.decimal_places:
            raise ValueError('滑动评分步长精度不能超过允许小数位数')
        default_value = self.config.default_value
        if default_value is None:
            return self
        if default_value < self.min_score or default_value > self.max_score:
            raise ValueError('滑动评分默认值必须位于评分区间内')
        if decimal_places(default_value) > self.decimal_places:
            raise ValueError('滑动评分默认值精度不能超过允许小数位数')
        if (default_value - self.min_score) % step != 0:
            raise ValueError('滑动评分默认值必须落在合法步长上')
        return self


class TextQuestionDraftModel(QuestionCommonDraftModel):
    """问答题草稿。"""

    question_type: Literal['TEXT'] = 'TEXT'
    is_scored: Literal[False] = False
    min_score: None = None
    max_score: None = None
    decimal_places: Literal[0] = 0
    config: TextQuestionConfigModel = Field(default_factory=TextQuestionConfigModel)
    options: list[QuestionOptionDraftModel] = Field(default_factory=list, max_length=0)


QuestionDraftModel = Annotated[
    SingleChoiceQuestionDraftModel
    | StarRatingQuestionDraftModel
    | NumericInputQuestionDraftModel
    | SliderQuestionDraftModel
    | TextQuestionDraftModel,
    Field(discriminator='question_type'),
]


def question_config_to_json(question: QuestionCommonDraftModel) -> dict[str, Any]:
    """把题型配置转换成可写入JSONB的camelCase JSON值。"""
    config = getattr(question, 'config', None)
    if config is None:
        return {}
    return config.model_dump(mode='json', by_alias=True, exclude_none=True)
