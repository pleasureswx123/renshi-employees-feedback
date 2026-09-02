from collections.abc import Callable
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from module_feedback.constants import DEFAULT_RELATION_DEFINITIONS
from module_feedback.entity.vo import PublicationConfigSaveModel
from module_feedback.validators import get_publication_validation_issues

TARGET_USER_ID = 10


def relation_payloads() -> list[dict[str, object]]:
    return [
        {
            'relationCode': item.code,
            'relationType': item.relation_type.value,
            'relationName': item.name,
            'isEnabled': item.is_enabled,
            'participatesInScore': item.participates_in_score,
            'weight': str(item.weight),
            'sortOrder': item.sort_order,
        }
        for item in DEFAULT_RELATION_DEFINITIONS
    ]


def valid_config_payload() -> dict[str, object]:
    relations = relation_payloads()
    relations[0].update({'isEnabled': True, 'participatesInScore': True, 'weight': '100.0000'})
    return {
        'projectLockVersion': 1,
        'versionId': 2,
        'versionLockVersion': 3,
        'targets': [{'targetUserId': 10}],
        'relations': relations,
        'evaluatorSelections': [{'targetUserId': 10, 'relationCode': 'REL_SUPERVISOR', 'evaluatorUserIds': [11]}],
    }


def test_publication_config_accepts_fixed_relations_and_non_self_selection() -> None:
    model = PublicationConfigSaveModel.model_validate(valid_config_payload())

    assert model.targets[0].target_user_id == TARGET_USER_ID
    assert model.relations[0].weight == Decimal('100.0000')
    assert model.model_dump(by_alias=True)['relations'][0]['weight'] == '100.0000'


@pytest.mark.parametrize(
    ('mutate', 'message'),
    [
        (lambda value: value['targets'].append({'targetUserId': 10}), '被评价人不能重复'),
        (
            lambda value: value['relations'].__setitem__(0, {**value['relations'][0], 'relationType': 'PEER'}),
            '类型不能修改',
        ),
        (
            lambda value: value['evaluatorSelections'].__setitem__(
                0,
                {'targetUserId': 10, 'relationCode': 'REL_SELF', 'evaluatorUserIds': [10]},
            ),
            '后端自动派生',
        ),
        (
            lambda value: value['evaluatorSelections'].__setitem__(
                0,
                {'targetUserId': 10, 'relationCode': 'REL_SUPERVISOR', 'evaluatorUserIds': [10]},
            ),
            '不能把被评价人本人作为评价人',
        ),
        (
            lambda value: value['relations'].append(
                {
                    'relationCode': 'CUSTOM_REVIEWER',
                    'relationType': 'CUSTOM',
                    'relationName': '项目伙伴',
                    'isEnabled': False,
                    'participatesInScore': False,
                    'weight': '0.0000',
                    'sortOrder': 6,
                }
            ),
            '必须以REL_开头',
        ),
    ],
)
def test_publication_config_rejects_identity_and_selection_tampering(
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    payload = valid_config_payload()
    mutate(payload)

    with pytest.raises(ValidationError, match=message):
        PublicationConfigSaveModel.model_validate(payload)


def test_publication_validator_returns_questionnaire_and_relation_issues_in_stable_order() -> None:
    questionnaire = SimpleNamespace(pages=[], indicators=[])
    target = SimpleNamespace(target_id=7, target_user_id=10, target_user_name='张三')
    self_relation = SimpleNamespace(
        relation_id=1,
        relation_code='REL_SELF',
        relation_name='自己',
        is_enabled=True,
        participates_in_score=False,
        weight=Decimal('0.0000'),
    )
    scored_relation = SimpleNamespace(
        relation_id=2,
        relation_code='REL_PEER',
        relation_name='同级',
        is_enabled=True,
        participates_in_score=True,
        weight=Decimal('80.0000'),
    )
    selections = [
        SimpleNamespace(target_id=7, target_user_id=10, relation_id=1, evaluator_user_id=10),
        SimpleNamespace(target_id=7, target_user_id=10, relation_id=2, evaluator_user_id=11),
    ]

    issues = get_publication_validation_issues(
        questionnaire,
        [target],
        [self_relation, scored_relation],
        selections,
        unavailable_target_ids={10},
        unavailable_evaluator_ids={11},
    )

    assert [item['code'] for item in issues] == [
        'QUESTIONNAIRE_NO_QUESTIONS',
        'INDICATOR_WEIGHT_TOTAL_INVALID',
        'TARGET_USER_UNAVAILABLE',
        'RELATION_WEIGHT_TOTAL_INVALID',
        'EVALUATOR_USER_UNAVAILABLE',
    ]
