from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from module_feedback.enums import ProjectStatus, QuestionnaireVersionStatus


class QuestionnaireVoModel(BaseModel):
    """问卷草稿接口模型公共配置。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra='forbid',
    )


class QuestionOptionDraftModel(QuestionnaireVoModel):
    """单选题选项草稿。"""

    option_id: int | None = Field(default=None, description='选项ID')
    option_code: str | None = Field(default=None, min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    option_label: str = Field(min_length=1, max_length=500, description='选项文本')
    score: Decimal = Field(default=Decimal('0'), ge=0, max_digits=12, decimal_places=4, description='选项分值')
    requires_reason: bool = Field(default=False, description='选择后是否必须填写原因')
    sort_order: int = Field(ge=1, description='选项顺序')

    @field_validator('option_label')
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('选项文本不能为空')
        return normalized


class QuestionDraftModel(QuestionnaireVoModel):
    """P3单选题草稿。"""

    question_id: int | None = Field(default=None, description='题目ID')
    question_code: str | None = Field(default=None, min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    question_type: Literal['SINGLE_CHOICE'] = Field(default='SINGLE_CHOICE', description='P3固定单选题')
    title: str = Field(min_length=1, max_length=2000, description='题目标题')
    description: str | None = Field(default=None, max_length=5000, description='题目说明')
    is_required: bool = Field(default=False, description='是否必答')
    is_scored: bool = Field(default=True, description='是否参与计分')
    sort_order: int = Field(ge=1, description='题目顺序')
    options: list[QuestionOptionDraftModel] = Field(min_length=2, max_length=100, description='单选题选项')

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

    @model_validator(mode='after')
    def validate_options(self) -> 'QuestionDraftModel':
        sort_orders = [item.sort_order for item in self.options]
        if len(sort_orders) != len(set(sort_orders)):
            raise ValueError('同一题目的选项顺序不能重复')
        codes = [item.option_code for item in self.options if item.option_code]
        if len(codes) != len(set(codes)):
            raise ValueError('同一题目的选项标识不能重复')
        return self


class QuestionnairePageDraftModel(QuestionnaireVoModel):
    """问卷页面草稿。"""

    page_id: int | None = Field(default=None, description='页面ID')
    page_title: str = Field(min_length=1, max_length=200, description='页面标题')
    page_description: str | None = Field(default=None, max_length=5000, description='页面说明')
    sort_order: int = Field(ge=1, description='页面顺序')
    questions: list[QuestionDraftModel] = Field(default_factory=list, max_length=200, description='页面题目')

    @field_validator('page_title')
    @classmethod
    def normalize_page_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('页面标题不能为空')
        return normalized

    @field_validator('page_description')
    @classmethod
    def normalize_page_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode='after')
    def validate_questions(self) -> 'QuestionnairePageDraftModel':
        sort_orders = [item.sort_order for item in self.questions]
        if len(sort_orders) != len(set(sort_orders)):
            raise ValueError('同一页面的题目顺序不能重复')
        return self


class QuestionnaireDraftSaveModel(QuestionnaireVoModel):
    """保存问卷草稿请求。"""

    version_id: int = Field(description='问卷草稿版本ID')
    lock_version: int = Field(ge=0, description='问卷乐观锁版本')
    title: str = Field(min_length=1, max_length=200, description='问卷标题')
    description: str | None = Field(default=None, max_length=5000, description='问卷说明')
    settings: dict[str, Any] = Field(default_factory=dict, description='问卷全局设置')
    pages: list[QuestionnairePageDraftModel] = Field(min_length=1, max_length=1, description='P3固定单页草稿')

    @field_validator('title')
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('问卷标题不能为空')
        return normalized

    @field_validator('description')
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode='after')
    def validate_document(self) -> 'QuestionnaireDraftSaveModel':
        question_codes = [
            question.question_code for page in self.pages for question in page.questions if question.question_code
        ]
        if len(question_codes) != len(set(question_codes)):
            raise ValueError('同一问卷版本的题目标识不能重复')
        return self


class QuestionnaireDraftModel(QuestionnaireDraftSaveModel):
    """问卷草稿详情响应。"""

    project_id: int = Field(description='评价项目ID')
    project_name: str = Field(description='评价项目名称')
    project_status: ProjectStatus = Field(description='项目状态')
    version_no: int = Field(description='项目内版本号')
    version_status: QuestionnaireVersionStatus = Field(description='问卷版本状态')
