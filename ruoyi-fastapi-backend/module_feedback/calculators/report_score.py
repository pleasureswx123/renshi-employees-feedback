from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

CALCULATION_VERSION = 'feedback-score-v1'
PRECISION = 50
ZERO = Decimal('0')
HUNDRED = Decimal('100')


def display_decimal(value: Decimal | None) -> str | None:
    """只在展示边界舍入；零分和缺失值保持不同语义。"""
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')


def decimal_json(value: Any) -> Any:
    """计算依据只用十进制字符串，不经过二进制浮点数。"""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: decimal_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [decimal_json(item) for item in value]
    return value


def _average(values: list[Decimal]) -> Decimal | None:
    return sum(values, ZERO) / len(values) if values else None


def _weighted_total(indicators: list[dict], scores: dict[int, Decimal | None]) -> Decimal | None:
    weighted = [item for item in indicators if Decimal(item['weight']) > 0]
    if any(scores[item['indicatorId']] is None for item in weighted) or not weighted:
        return None
    return sum((scores[item['indicatorId']] * Decimal(item['weight']) for item in weighted), ZERO) / HUNDRED


def _group_status(expected: int, submitted: int) -> str:
    if not expected:
        return 'NOT_APPLICABLE'
    if not submitted:
        return 'MISSING'
    return 'COMPLETE' if submitted == expected else 'PARTIAL'


def _question_rows(questions: list[dict], groups: list[dict]) -> list[dict]:
    rows = []
    for question in questions:
        question_id = question['questionId']
        for group in groups:
            answered = [sheet for sheet in group['sheets'] if question_id in sheet['answeredQuestionIds']]
            values = [
                Decimal(sheet['rawScores'][str(question_id)])
                for sheet in answered
                if sheet['rawScores'].get(str(question_id)) is not None
            ]
            raw_average = _average(values)
            maximum = Decimal(question['maxScore'])
            rows.append(
                {
                    'questionId': question_id,
                    'title': question['title'],
                    'questionType': question['questionType'],
                    'isScored': question['isScored'],
                    'maxScore': display_decimal(maximum) if maximum else None,
                    'relationId': group['relationId'],
                    'relationName': group['relationName'],
                    'submittedCount': len(group['sheets']),
                    'answeredCount': len(answered),
                    'missingAnswerCount': len(group['sheets']) - len(answered),
                    'rawAverage': display_decimal(raw_average),
                    'score': display_decimal(raw_average / maximum * HUNDRED)
                    if raw_average is not None and maximum
                    else None,
                }
            )
    return rows


def calculate_report(inputs: dict) -> tuple[list[dict], dict]:
    """依据无原文的冻结输入计算全部粒度结果；无数据库或身份查询副作用。"""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return _calculate(inputs)


def _calculation_groups(inputs: dict) -> tuple[list[dict], bool, int, int]:
    groups = []
    for relation in inputs['relations']:
        tasks = [task for task in inputs['assignments'] if task['relationId'] == relation['relationId']]
        sheets = [task['sheet'] for task in tasks if task['status'] == 'SUBMITTED']
        groups.append({**relation, 'tasks': tasks, 'sheets': sheets})
    only_self = inputs['onlySelfEvaluation']
    non_self_tasks = [task for group in groups if group['relationType'] != 'SELF' for task in group['tasks']]
    if only_self != (not non_self_tasks):
        raise ValueError('发布时仅自评标记与任务集合不一致')
    expected = len(inputs['assignments'])
    submitted = sum(len(group['sheets']) for group in groups)
    if expected == 0:
        raise ValueError('发布目标没有任务')
    return groups, only_self, expected, submitted


