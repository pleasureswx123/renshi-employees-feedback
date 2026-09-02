from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from module_feedback.entity.vo.questionnaire_question_vo import QuestionnaireVoModel
from module_feedback.entity.vo.questionnaire_vo import QuestionnairePageDraftModel
from module_feedback.enums import AssignmentStatus, ProjectStatus


class EmployeePageQueryModel(QuestionnaireVoModel):
    """本人待办与历史分页条件，不允许传入评价人身份。"""

    page_num: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str = Field(default='', max_length=200)


class EmployeeProjectModel(QuestionnaireVoModel):
    """仅含当前评价人任务统计的项目摘要。"""

    project_id: int
    project_name: str
    project_status: ProjectStatus
    published_time: datetime | None
    total_count: int
    pending_count: int
    draft_count: int
    submitted_count: int
    closed_count: int


class EmployeeTaskModel(QuestionnaireVoModel):
    """当前评价人的单份任务。"""

    assignment_id: int
    project_id: int
    project_name: str
    project_status: ProjectStatus
    version_id: int
    target_user_id: int
    target_name: str
    target_dept_name: str | None
    relation_id: int
    relation_name: str
    status: AssignmentStatus
    saved_time: datetime | None
    submitted_time: datetime | None


class EmployeeProjectDetailModel(EmployeeProjectModel):
    """项目中本人的全部任务，包含已提交与关闭状态。"""

    tasks: list[EmployeeTaskModel]


class AnswerInputModel(QuestionnaireVoModel):
    """答案只接受一个值通道；不允许客户端提供分数或快照。"""

    question_id: int = Field(gt=0, strict=True)
    option_id: int | None = Field(default=None, gt=0, strict=True)
    numeric_value: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    text_value: str | None = Field(default=None, max_length=5000, strict=True)
    reason: str | None = Field(default=None, max_length=500, strict=True)

    @field_validator('numeric_value', mode='before')
    @classmethod
    def decimal_string_only(cls, value: Any) -> Any:
        if value is not None and not isinstance(value, (str, Decimal)):
            raise ValueError('数值答案必须使用十进制字符串')
        return value

    @model_validator(mode='after')
    def single_value_channel(self) -> 'AnswerInputModel':
        if sum(value is not None for value in (self.option_id, self.numeric_value, self.text_value)) != 1:
            raise ValueError('每题必须且只能提供一个答案值')
        return self


class AnswerDraftSaveModel(QuestionnaireVoModel):
    """整份暂存协议；未出现在列表中的题目视为清空。"""

    version_id: int = Field(gt=0, strict=True)
    lock_version: int = Field(ge=0, strict=True)
    last_page_id: int = Field(gt=0, strict=True)
    answers: list[AnswerInputModel] = Field(default_factory=list, max_length=10000)


class AnswerSubmitModel(AnswerDraftSaveModel):
    """正式提交使用任务内幂等标识。"""

    submission_id: UUID


class AnswerValueModel(QuestionnaireVoModel):
    """本人答案展示值，不包含其他评价人的内容。"""

    question_id: int
    option_id: int | None = None
    numeric_value: Decimal | None = None
    text_value: str | None = None
    reason: str | None = None


class EmployeeQuestionnaireModel(QuestionnaireVoModel):
    """冻结问卷作答视图，不提供编辑或全项目人员配置。"""

    version_id: int
    title: str
    description: str | None
    description_doc: dict[str, Any] | None
    pages: list[QuestionnairePageDraftModel]


class EmployeeAnswerDetailModel(QuestionnaireVoModel):
    """任务、冻结问卷和本人答卷的聚合详情。"""

    task: EmployeeTaskModel
    questionnaire: EmployeeQuestionnaireModel
    sheet_id: int | None = None
    lock_version: int = 0
    last_page_id: int
    answered_count: int = 0
    answers: list[AnswerValueModel] = Field(default_factory=list)
    editable: bool
    already_submitted: bool = False
