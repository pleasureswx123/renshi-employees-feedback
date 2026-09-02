from decimal import Decimal
from typing import NamedTuple

from module_feedback.enums import RelationType


class DefaultRelationDefinition(NamedTuple):
    """项目草稿固定评价关系定义。"""

    code: str
    relation_type: RelationType
    name: str
    is_enabled: bool
    participates_in_score: bool
    weight: Decimal
    sort_order: int


SELF_RELATION_CODE = 'REL_SELF'

DEFAULT_RELATION_DEFINITIONS = (
    DefaultRelationDefinition(
        'REL_SUPERVISOR',
        RelationType.SUPERVISOR,
        '上级',
        False,
        False,
        Decimal('0.0000'),
        1,
    ),
    DefaultRelationDefinition(
        'REL_PEER',
        RelationType.PEER,
        '同级',
        False,
        False,
        Decimal('0.0000'),
        2,
    ),
    DefaultRelationDefinition(
        'REL_SUBORDINATE',
        RelationType.SUBORDINATE,
        '下级',
        False,
        False,
        Decimal('0.0000'),
        3,
    ),
    DefaultRelationDefinition(
        SELF_RELATION_CODE,
        RelationType.SELF,
        '自己',
        True,
        False,
        Decimal('0.0000'),
        4,
    ),
    DefaultRelationDefinition(
        'REL_OTHER',
        RelationType.OTHER,
        '其他',
        False,
        False,
        Decimal('0.0000'),
        5,
    ),
)

FIXED_RELATION_CODES = frozenset(item.code for item in DEFAULT_RELATION_DEFINITIONS)
