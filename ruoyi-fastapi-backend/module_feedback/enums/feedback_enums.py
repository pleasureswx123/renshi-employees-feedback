from enum import Enum


class FeedbackEnum(str, Enum):
    """可直接持久化为字符串的评价业务枚举基类。"""

    def __str__(self) -> str:
        return self.value


class ProjectStatus(FeedbackEnum):
    """评价项目状态。"""

    PREPARING = 'PREPARING'
    ACTIVE = 'ACTIVE'
    COMPLETED = 'COMPLETED'


class QuestionnaireVersionStatus(FeedbackEnum):
    """问卷版本状态。"""

    DRAFT = 'DRAFT'
    FROZEN = 'FROZEN'


class AssignmentStatus(FeedbackEnum):
    """评价任务状态。"""

    PENDING = 'PENDING'
    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'
    CLOSED_INCOMPLETE = 'CLOSED_INCOMPLETE'


class QuestionType(FeedbackEnum):
    """首期支持的题型。"""

    SINGLE_CHOICE = 'SINGLE_CHOICE'
    STAR_RATING = 'STAR_RATING'
    NUMERIC_INPUT = 'NUMERIC_INPUT'
    SLIDER = 'SLIDER'
    TEXT = 'TEXT'


class AnswerValueType(FeedbackEnum):
    """答案值使用的持久化通道。"""

    OPTION = 'OPTION'
    NUMERIC = 'NUMERIC'
    TEXT = 'TEXT'


class AnswerSheetStatus(FeedbackEnum):
    """已建立答卷的状态。"""

    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'


class RelationType(FeedbackEnum):
    """评价关系类型。"""

    SUPERVISOR = 'SUPERVISOR'
    PEER = 'PEER'
    SUBORDINATE = 'SUBORDINATE'
    SELF = 'SELF'
    OTHER = 'OTHER'
    CUSTOM = 'CUSTOM'


class ScoreResultType(FeedbackEnum):
    """计分结果粒度。"""

    INDICATOR_RELATION = 'INDICATOR_RELATION'
    INDICATOR_COMPOSITE = 'INDICATOR_COMPOSITE'
    PERSON_TOTAL = 'PERSON_TOTAL'
    COVERAGE = 'COVERAGE'
