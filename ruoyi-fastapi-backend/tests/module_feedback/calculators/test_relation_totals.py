from decimal import Decimal

from module_feedback.calculators.report_score import relation_totals


def test_relation_totals_average_all_indicators_without_weights() -> None:
    rows = [
        {'result_type': 'INDICATOR_COMPOSITE', 'indicator_id': 1, 'original_weight': Decimal('20')},
        {'result_type': 'INDICATOR_COMPOSITE', 'indicator_id': 2, 'original_weight': Decimal('80')},
        {'result_type': 'INDICATOR_COMPOSITE', 'indicator_id': 3, 'original_weight': Decimal('0')},
    ]
    for relation_id, scores in [(8, ['53.2149', '61.0249', '90']), (9, ['0', '0', '0']), (10, ['80', None, '90'])]:
        rows.extend(
            {
                'result_type': 'INDICATOR_RELATION',
                'indicator_id': index,
                'relation_id': relation_id,
                'score': Decimal(score) if score is not None else None,
            }
            for index, score in enumerate(scores, 1)
        )
    assert relation_totals(rows) == {8: '68.08', 9: '0.00', 10: None}


def test_relation_totals_do_not_fill_absent_indicator() -> None:
    assert relation_totals(
        [
            {'result_type': 'INDICATOR_COMPOSITE', 'indicator_id': 1, 'original_weight': Decimal('100')},
            {'result_type': 'INDICATOR_RELATION', 'indicator_id': 2, 'relation_id': 8, 'score': Decimal('80')},
        ]
    ) == {8: None}
