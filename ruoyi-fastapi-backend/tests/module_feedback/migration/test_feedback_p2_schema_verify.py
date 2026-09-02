import pytest

from scripts.feedback_p2_schema_verify import (
    EXPECTED_TABLES,
    IMMUTABLE_TABLES,
    NUMERIC_12_4_COLUMNS,
    REQUIRED_CONSTRAINTS,
    REQUIRED_INDEXES,
    validate_database_name,
)

EXPECTED_P2_TABLE_COUNT = 13


def test_schema_verifier_covers_all_p2_tables_and_key_gates() -> None:
    assert len(EXPECTED_TABLES) == EXPECTED_P2_TABLE_COUNT
    assert {'fb_assignment', 'fb_answer', 'fb_score_result'} <= EXPECTED_TABLES
    assert {'fb_answer_sheet', 'fb_answer', 'fb_score_result'} == IMMUTABLE_TABLES
    assert ('fb_score_result', 'score') in NUMERIC_12_4_COLUMNS
    assert 'uq_fb_assignment_business_key' in REQUIRED_CONSTRAINTS
    assert 'uq_fb_answer_sheet_question' in REQUIRED_CONSTRAINTS
    assert 'ix_fb_assignment_evaluator_status' in REQUIRED_INDEXES


def test_migration_cycle_is_restricted_to_feedback_test_database() -> None:
    assert validate_database_name('ruoyi_feedback_test', cycle=True) == 'ruoyi_feedback_test'
    assert validate_database_name('ruoyi_feedback_dev', cycle=False) == 'ruoyi_feedback_dev'
    with pytest.raises(ValueError, match='只允许在_test'):
        validate_database_name('ruoyi_feedback_dev', cycle=True)
    with pytest.raises(ValueError, match='只允许验证'):
        validate_database_name('postgres', cycle=False)
