from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from module_feedback.calculators.raw_score import calculate_raw_score
from module_feedback.entity.vo.employee_vo import AnswerDraftSaveModel, AnswerInputModel, AnswerSubmitModel
from module_feedback.validators.answer_validator import validate_answers


def frozen_version() -> SimpleNamespace:
    common = {
        'is_required': True,
        'is_scored': True,
        'min_score': Decimal('0'),
        'max_score': Decimal('10'),
        'options': [],
    }
    questions = [
        SimpleNamespace(
            **{**common, 'question_id': 1, 'question_type': 'SINGLE_CHOICE', 'decimal_places': 0},
            config={},
        ),
        SimpleNamespace(**common, question_id=2, question_type='STAR_RATING', decimal_places=0, config={}),
        SimpleNamespace(**common, question_id=3, question_type='NUMERIC_INPUT', decimal_places=2, config={}),
        SimpleNamespace(**common, question_id=4, question_type='SLIDER', decimal_places=1, config={'step': '0.5'}),
        SimpleNamespace(
            **{**common, 'is_scored': False},
            question_id=5,
            question_type='TEXT',
            decimal_places=0,
            config={'maxLength': 4},
        ),
    ]
    questions[0].options = [
        SimpleNamespace(option_id=11, score=Decimal('3.2500'), requires_reason=True),
        SimpleNamespace(option_id=12, score=Decimal('0'), requires_reason=False),
    ]
    return SimpleNamespace(pages=[SimpleNamespace(page_id=1, questions=questions)])


def payload(answers: list[dict], **kwargs) -> AnswerDraftSaveModel:
    return AnswerDraftSaveModel(versionId=1, lockVersion=0, lastPageId=kwargs.get('page_id', 1), answers=answers)


@pytest.mark.parametrize(
    ('answer', 'code'),
    [
        ({'questionId': 1, 'optionId': 99}, 'INVALID_OPTION'),
        ({'questionId': 1, 'optionId': 11}, 'REASON_REQUIRED'),
        ({'questionId': 1, 'optionId': 12, 'reason': '不接受'}, 'UNEXPECTED_REASON'),
        ({'questionId': 2, 'numericValue': '-1'}, 'OUT_OF_RANGE'),
        ({'questionId': 2, 'numericValue': '1.5'}, 'INVALID_PRECISION'),
        ({'questionId': 3, 'numericValue': '2.001'}, 'INVALID_PRECISION'),
        ({'questionId': 3, 'textValue': '2'}, 'INVALID_ANSWER_TYPE'),
        ({'questionId': 4, 'numericValue': '1.2'}, 'INVALID_STEP'),
        ({'questionId': 4, 'numericValue': '11'}, 'OUT_OF_RANGE'),
        ({'questionId': 5, 'textValue': '超过四个字'}, 'TEXT_TOO_LONG'),
        ({'questionId': 5, 'textValue': '   '}, 'REQUIRED'),
        ({'questionId': 5, 'optionId': 11}, 'INVALID_ANSWER_TYPE'),
        ({'questionId': 999, 'textValue': '未知'}, 'INVALID_QUESTION'),
    ],
)
def test_frozen_answer_validation_reports_locatable_issue(answer: dict, code: str) -> None:
    _, issues = validate_answers(frozen_version(), payload([answer]), submitting=True)
    issue = next(item for item in issues if item['code'] == code)
    assert issue['questionId'] == answer['questionId']
    assert issue['pageId'] == (None if code == 'INVALID_QUESTION' else 1)


def test_draft_allows_missing_answers_and_reason_but_not_invalid_references() -> None:
    version = frozen_version()
    _, issues = validate_answers(version, payload([{'questionId': 1, 'optionId': 11}]), submitting=False)
    assert issues == []
    _, issues = validate_answers(version, payload([], page_id=999), submitting=False)
    assert issues[0]['code'] == 'INVALID_PAGE'
    _, issues = validate_answers(
        version,
        payload([{'questionId': 2, 'numericValue': '2'}, {'questionId': 2, 'numericValue': '3'}]),
        submitting=False,
    )
    assert issues[0]['code'] == 'DUPLICATE_ANSWER'


def test_all_five_answers_zero_unicode_and_exact_raw_score() -> None:
    version = frozen_version()
    request = payload(
        [
            {'questionId': 1, 'optionId': 11, 'reason': ' 原因 '},
            {'questionId': 2, 'numericValue': '0'},
            {'questionId': 3, 'numericValue': '1.25'},
            {'questionId': 4, 'numericValue': '2.5'},
            {'questionId': 5, 'textValue': '汉😀字'},
        ]
    )
    answers, issues = validate_answers(version, request, submitting=True)
    assert not issues
    assert answers[0].reason == '原因'
    assert [
        calculate_raw_score(question, answer)
        for question, answer in zip(version.pages[0].questions, answers, strict=True)
    ] == [Decimal('3.25'), Decimal('0'), Decimal('1.25'), Decimal('2.5'), None]
    version.pages[0].questions[2].is_scored = False
    assert calculate_raw_score(version.pages[0].questions[2], answers[2]) is None


@pytest.mark.parametrize(
    'answer',
    [
        {'questionId': 1},
        {'questionId': 1, 'optionId': 1, 'numericValue': '1'},
        {'questionId': 1, 'numericValue': 0.1},
        {'questionId': 1, 'numericValue': 'NaN'},
        {'questionId': 1, 'numericValue': 'Infinity'},
        {'questionId': 1, 'numericValue': '1.00001'},
        {'questionId': 1, 'numericValue': '100000000'},
        {'questionId': True, 'textValue': '不接受布尔ID'},
        {'questionId': 1, 'textValue': '答案', 'rawScore': '999'},
        {'questionId': 1, 'optionId': 1, 'reason': '字' * 501},
    ],
)
def test_answer_protocol_rejects_ambiguous_and_untrusted_values(answer: dict) -> None:
    with pytest.raises(ValidationError):
        AnswerInputModel.model_validate(answer)


def test_submission_requires_uuid_and_forbids_identity_and_snapshot_injection() -> None:
    base = {'versionId': 1, 'lockVersion': 0, 'lastPageId': 1, 'answers': []}
    for extra in (
        {},
        {'submissionId': 'bad'},
        {'submissionId': '621e027c-016f-4603-b650-18020d826aa1', 'evaluatorUserId': 2},
    ):
        with pytest.raises(ValidationError):
            AnswerSubmitModel.model_validate({**base, **extra})
