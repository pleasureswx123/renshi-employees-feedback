from datetime import datetime
from typing import Literal

from pydantic import Field

from module_feedback.entity.vo.employee_vo import AnswerValueModel, EmployeeQuestionnaireModel
from module_feedback.entity.vo.questionnaire_question_vo import QuestionnaireVoModel


class ReportQueryModel(QuestionnaireVoModel):
    page_num: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str = Field(default='', max_length=200)
    department: str | None = Field(default=None, max_length=200)
    sort_relation_id: int | None = Field(default=None, gt=0)
    sort_order: Literal['asc', 'desc'] = 'desc'


class SubmittedAnswerQueryModel(ReportQueryModel):
    target_user_id: int | None = Field(default=None, gt=0)


class ReportProjectModel(QuestionnaireVoModel):
    project_id: int
    project_name: str
    completed_time: datetime


class RelationCoverageModel(QuestionnaireVoModel):
    relation_id: int
    relation_name: str
    relation_type: str
    status: Literal['NOT_APPLICABLE', 'MISSING', 'PARTIAL', 'COMPLETE']
    expected_count: int
    submitted_count: int


class RelationScoreModel(RelationCoverageModel):
    score: str | None
    original_weight: str
    effective_weight: str
    missing_answer_count: int


class ReportIndicatorModel(QuestionnaireVoModel):
    indicator_id: int
    indicator_name: str
    weight: str
    score: str | None
    self_score: str | None
    other_score: str | None
    relations: list[RelationScoreModel]


class ReportQuestionModel(QuestionnaireVoModel):
    question_id: int
    title: str
    question_type: str
    is_scored: bool
    max_score: str | None
    relation_id: int
    relation_name: str
    submitted_count: int
    answered_count: int
    missing_answer_count: int
    raw_average: str | None
    score: str | None


class ReportRowModel(QuestionnaireVoModel):
    target_user_id: int
    target_name: str
    target_dept_name: str | None
    rank: int | None = None
    only_self_evaluation: bool
    score: str | None
    self_score: str | None
    other_score: str | None
    expected_count: int
    submitted_count: int
    completion_rate: str
    has_missing_data: bool
    insufficient_data: bool
    relations: list[RelationCoverageModel]
    relation_scores: dict[int, str | None] = Field(default_factory=dict)
    indicators: list[ReportIndicatorModel]


class PersonalReportModel(ReportRowModel):
    project_id: int
    project_name: str
    version_id: int
    calculation_version: str
    calculated_time: datetime
    questions: list[ReportQuestionModel]


class TeamReportModel(QuestionnaireVoModel):
    department_options: list[str] = Field(default_factory=list)
    indicator_options: list[dict] = Field(default_factory=list)
    relation_options: list[dict] = Field(default_factory=list)
    project_id: int
    project_name: str
    version_id: int
    ready: bool
    data_scope_complete: bool
    scope_message: str | None
    target_count: int
    expected_count: int
    submitted_count: int
    completion_rate: str
    rows: list[ReportRowModel]
    total: int
    page_num: int
    page_size: int


class ReportCalculationModel(QuestionnaireVoModel):
    project_id: int
    calculated_count: int
    existing_count: int
    data_scope_complete: bool


class SubmittedAnswerRowModel(QuestionnaireVoModel):
    raw_total_score: str | None = None
    assignment_id: int
    target_user_id: int
    target_name: str
    target_dept_name: str | None
    evaluator_name: str
    evaluator_dept_name: str | None
    relation_name: str
    submitted_time: datetime


class SubmittedAnswerDetailModel(SubmittedAnswerRowModel):
    project_id: int
    project_name: str
    questionnaire: EmployeeQuestionnaireModel
    answers: list[AnswerValueModel]
    editable: Literal[False] = False


class ScoreSourceRowModel(QuestionnaireVoModel):
    key: str
    parent_key: str | None = None
    earned_formula: str | None = None
    maximum_formula: str | None = None
    raw_score: str | None = None
    max_score: str | None = None
    level: str
    label: str
    formula: str
    result: str | None = None
    exact_result: str | None = None
    note: str = ''
    indicator_id: int | None = None
    relation_id: int | None = None


class ScoreSourceModel(QuestionnaireVoModel):
    target_name: str
    calculation_version: str
    calculated_time: datetime
    rows: list[ScoreSourceRowModel]


class AnswerProjectQueryModel(ReportQueryModel):
    project_id: int | None = Field(default=None, gt=0)


class AnswerProjectModel(QuestionnaireVoModel):
    project_id: int
    project_name: str
    status: str
