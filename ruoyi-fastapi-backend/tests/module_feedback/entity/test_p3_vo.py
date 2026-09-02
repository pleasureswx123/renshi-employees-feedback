from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import ValidationError

from module_feedback.entity.vo import QuestionnaireDraftSaveModel


def build_draft_payload() -> dict:
    return {
        'versionId': 10,
        'lockVersion': 0,
        'title': 'P3单选题问卷',
        'description': '验证草稿协议',
        'pages': [
            {
                'pageTitle': '第1页',
                'sortOrder': 1,
                'questions': [
                    {
                        'questionCode': 'Q_1',
                        'questionType': 'SINGLE_CHOICE',
                        'title': '请选择最符合的选项',
                        'isRequired': True,
                        'sortOrder': 1,
                        'options': [
                            {
                                'optionCode': 'O_A',
                                'optionLabel': '优秀',
                                'score': '5.0000',
                                'requiresReason': True,
                                'sortOrder': 1,
                            },
                            {
                                'optionCode': 'O_B',
                                'optionLabel': '良好',
                                'score': '4.0000',
                                'sortOrder': 2,
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_questionnaire_draft_contract_preserves_decimal_and_reason_rule() -> None:
    draft = QuestionnaireDraftSaveModel(**build_draft_payload())

    assert draft.pages[0].questions[0].question_type == 'SINGLE_CHOICE'
    assert draft.pages[0].questions[0].options[0].score == Decimal('5.0000')
    assert draft.pages[0].questions[0].options[0].requires_reason is True


@pytest.mark.parametrize(
    ('mutator', 'message'),
    [
        (
            lambda payload: payload['pages'][0]['questions'][0].update(questionType='TEXT'),
            'SINGLE_CHOICE',
        ),
        (
            lambda payload: payload['pages'][0]['questions'][0].update(options=[]),
            'at least 2 items',
        ),
        (
            lambda payload: payload['pages'][0]['questions'][0]['options'][1].update(sortOrder=1),
            '选项顺序不能重复',
        ),
        (
            lambda payload: payload['pages'][0]['questions'][0]['options'][1].update(optionCode='O_A'),
            '选项标识不能重复',
        ),
    ],
)
def test_questionnaire_draft_contract_rejects_invalid_single_choice(
    mutator: Callable[[dict], object],
    message: str,
) -> None:
    payload = build_draft_payload()
    mutator(payload)

    with pytest.raises(ValidationError) as exc_info:
        QuestionnaireDraftSaveModel(**payload)

    assert message in str(exc_info.value)
