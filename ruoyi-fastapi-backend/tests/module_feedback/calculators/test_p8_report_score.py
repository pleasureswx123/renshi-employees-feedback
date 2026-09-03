# ruff: noqa: PLR2004
from copy import deepcopy
from decimal import Decimal
from typing import Any

import pytest

from module_feedback.calculators.report_score import calculate_report, display_decimal


def sample(scores: Any = None, *, only_self: Any = False, absent: Any = ()) -> dict:
    scores = scores if scores is not None else {1: ['90'], 2: ['80'], 3: ['70'], 4: ['92']}
    relations = [
        {'relationId': i, 'relationName': name, 'relationType': kind, 'weight': weight, 'participatesInScore': i != 4}
        for i, name, kind, weight in [
            (1, '上级', 'SUPERVISOR', '50'),
            (2, '同级', 'PEER', '30'),
            (3, '下级', 'SUBORDINATE', '20'),
            (4, '自己', 'SELF', '0'),
        ]
    ]
    tasks = []
    for relation in relations:
        relation_id = relation['relationId']
        if relation_id in absent or (only_self and relation_id != 4):
            continue
        for score in scores.get(relation_id, [None]):
            task = {
                'assignmentId': len(tasks) + 1,
                'relationId': relation_id,
                'status': 'SUBMITTED' if score is not None else 'CLOSED_INCOMPLETE',
            }
            if score is not None:
                task['sheet'] = {
                    'sheetId': len(tasks) + 1,
                    'answerDigest': 'test',
                    'answeredQuestionIds': [1],
                    'rawScores': {'1': score},
                }
            tasks.append(task)
    return {
        'versionId': 1,
        'targetUserId': 1,
        'onlySelfEvaluation': only_self,
        'scoringRule': {'calculationVersion': 'feedback-score-v1'},
        'questions': [
            {'questionId': 1, 'title': '表现', 'questionType': 'NUMERIC_INPUT', 'isScored': True, 'maxScore': '100'}
        ],
        'indicators': [{'indicatorId': 1, 'indicatorName': '综合', 'weight': '100', 'questionIds': [1]}],
        'relations': relations,
        'assignments': tasks,
    }


@pytest.mark.parametrize(
    ('scores', 'absent', 'only_self', 'expected', 'rate'),
    [
        (None, (), False, '83.00', '100.00'),
        (None, (3,), False, '86.25', '100.00'),
        ({1: ['90'], 2: ['80'], 4: ['92']}, (), False, '86.25', '75.00'),
        (None, (), True, '92.00', '100.00'),
        ({4: ['92']}, (), False, None, '25.00'),
        ({}, (), False, None, '0.00'),
        ({1: ['0']}, (), False, '0.00', '25.00'),
        ({1: ['80', '100'], 2: ['80'], 3: ['70']}, (), False, '83.00', '80.00'),
    ],
)
def test_hand_calculation_samples(scores: Any, absent: Any, only_self: Any, expected: Any, rate: Any) -> None:
    inputs = sample(scores, absent=absent, only_self=only_self)
    original = deepcopy(inputs)
    rows, report = calculate_report(inputs)
    assert report['score'] == expected
    assert report['completionRate'] == rate
    assert inputs == original
    assert all(row['score'] is None or isinstance(row['score'], Decimal) for row in rows)


def test_missing_not_applicable_and_original_effective_weights() -> None:
    _, report = calculate_report(sample({1: ['90'], 2: ['80']}, absent=(3,)))
    relations = {r['relationId']: r for r in report['indicators'][0]['relations']}
    assert relations[1]['originalWeight'] == '50.00'
    assert relations[1]['effectiveWeight'] == '62.50'
    assert relations[3]['status'] == 'NOT_APPLICABLE'
    assert relations[4]['status'] == 'MISSING'
    assert relations[4]['score'] is None


def test_multiple_indicators_optional_missing_keeps_denominator_and_text_not_scored() -> None:
    inputs = sample({1: ['90']})
    inputs['questions'].extend(
        [
            {'questionId': 2, 'title': '可选', 'questionType': 'NUMERIC_INPUT', 'isScored': True, 'maxScore': '100'},
            {'questionId': 3, 'title': '文字', 'questionType': 'TEXT', 'isScored': False, 'maxScore': '0'},
        ]
    )
    inputs['indicators'] = [
        {'indicatorId': 1, 'indicatorName': '一', 'weight': '60', 'questionIds': [1]},
        {'indicatorId': 2, 'indicatorName': '二', 'weight': '40', 'questionIds': [2, 3]},
    ]
    rows, report = calculate_report(inputs)
    assert report['score'] == '54.00'
    assert report['indicators'][1]['score'] == '0.00'
    assert report['indicators'][1]['relations'][0]['missingAnswerCount'] == 1
    assert all(r['rawAverage'] is None for r in report['questions'] if r['questionId'] == 3)
    assert next(r for r in rows if r['result_type'] == 'PERSON_TOTAL')['calculation_basis']['inputs'] == inputs


def test_intermediate_precision_and_half_up_boundary() -> None:
    inputs = sample({1: ['1']}, absent=(2, 3, 4))
    inputs['questions'][0]['maxScore'] = '3'
    rows, report = calculate_report(inputs)
    score = next(r['score'] for r in rows if r['result_type'] == 'PERSON_TOTAL')
    assert str(score).startswith('33.333333333333333333333333333333333333')
    assert report['score'] == '33.33'
    assert display_decimal(Decimal('83.00499999999999999')) == '83.00'
    assert display_decimal(Decimal('83.005')) == '83.01'


def test_zero_weight_feedback_never_replaces_formal_score() -> None:
    inputs = sample({1: ['90'], 4: ['92']})
    inputs['relations'][0]['participatesInScore'] = False
    _, report = calculate_report(inputs)
    assert report['score'] is None
    assert report['selfScore'] == '92.00'
