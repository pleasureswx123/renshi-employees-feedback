from decimal import Decimal

from module_feedback.constants import DEFAULT_RELATION_DEFINITIONS, FIXED_RELATION_CODES, SELF_RELATION_CODE
from module_feedback.enums import RelationType
from module_feedback.service import FeedbackProjectService

EXPECTED_RELATION_COUNT = 5
PROJECT_ID = 7
VERSION_ID = 11


def test_fixed_relation_definitions_do_not_embed_organization_weights() -> None:
    assert [item.code for item in DEFAULT_RELATION_DEFINITIONS] == [
        'REL_SUPERVISOR',
        'REL_PEER',
        'REL_SUBORDINATE',
        'REL_SELF',
        'REL_OTHER',
    ]
    assert {item.code for item in DEFAULT_RELATION_DEFINITIONS} == FIXED_RELATION_CODES
    assert [item.sort_order for item in DEFAULT_RELATION_DEFINITIONS] == [1, 2, 3, 4, 5]
    assert all(item.weight == Decimal('0.0000') for item in DEFAULT_RELATION_DEFINITIONS)

    self_relation = next(item for item in DEFAULT_RELATION_DEFINITIONS if item.code == SELF_RELATION_CODE)
    assert self_relation.relation_type == RelationType.SELF
    assert self_relation.is_enabled is True
    assert self_relation.participates_in_score is False
    assert all(
        item.is_enabled is False and item.participates_in_score is False
        for item in DEFAULT_RELATION_DEFINITIONS
        if item.code != SELF_RELATION_CODE
    )


def test_project_service_builds_fixed_relations_for_the_same_draft_version() -> None:
    relations = FeedbackProjectService._build_default_relations(PROJECT_ID, VERSION_ID, 'hr-user')

    assert len(relations) == EXPECTED_RELATION_COUNT
    assert {item.relation_code for item in relations} == FIXED_RELATION_CODES
    assert all(item.project_id == PROJECT_ID and item.version_id == VERSION_ID for item in relations)
    assert all(item.create_by == 'hr-user' and item.update_by == 'hr-user' for item in relations)
