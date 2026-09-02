from module_feedback.enums import (
    AnswerSheetStatus,
    AnswerValueType,
    AssignmentStatus,
    ProjectStatus,
    QuestionnaireVersionStatus,
    QuestionType,
    RelationType,
    ScoreResultType,
)


def test_p2_enum_values_match_persistence_contract() -> None:
    assert {item.value for item in ProjectStatus} == {'PREPARING', 'ACTIVE', 'COMPLETED'}
    assert {item.value for item in QuestionnaireVersionStatus} == {'DRAFT', 'FROZEN'}
    assert {item.value for item in AssignmentStatus} == {
        'PENDING',
        'DRAFT',
        'SUBMITTED',
        'CLOSED_INCOMPLETE',
    }
    assert {item.value for item in QuestionType} == {
        'SINGLE_CHOICE',
        'STAR_RATING',
        'NUMERIC_INPUT',
        'SLIDER',
        'TEXT',
    }
    assert {item.value for item in AnswerValueType} == {'OPTION', 'NUMERIC', 'TEXT'}
    assert {item.value for item in AnswerSheetStatus} == {'DRAFT', 'SUBMITTED'}
    assert {item.value for item in RelationType} == {
        'SUPERVISOR',
        'PEER',
        'SUBORDINATE',
        'SELF',
        'OTHER',
        'CUSTOM',
    }
    assert {item.value for item in ScoreResultType} == {
        'INDICATOR_RELATION',
        'INDICATOR_COMPOSITE',
        'PERSON_TOTAL',
        'COVERAGE',
    }


def test_feedback_enums_are_string_compatible() -> None:
    assert ProjectStatus(ProjectStatus.PREPARING.value) is ProjectStatus.PREPARING
    assert str(AssignmentStatus.CLOSED_INCOMPLETE) == 'CLOSED_INCOMPLETE'
