from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from module_feedback.enums import ProjectStatus


class FeedbackVoModel(BaseModel):
    """评价业务接口模型公共配置。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra='forbid',
    )


class ProjectCreateModel(FeedbackVoModel):
    """创建准备阶段评价项目。"""

    template_key: str | None = Field(
        default=None, max_length=100, description='系统问卷模板版本标识；为空时创建空白问卷'
    )
    source_project_id: int | None = Field(default=None, ge=1, description='复制问卷的历史项目ID')

    @model_validator(mode='after')
    def validate_source(self):
        if self.source_project_id and self.template_key:
            raise ValueError('历史项目与系统模板不能同时选择')
        return self

    project_name: str = Field(min_length=1, max_length=200, description='评价项目名称')
    description: str | None = Field(default=None, max_length=5000, description='评价项目说明')
    questionnaire_title: str | None = Field(default=None, max_length=200, description='初始问卷标题')
    questionnaire_description: str | None = Field(default=None, max_length=5000, description='初始问卷说明')

    @field_validator('project_name')
    @classmethod
    def normalize_project_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('项目名称不能为空')
        return normalized

    @field_validator('questionnaire_title')
    @classmethod
    def normalize_questionnaire_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator('description', 'questionnaire_description')
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ProjectUpdateModel(FeedbackVoModel):
    """编辑准备阶段评价项目。"""

    project_name: str = Field(min_length=1, max_length=200, description='评价项目名称')
    description: str | None = Field(default=None, max_length=5000, description='评价项目说明')
    lock_version: int = Field(ge=0, description='项目乐观锁版本')

    @field_validator('project_name')
    @classmethod
    def normalize_project_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('项目名称不能为空')
        return normalized

    @field_validator('description')
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ProjectPageQueryModel(FeedbackVoModel):
    """评价项目分页查询条件。"""

    project_name: str | None = Field(default=None, max_length=200, description='项目名称模糊查询')
    status: ProjectStatus | None = Field(default=None, description='项目状态')
    page_num: int = Field(default=1, ge=1, description='当前页码')
    page_size: int = Field(default=10, ge=1, le=100, description='每页记录数')

    @field_validator('project_name')
    @classmethod
    def normalize_project_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ProjectSummaryModel(FeedbackVoModel):
    """评价项目列表行。"""

    project_id: int = Field(description='评价项目ID')
    project_name: str = Field(description='评价项目名称')
    description: str | None = Field(default=None, description='评价项目说明')
    status: ProjectStatus = Field(description='项目状态')
    owner_user_id: int = Field(description='项目负责人用户ID')
    owner_dept_id: int | None = Field(default=None, description='项目归属部门ID')
    draft_version_id: int | None = Field(default=None, description='当前草稿问卷版本ID')
    lock_version: int = Field(description='项目乐观锁版本')
    create_by: str = Field(description='创建者')
    create_time: datetime = Field(description='创建时间')
    update_by: str = Field(description='更新者')
    update_time: datetime = Field(description='更新时间')


class ProjectDetailModel(ProjectSummaryModel):
    """评价项目详情。"""

    current_questionnaire_version_id: int | None = Field(default=None, description='当前已发布问卷版本ID')
    published_by: int | None = Field(default=None, description='发布人用户ID')
    published_time: datetime | None = Field(default=None, description='发布时间')
    completed_by: int | None = Field(default=None, description='完成人用户ID')
    completed_time: datetime | None = Field(default=None, description='完成时间')
    completion_reason: str | None = Field(default=None, description='完成原因')
