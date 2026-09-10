from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_serializer, field_validator, model_validator

from module_feedback.constants import DEFAULT_RELATION_DEFINITIONS, FIXED_RELATION_CODES, SELF_RELATION_CODE
from module_feedback.entity.vo.questionnaire_question_vo import QuestionnaireVoModel
from module_feedback.entity.vo.questionnaire_vo import QuestionnaireDraftSaveModel, ValidationIssueModel
from module_feedback.enums import ProjectStatus, QuestionnaireVersionStatus, RelationType


class ParticipantOptionQueryModel(QuestionnaireVoModel):
    """项目内候选人员分页查询。"""

    page_num: int = Field(default=1, ge=1, description='当前页码')
    page_size: int = Field(default=20, ge=1, le=100, description='每页记录数')
    keyword: str | None = Field(default=None, max_length=100, description='账号或姓名关键词')
    dept_id: int | None = Field(default=None, ge=1, description='部门ID')
    unassigned: bool = Field(default=False, description='仅查询未分配部门的人员')

    @field_validator('keyword')
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ParticipantOptionModel(QuestionnaireVoModel):
    """P5页面需要的最小人员信息。"""

    user_id: int = Field(description='用户ID')
    user_name: str | None = Field(default=None, description='用户账号')
    nick_name: str = Field(description='用户姓名')
    dept_id: int | None = Field(default=None, description='部门ID')
    dept_name: str | None = Field(default=None, description='部门名称')
    available: bool = Field(default=True, description='人员当前是否可用')


class PublicationTargetSaveModel(QuestionnaireVoModel):
    """保存被评价人选择。"""

    target_user_id: int = Field(ge=1, description='被评价人用户ID')


class PublicationTargetModel(ParticipantOptionModel):
    """发布配置中的被评价人及展示快照。"""

    target_id: int = Field(description='被评价人配置ID')
    only_self_evaluation: bool = Field(description='是否仅有自评任务')


class PublicationRelationSaveModel(QuestionnaireVoModel):
    """项目内评价关系保存协议。"""

    relation_code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    relation_type: RelationType = Field(description='评价关系类型')
    relation_name: str = Field(min_length=1, max_length=100, description='评价关系名称')
    is_enabled: bool = Field(description='是否启用')
    participates_in_score: bool = Field(description='是否参与综合计分')
    weight: Decimal = Field(ge=0, le=100, max_digits=12, decimal_places=4, description='关系权重')
    sort_order: int = Field(ge=1, description='关系顺序')

    @field_validator('relation_name')
    @classmethod
    def normalize_relation_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('评价关系名称不能为空')
        return normalized

    @field_serializer('weight')
    def serialize_weight(self, value: Decimal) -> str:
        return f'{value:.4f}'

    @model_validator(mode='after')
    def validate_weight_semantics(self) -> 'PublicationRelationSaveModel':
        if not self.is_enabled and (self.participates_in_score or self.weight != 0):
            raise ValueError('禁用关系不能参与计分且权重必须为0.0000')
        if not self.participates_in_score and self.weight != 0:
            raise ValueError('不参与计分的关系权重必须为0.0000')
        if self.participates_in_score and self.weight <= 0:
            raise ValueError('参与计分的关系权重必须大于0')
        return self


class PublicationRelationModel(PublicationRelationSaveModel):
    """评价关系读取协议。"""

    relation_id: int = Field(description='评价关系ID')
    fixed: bool = Field(description='是否为固定关系')