def _calculate(inputs: dict) -> tuple[list[dict], dict]:
    questions = {question['questionId']: question for question in inputs['questions']}
    indicators = inputs['indicators']
    if inputs['scoringRule']['calculationVersion'] != CALCULATION_VERSION:
        raise ValueError('不支持的冻结计分规则版本')
    if sum((Decimal(item['weight']) for item in indicators), ZERO) != HUNDRED:
        raise ValueError('冻结指标权重不等于100%')
    groups, only_self, expected, submitted = _calculation_groups(inputs)
    coverage = Decimal(submitted) / expected * HUNDRED
    results = []
    indicator_rows = []
    composite_scores, self_scores, other_scores = {}, {}, {}
    coverage_rows = [
        {
            'relationId': group['relationId'],
            'relationName': group['relationName'],
            'relationType': group['relationType'],
            'status': _group_status(len(group['tasks']), len(group['sheets'])),
            'expectedCount': len(group['tasks']),
            'submittedCount': len(group['sheets']),
        }
        for group in groups
    ]
    for indicator in indicators:
        indicator_id = indicator['indicatorId']
        scored = [questions[qid] for qid in indicator['questionIds'] if questions[qid]['isScored']]
        maximum = sum((Decimal(question['maxScore']) for question in scored), ZERO)
        if not maximum and Decimal(indicator['weight']) > 0:
            raise ValueError('正权重指标缺少计分题')
        relation_values = []
        for group in groups:
            sheet_scores = []
            for sheet in group['sheets']:
                raw_sum = sum((Decimal(sheet['rawScores'].get(str(q['questionId'])) or '0') for q in scored), ZERO)
                sheet_scores.append(
                    {
                        'sheetId': sheet['sheetId'],
                        'rawSum': raw_sum,
                        'maximum': maximum,
                        'score': raw_sum / maximum * HUNDRED if maximum else None,
                    }
                )
            score = _average([item['score'] for item in sheet_scores if item['score'] is not None])
            is_self = group['relationType'] == 'SELF'
            eligible = bool(score is not None and not is_self and group['participatesInScore'])
            relation_values.append(
                {
                    'group': group,
                    'score': score,
                    'sheetScores': sheet_scores,
                    'weight': Decimal(group['weight']) if eligible else ZERO,
                }
            )
        denominator = sum((item['weight'] for item in relation_values), ZERO)
        other_score = (
            sum((item['score'] * item['weight'] for item in relation_values if item['weight']), ZERO) / denominator
            if denominator
            else None
        )
        self_score = _average(
            [
                item['score']
                for item in relation_values
                if item['group']['relationType'] == 'SELF' and item['score'] is not None
            ]
        )
        score = self_score if only_self else other_score
        composite_scores[indicator_id], self_scores[indicator_id], other_scores[indicator_id] = (
            score,
            self_score,
            other_score,
        )
        relation_rows = []
        for item in relation_values:
            group = item['group']
            if only_self:
                effective = HUNDRED if group['relationType'] == 'SELF' and item['score'] is not None else ZERO
            else:
                effective = item['weight'] / denominator * HUNDRED if denominator else ZERO
            missing_answers = sum(
                str(question['questionId']) not in sheet['rawScores']
                for sheet in group['sheets']
                for question in scored
            )
            missing = len(group['tasks']) > len(group['sheets']) or bool(missing_answers)
            results.append(
                {
                    'result_type': 'INDICATOR_RELATION',
                    'indicator_id': indicator_id,
                    'relation_id': group['relationId'],
                    'score': item['score'],
                    'original_weight': Decimal(group['weight']),
                    'effective_weight': effective,
                    'expected_count': len(group['tasks']),
                    'submitted_count': len(group['sheets']),
                    'has_missing_data': missing,
                    'calculation_basis': decimal_json(
                        {'sheetScores': item['sheetScores'], 'effectiveWeight': effective}
                    ),
                }
            )
            relation_rows.append(
                {
                    **next(row for row in coverage_rows if row['relationId'] == group['relationId']),
                    'score': display_decimal(item['score']),
                    'originalWeight': display_decimal(Decimal(group['weight'])),
                    'effectiveWeight': display_decimal(effective),
                    'missingAnswerCount': missing_answers,
                }
            )
        results.append(
            {
                'result_type': 'INDICATOR_COMPOSITE',
                'indicator_id': indicator_id,
                'score': score,
                'original_weight': Decimal(indicator['weight']),
                'effective_weight': Decimal(indicator['weight']),
                'expected_count': expected,
                'submitted_count': submitted,
                'has_missing_data': expected > submitted or any(row['missingAnswerCount'] for row in relation_rows),
                'calculation_basis': decimal_json({'selfScore': self_score, 'otherScore': other_score, 'score': score}),
            }
        )
        indicator_rows.append(
            {
                'indicatorId': indicator_id,
                'indicatorName': indicator['indicatorName'],
                'weight': display_decimal(Decimal(indicator['weight'])),
                'score': display_decimal(score),
                'selfScore': display_decimal(self_score),
                'otherScore': display_decimal(other_score),
                'relations': relation_rows,
            }
        )
    total_score = _weighted_total(indicators, composite_scores)
    self_total = _weighted_total(indicators, self_scores)
    other_total = _weighted_total(indicators, other_scores)
    question_rows = _question_rows(inputs['questions'], groups)
    has_missing = expected > submitted or any(row['missingAnswerCount'] for row in question_rows)
    report = {
        'targetUserId': inputs['targetUserId'],
        'onlySelfEvaluation': only_self,
        'score': display_decimal(total_score),
        'selfScore': display_decimal(self_total),
        'otherScore': display_decimal(other_total),
        'expectedCount': expected,
        'submittedCount': submitted,
        'completionRate': display_decimal(coverage),
        'hasMissingData': has_missing,
        'insufficientData': total_score is None,
        'relations': coverage_rows,
        'indicators': indicator_rows,
        'questions': question_rows,
    }
    results.extend(
        [
            {
                'result_type': 'PERSON_TOTAL',
                'score': total_score,
                'expected_count': expected,
                'submitted_count': submitted,
                'has_missing_data': has_missing,
                'calculation_basis': decimal_json(
                    {
                        'precision': PRECISION,
                        'inputs': inputs,
                        'report': report,
                        'indicatorScores': {str(key): value for key, value in composite_scores.items()},
                        'score': total_score,
                        'selfScore': self_total,
                        'otherScore': other_total,
                    }
                ),
            },
            {
                'result_type': 'COVERAGE',
                'score': coverage,
                'expected_count': expected,
                'submitted_count': submitted,
                'has_missing_data': has_missing,
                'calculation_basis': {'expectedCount': expected, 'submittedCount': submitted},
            },
        ]
    )
    return results, report
