import pytest

from scripts.feedback_p2_schema_verify import (
    DESIGNER_COLUMNS,
    DESIGNER_REVISION,
    DOMAIN_REVISION,
    EXPECTED_TABLES,
    IMMUTABLE_TABLES,
    NUMERIC_12_4_COLUMNS,
    PUBLICATION_COLUMNS,
    PUBLICATION_REVISION,
    REQUIRED_CONSTRAINTS,
    REQUIRED_INDEXES,
    validate_database_name,
)

EXPECTED_FEEDBACK_TABLE_COUNT = 15
EXPECTED_PUBLICATION_COLUMN_COUNT = 12


def test_schema_verifier_covers_all_feedback_tables_and_key_gates() -> None:
    assert len(EXPECTED_TABLES) == EXPECTED_FEEDBACK_TABLE_COUNT
    assert {
        'fb_evaluator_selection',
        'fb_assignment',
        'fb_answer',
        'fb_score_result',
        'fb_project_completion_audit',
    } <= EXPECTED_TABLES
    assert {'fb_answer_sheet', 'fb_answer', 'fb_score_result', 'fb_project_completion_audit'} == IMMUTABLE_TABLES
    assert ('fb_score_result', 'score') in NUMERIC_12_4_COLUMNS
    assert 'uq_fb_assignment_business_key' in REQUIRED_CONSTRAINTS
    assert 'uq_fb_evaluator_selection_business_key' in REQUIRED_CONSTRAINTS
    assert 'uq_fb_answer_sheet_question' in REQUIRED_CONSTRAINTS
    assert 'uq_fb_questionnaire_page_version_code' in REQUIRED_CONSTRAINTS
    assert 'ck_fb_project_completion_audit_summary_identity' in REQUIRED_CONSTRAINTS
    assert 'ix_fb_assignment_evaluator_status' in REQUIRED_INDEXES
    assert 'ix_fb_evaluator_selection_project_version' in REQUIRED_INDEXES
    assert 'ix_fb_evaluator_selection_evaluator_project' in REQUIRED_INDEXES
    assert 'uq_fb_project_completion_audit_success' in REQUIRED_INDEXES
    assert PUBLICATION_REVISION == '20260902_04_feedback_publication'
    assert DESIGNER_REVISION == '20260902_03_feedback_designer'
    assert DOMAIN_REVISION == '20260902_02_feedback_domain'
    assert {
        ('fb_questionnaire_version', 'description_doc'),
        ('fb_questionnaire_page', 'page_code'),
    } == DESIGNER_COLUMNS
    assert len(PUBLICATION_COLUMNS) == EXPECTED_PUBLICATION_COLUMN_COUNT
    assert ('fb_evaluator_selection', 'evaluator_user_id') in PUBLICATION_COLUMNS


def test_migration_cycle_is_restricted_to_feedback_test_database() -> None:
    assert validate_database_name('ruoyi_feedback_test', cycle=True) == 'ruoyi_feedback_test'
    assert validate_database_name('ruoyi_feedback_dev', cycle=False) == 'ruoyi_feedback_dev'
    with pytest.raises(ValueError, match='只允许在_test'):
        validate_database_name('ruoyi_feedback_dev', cycle=True)
    with pytest.raises(ValueError, match='只允许验证'):
        validate_database_name('postgres', cycle=False)