class EvaluatorSelectionSaveModel(QuestionnaireVoModel):
    """按被评价人和非自评关系保存评价人集合。"""

    target_user_id: int = Field(ge=1, description='被评价人用户ID')
    relation_code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    evaluator_user_ids: list[int] = Field(min_length=1, max_length=1000, description='评价人用户ID集合')

    @field_validator('evaluator_user_ids')
    @classmethod
    def validate_evaluator_ids(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError('评价人用户ID必须为正整数')
        if len(values) != len(set(values)):
            raise ValueError('同一关系下不能重复选择评价人')
        return values


class EvaluatorSelectionModel(QuestionnaireVoModel):
    """后端保存并按关系聚合的评价人选择。"""

    target_user_id: int = Field(description='被评价人用户ID')
    relation_code: str = Field(description='评价关系稳定标识')
    evaluator_user_ids: list[int] = Field(description='评价人用户ID集合')
    system_managed: bool = Field(default=False, description='是否由后端维护')


class PublicationTargetPreviewModel(QuestionnaireVoModel):
    """单个被评价人的任务预览。"""

    target_user_id: int = Field(description='被评价人用户ID')
    self_count: int = Field(ge=0, description='自评任务数')
    non_self_count: int = Field(ge=0, description='他评任务数')
    assignment_count: int = Field(ge=0, description='任务总数')


class PublicationPreviewModel(QuestionnaireVoModel):
    """服务端权威任务预览。"""

    target_count: int = Field(ge=0, description='被评价人数')
    assignment_count: int = Field(ge=0, description='任务总数')
    evaluator_count: int = Field(ge=0, description='去重评价人数')
    target_summaries: list[PublicationTargetPreviewModel] = Field(default_factory=list)


class PublicationConfigSaveModel(QuestionnaireVoModel):
    """整体替换发布配置请求。"""

    project_lock_version: int = Field(ge=0, description='项目乐观锁版本')
    version_id: int = Field(ge=1, description='问卷版本ID')
    version_lock_version: int = Field(ge=0, description='问卷版本乐观锁')
    targets: list[PublicationTargetSaveModel] = Field(default_factory=list, max_length=1000)
    relations: list[PublicationRelationSaveModel] = Field(min_length=5, max_length=100)
    evaluator_selections: list[EvaluatorSelectionSaveModel] = Field(default_factory=list, max_length=10000)

    def _validate_relation_structure(self) -> dict[str, PublicationRelationSaveModel]:
        relation_codes = [item.relation_code for item in self.relations]
        relation_names = [item.relation_name for item in self.relations]
        relation_sorts = [item.sort_order for item in self.relations]
        if len(relation_codes) != len(set(relation_codes)):
            raise ValueError('评价关系标识不能重复')
        if len(relation_names) != len(set(relation_names)):
            raise ValueError('评价关系名称不能重复')
        if len(relation_sorts) != len(set(relation_sorts)):
            raise ValueError('评价关系顺序不能重复')
        if sorted(relation_sorts) != list(range(1, len(self.relations) + 1)):
            raise ValueError('评价关系顺序必须从1开始连续排列')
        if not FIXED_RELATION_CODES.issubset(relation_codes):
            raise ValueError('固定评价关系缺失')

        defaults_by_code = {item.code: item for item in DEFAULT_RELATION_DEFINITIONS}
        relations_by_code = {item.relation_code: item for item in self.relations}
        for code, default in defaults_by_code.items():
            relation = relations_by_code[code]
            if relation.relation_type != default.relation_type:
                raise ValueError(f'固定关系{code}的类型不能修改')
        for relation in self.relations:
            if relation.relation_code not in FIXED_RELATION_CODES:
                if relation.relation_type != RelationType.CUSTOM:
                    raise ValueError('自定义关系必须使用CUSTOM类型')
                if not relation.relation_code.startswith('REL_'):
                    raise ValueError('自定义关系标识必须以REL_开头')
        self_relation = relations_by_code[SELF_RELATION_CODE]
        if not self_relation.is_enabled or self_relation.participates_in_score or self_relation.weight != Decimal('0'):
            raise ValueError('自己关系必须启用、不参与计分且权重为0.0000')
        return relations_by_code

    def _validate_selection_structure(
        self,
        target_id_set: set[int],
        relations_by_code: dict[str, PublicationRelationSaveModel],
    ) -> None:
        selection_keys: set[tuple[int, str]] = set()
        for selection in self.evaluator_selections:
            key = (selection.target_user_id, selection.relation_code)
            if key in selection_keys:
                raise ValueError('同一被评价人和关系只能出现一组评价人选择')
            selection_keys.add(key)
            if selection.target_user_id not in target_id_set:
                raise ValueError('评价人选择引用了未选中的被评价人')
            relation = relations_by_code.get(selection.relation_code)
            if relation is None:
                raise ValueError('评价人选择引用了不存在的关系')
            if relation.relation_code == SELF_RELATION_CODE:
                raise ValueError('自己关系由后端自动派生，客户端不能提交')
            if not relation.is_enabled:
                raise ValueError('禁用关系不能配置评价人')
            if selection.target_user_id in selection.evaluator_user_ids:
                raise ValueError('非自评关系不能把被评价人本人作为评价人')

    @model_validator(mode='after')
    def validate_aggregate_structure(self) -> 'PublicationConfigSaveModel':
        target_ids = [item.target_user_id for item in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError('被评价人不能重复')
        relations_by_code = self._validate_relation_structure()
        self._validate_selection_structure(set(target_ids), relations_by_code)
        return self


class FrozenPublicationDetailsModel(QuestionnaireVoModel):
    """发布后按原冻结版本读取的详情，不接受客户端写入。"""

    published_by: int = Field(description='发布人用户ID')
    published_by_name: str = Field(description='发布人当前账号，仅用于识别操作人')
    published_time: datetime = Field(description='发布时间')
    version_no: int = Field(description='发布时问卷版本号')
    questionnaire: QuestionnaireDraftSaveModel = Field(description='原冻结问卷、题目及指标')


class PublicationConfigModel(QuestionnaireVoModel):
    """准备期可编辑或发布后只读的聚合配置。"""

    project_id: int = Field(description='评价项目ID')
    project_name: str = Field(description='评价项目名称')
    project_status: ProjectStatus = Field(description='项目状态')
    project_lock_version: int = Field(description='项目乐观锁版本')
    version_id: int = Field(description='问卷版本ID')
    version_lock_version: int = Field(description='问卷版本乐观锁')
    version_status: QuestionnaireVersionStatus = Field(description='问卷版本状态')
    editable: bool = Field(description='配置是否可编辑')
    targets: list[PublicationTargetModel] = Field(default_factory=list)
    relations: list[PublicationRelationModel] = Field(default_factory=list)
    evaluator_selections: list[EvaluatorSelectionModel] = Field(default_factory=list)
    configured_participants: list[ParticipantOptionModel] = Field(default_factory=list)
    preview: PublicationPreviewModel
    is_publish_ready: bool = Field(description='是否满足发布条件')
    validation_issues: list[ValidationIssueModel] = Field(default_factory=list)
    frozen_details: FrozenPublicationDetailsModel | None = Field(default=None, description='仅已发布项目返回冻结详情')


class PublishRequestModel(QuestionnaireVoModel):
    """发布并发前置条件。"""

    project_lock_version: int = Field(ge=0, description='项目乐观锁版本')
    version_id: int = Field(ge=1, description='问卷版本ID')
    version_lock_version: int = Field(ge=0, description='问卷版本乐观锁')


class PublishResultModel(QuestionnaireVoModel):
    """项目发布结果。"""

    project_id: int
    project_status: ProjectStatus
    version_id: int
    version_status: QuestionnaireVersionStatus
    published_by: int
    published_time: datetime
    target_count: int
    assignment_count: int
    evaluator_count: int
    already_published: bool
