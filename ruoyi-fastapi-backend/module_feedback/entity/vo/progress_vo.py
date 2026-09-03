from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic运行时解析字段类型
from decimal import ROUND_HALF_UP, Decimal

from pydantic import Field, field_validator, model_validator

from module_feedback.entity.vo.project_vo import FeedbackVoModel
from module_feedback.enums import AssignmentStatus, ProjectStatus  # noqa: TC001 - Pydantic运行时解析枚举


class ProgressSummaryModel(FeedbackVoModel):
    total_count: int = Field(ge=0)
    submitted_count: int = Field(ge=0)
    draft_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    closed_incomplete_count: int = Field(ge=0)
    incomplete_count: int = Field(ge=0)
    completion_rate: str

    @classmethod
    def from_counts(cls, **counts: int) -> ProgressSummaryModel:
        normalized = {str(key).upper(): int(value) for key, value in counts.items()}
        submitted = normalized.get('SUBMITTED', 0)
        draft = normalized.get('DRAFT', 0)
        pending = normalized.get('PENDING', 0)
        closed = normalized.get('CLOSED_INCOMPLETE', 0)
        total = submitted + draft + pending + closed
        rate = Decimal('0') if total == 0 else Decimal(submitted * 100) / Decimal(total)
        return cls(
            totalCount=total,
            submittedCount=submitted,
            draftCount=draft,
            pendingCount=pending,
            closedIncompleteCount=closed,
            incompleteCount=draft + pending + closed,
            completionRate=str(rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        )


class ExpectedProgressSummaryModel(FeedbackVoModel):
    total_count: int = Field(ge=0, strict=True)
    submitted_count: int = Field(ge=0, strict=True)
    draft_count: int = Field(ge=0, strict=True)
    pending_count: int = Field(ge=0, strict=True)
    closed_incomplete_count: int = Field(ge=0, strict=True)

    @model_validator(mode='after')
    def validate_identity(self) -> ExpectedProgressSummaryModel:
        if (
            self.total_count
            != self.submitted_count + self.draft_count + self.pending_count + self.closed_incomplete_count
        ):
            raise ValueError('任务总数与状态计数不一致')
        return self


class ProgressQueryModel(FeedbackVoModel):
    page_num: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    evaluator_user_id: int | None = Field(default=None, ge=1)
    target_user_id: int | None = Field(default=None, ge=1)
    relation_id: int | None = Field(default=None, ge=1)
    status: AssignmentStatus | None = None
    evaluator_keyword: str | None = Field(default=None, max_length=100)
    target_keyword: str | None = Field(default=None, max_length=100)

    @field_validator('page_num', 'page_size', 'evaluator_user_id', 'target_user_id', 'relation_id', mode='before')
    @classmethod
    def validate_integer_query_value(cls, value: object) -> object:
        if value is None or (isinstance(value, int) and not isinstance(value, bool)):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.isascii() and normalized.isdigit():
                return int(normalized)
        raise ValueError('必须为整数')

    @field_validator('evaluator_keyword', 'target_keyword')
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ProgressRelationOptionModel(FeedbackVoModel):
    relation_id: int
    relation_code: str
    relation_name: str
    sort_order: int


class ProgressFilterOptionsModel(FeedbackVoModel):
    relations: list[ProgressRelationOptionModel]


class ProgressRowModel(FeedbackVoModel):
    assignment_id: int
    evaluator_user_id: int
    evaluator_name: str
    evaluator_dept_name: str | None = None
    target_user_id: int
    target_name: str
    target_dept_id: int | None = None
    target_dept_name: str | None = None
    relation_id: int
    relation_code: str
    relation_name: str
    status: AssignmentStatus
    saved_time: datetime | None = None
    submitted_time: datetime | None = None
    closed_time: datetime | None = None


class ProgressPageModel(FeedbackVoModel):
    project_id: int
    project_name: str
    project_status: ProjectStatus
    project_lock_version: int
    data_scope_complete: bool
    scope_message: str | None
    summary: ProgressSummaryModel
    filter_options: ProgressFilterOptionsModel
    rows: list[ProgressRowModel]
    total: int
    page_num: int
    page_size: int


class MissingRelationModel(FeedbackVoModel):
    target_user_id: int
    target_name: str
    relation_id: int
    relation_name: str
    assignment_count: int
    submitted_count: int


class CompletionPrecheckModel(FeedbackVoModel):
    project_id: int
    project_name: str
    project_status: ProjectStatus
    project_lock_version: int
    data_scope_complete: bool
    can_complete: bool
    completed_by: int | None = None
    completed_time: datetime | None = None
    completion_reason: str | None = None
    already_completed: bool = False
    summary: ProgressSummaryModel
    missing_relations: list[MissingRelationModel]
    impact_messages: list[str]
    prechecked_at: datetime


class ProjectCompleteRequestModel(FeedbackVoModel):
    project_lock_version: int = Field(ge=0, strict=True)
    completion_reason: str = Field(min_length=1, max_length=500)
    expected_summary: ExpectedProgressSummaryModel

    @field_validator('completion_reason', mode='before')
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError('完成原因不能为空')
        return normalized


class ProjectCompleteResultModel(FeedbackVoModel):
    project_id: int
    project_status: ProjectStatus
    project_lock_version: int
    completed_by: int
    completed_time: datetime
    completion_reason: str
    already_completed: bool
    summary: ProgressSummaryModel
