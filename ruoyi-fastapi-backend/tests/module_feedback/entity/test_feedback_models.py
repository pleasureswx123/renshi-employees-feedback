import warnings

from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import configure_mappers

from config.database import Base
from module_admin.entity.do.dept_do import SysDept  # noqa: F401
from module_admin.entity.do.user_do import SysUser  # noqa: F401
from module_feedback.entity.do import (  # noqa: F401
    FbAnswer,
    FbAnswerSheet,
    FbAssignment,
    FbEvaluatorSelection,
    FbIndicator,
    FbIndicatorQuestion,
    FbProject,
    FbProjectTarget,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
    FbQuestionOption,
    FbRelation,
    FbScoreResult,
)

EXPECTED_TABLES = {
    'fb_project',
    'fb_questionnaire_version',
    'fb_questionnaire_page',
    'fb_question',
    'fb_question_option',
    'fb_indicator',
    'fb_indicator_question',
    'fb_relation',
    'fb_project_target',
    'fb_evaluator_selection',
    'fb_assignment',
    'fb_answer_sheet',
    'fb_answer',
    'fb_score_result',
}
EXPECTED_SELECTION_COLUMN_COUNT = 12


def test_all_p2_models_map_without_relationship_warnings() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter('error', SAWarning)
        configure_mappers()


def test_all_p2_tables_and_columns_have_chinese_comments() -> None:
    feedback_tables = {name: table for name, table in Base.metadata.tables.items() if name.startswith('fb_')}
    assert set(feedback_tables) == EXPECTED_TABLES
    for table in feedback_tables.values():
        assert table.comment
        assert all(column.comment for column in table.columns)


def test_formal_scores_and_weights_use_exact_numeric_with_wide_sheet_total() -> None:
    numeric_columns = {
        ('fb_question', 'min_score'),
        ('fb_question', 'max_score'),
        ('fb_question_option', 'score'),
        ('fb_indicator', 'weight'),
        ('fb_relation', 'weight'),
        ('fb_answer_sheet', 'raw_total_score'),
        ('fb_answer', 'numeric_value'),
        ('fb_answer', 'raw_score'),
        ('fb_score_result', 'score'),
        ('fb_score_result', 'original_weight'),
        ('fb_score_result', 'effective_weight'),
    }
    for table_name, column_name in numeric_columns:
        column_type = Base.metadata.tables[table_name].c[column_name].type
        assert isinstance(column_type, Numeric)
        expected_precision = 18 if (table_name, column_name) == ('fb_answer_sheet', 'raw_total_score') else 12
        assert (column_type.precision, column_type.scale) == (expected_precision, 4)


def test_immutable_submission_tables_do_not_define_soft_delete() -> None:
    for table_name in ('fb_answer_sheet', 'fb_answer', 'fb_score_result'):
        assert 'del_flag' not in Base.metadata.tables[table_name].c


def test_key_business_constraints_are_present_in_metadata() -> None:
    expected_constraints = {
        'fb_assignment': {'uq_fb_assignment_business_key', 'ck_fb_assignment_status'},
        'fb_evaluator_selection': {'uq_fb_evaluator_selection_business_key'},
        'fb_answer': {'uq_fb_answer_sheet_question', 'ck_fb_answer_value_channel'},
        'fb_questionnaire_page': {
            'uq_fb_questionnaire_page_version_sort',
            'uq_fb_questionnaire_page_version_code',
        },
        'fb_question': {'uq_fb_question_page_sort', 'ck_fb_question_score_range'},
        'fb_indicator': {'ck_fb_indicator_weight'},
        'fb_relation': {'ck_fb_relation_weight'},
    }
    for table_name, expected_names in expected_constraints.items():
        constraints = {
            constraint.name
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, (CheckConstraint, UniqueConstraint))
        }
        assert expected_names <= constraints


def test_project_detail_relationships_require_explicit_eager_loading() -> None:
    assert FbProject.questionnaire_versions.property.lazy == 'raise'
    assert FbProject.targets.property.lazy == 'raise'
    assert FbProjectTarget.evaluator_selections.property.lazy == 'raise'
    assert FbEvaluatorSelection.relation.property.lazy == 'raise'
    assert FbEvaluatorSelection.target_snapshot.property.lazy == 'raise'
    assert FbQuestionnaireVersion.pages.property.lazy == 'raise'
    assert FbQuestionnairePage.questions.property.lazy == 'raise'
    assert FbQuestion.options.property.lazy == 'raise'


def test_evaluator_selection_uses_aggregate_lock_and_cascade_references() -> None:
    table = Base.metadata.tables['fb_evaluator_selection']
    assert 'lock_version' not in table.c
    assert 'del_flag' not in table.c
    assert len(table.c) == EXPECTED_SELECTION_COLUMN_COUNT
    foreign_keys = {constraint.name: constraint.ondelete for constraint in table.foreign_key_constraints}
    assert foreign_keys['fk_fb_evaluator_selection_relation'] == 'CASCADE'
    assert foreign_keys['fk_fb_evaluator_selection_target'] == 'CASCADE'
    assert foreign_keys['fk_fb_evaluator_selection_project'] == 'RESTRICT'
