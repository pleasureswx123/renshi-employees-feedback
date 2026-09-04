from typing import Any

from pydantic import Field, field_validator, model_validator

from module_feedback.entity.vo.indicator_vo import IndicatorDraftModel
from module_feedback.entity.vo.questionnaire_question_vo import QuestionDraftModel, QuestionnaireVoModel
from module_feedback.enums import ProjectStatus, QuestionnaireVersionStatus
from module_feedback.validators.questionnaire_validator import extract_rich_text, validate_draft_structure


class ValidationIssueModel(QuestionnaireVoModel):
    """后端权威的发布完整性问题。"""

    code: str = Field(description='稳定问题码')
    path: str = Field(description='草稿字段路径')
    message: str = Field(description='中文问题说明')


class QuestionnairePageDraftModel(QuestionnaireVoModel):
    """问卷页面草稿。"""

    page_id: int | None = Field(default=None, description='页面ID')
    page_code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    page_title: str = Field(min_length=1, max_length=200, description='页面标题')
    sort_order: int = Field(ge=1, description='页面顺序')
    questions: list[QuestionDraftModel] = Field(default_factory=list, max_length=200, description='页面题目')

    @field_validator('page_title')
    @classmethod
    def normalize_page_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('页面标题不能为空')
        return normalized


class QuestionnaireDraftSaveModel(QuestionnaireVoModel):
    """保存完整问卷草稿请求。"""

    version_id: int = Field(description='问卷草稿版本ID')
    lock_version: int = Field(ge=0, description='问卷乐观锁版本')
    title: str = Field(min_length=1, max_length=200, description='问卷标题')
    description: str | None = Field(default=None, max_length=5000, description='问卷纯文本说明')
    description_doc: dict[str, Any] | None = Field(default=None, description='问卷富文本说明文档')
    settings: dict[str, Any] = Field(default_factory=dict, description='问卷全局设置')
    pages: list[QuestionnairePageDraftModel] = Field(min_length=1, max_length=50, description='问卷页面')
    indicators: list[IndicatorDraftModel] = Field(default_factory=list, max_length=500, description='评价指标')

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
        if self.description_doc is not None:
            self.description = extract_rich_text(self.description_doc)
        validate_draft_structure(self)
        return self


class QuestionnaireDraftModel(QuestionnaireDraftSaveModel):
    """问卷草稿详情响应。"""

    project_id: int = Field(description='评价项目ID')
    project_name: str = Field(description='评价项目名称')
    project_status: ProjectStatus = Field(description='项目状态')
    version_no: int = Field(description='项目内版本号')
    version_status: QuestionnaireVersionStatus = Field(description='问卷版本状态')
    is_publish_ready: bool = Field(default=False, description='是否满足问卷和指标发布条件')
    validation_issues: list[ValidationIssueModel] = Field(default_factory=list, description='发布完整性问题')
