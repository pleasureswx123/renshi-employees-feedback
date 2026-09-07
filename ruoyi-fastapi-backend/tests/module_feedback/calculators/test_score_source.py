from copy import deepcopy
from decimal import Decimal

import pytest

from module_feedback.calculators.report_score import calculate_report
from module_feedback.calculators.score_source import source_rows
from tests.module_feedback.calculators.test_p8_report_score import sample


def basis_for(inputs: dict) -> tuple:
    results, _ = calculate_report(inputs)
    total = next(row for row in results if row['result_type'] == 'PERSON_TOTAL')
    return total['calculation_basis'], total['score']


def test_source_whitelist_and_exact_formulas() -> None:
    basis, score = basis_for(sample())
    before = deepcopy(basis)
    rows = source_rows(basis, score)
    assert rows[0]['result'] == '83.00'
    assert rows[1]['formula'] == '(90.0 × 50 + 80.0 × 30 + 70.0 × 20) ÷ 100'
    assert rows[2]['formula'] == '90.0 ÷ 1'
    assert all(row['level'] not in {'sheet', 'question'} for row in rows)
    assert not any(word in str(rows) for word in ['sheetId', 'answerDigest', 'assignmentId', 'rawScores'])
    assert basis == before
    detail = source_rows(basis, score, detail=(1, 1))
    assert detail[1]['formula'] == '90 ÷ 100 × 100'
    assert detail[2]['formula'] == '实得分 90 / 满分 100'


@pytest.mark.parametrize('inputs', [sample(only_self=True), sample({}), sample({1: ['0']}), sample({1: ['80', '100']})])
def test_source_self_missing_zero_and_average(inputs: dict) -> None:
    basis, score = basis_for(inputs)
    rows = source_rows(basis, score)
    assert rows[0]['exactResult'] == (str(score) if score is not None else None)


def test_source_rejects_inconsistent_result() -> None:
    basis, score = basis_for(sample())
    with pytest.raises(ValueError):
        source_rows(basis, score + Decimal(1))
    basis['report']['score'] = '99.00'
    with pytest.raises(ValueError):
        source_rows(basis, score)


def test_missing_question_keeps_denominator() -> None:
    inputs = sample({1: ['90']})
    inputs['questions'].append(
        {'questionId': 2, 'title': '可选题', 'questionType': 'NUMERIC_INPUT', 'isScored': True, 'maxScore': '100'}
    )
    inputs['indicators'][0]['questionIds'].append(2)
    basis, score = basis_for(inputs)
    rows = source_rows(basis, score, detail=(1, 1))
    assert rows[1]['formula'] == '90 ÷ 200 × 100'
    assert rows[1]['earnedFormula'] == '90 + 0（漏答） = 90'
    assert rows[1]['maximumFormula'] == '100 + 100 = 200'
    assert rows[-1]['rawScore'] is None
    assert rows[-1]['maxScore'] == '100'
    assert rows[-1]['result'] is None
    assert '漏答' in rows[-1]['note']
