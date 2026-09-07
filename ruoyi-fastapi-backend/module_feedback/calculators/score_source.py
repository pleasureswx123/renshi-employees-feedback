"""将冻结计算依据投影为可核对的公式，不写入或覆盖正式结果。"""

from decimal import Decimal, localcontext

from module_feedback.calculators.report_score import CALCULATION_VERSION, PRECISION, calculate_report, display_decimal


def source_rows(basis: dict, persisted_score: Decimal | None, *, detail: tuple[int, int] | None = None) -> list[dict]:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return _source_rows(basis, persisted_score, detail=detail)


def _source_rows(basis: dict, persisted_score: Decimal | None, *, detail: tuple[int, int] | None) -> list[dict]:
    inputs = basis['inputs']
    if inputs['scoringRule']['calculationVersion'] != CALCULATION_VERSION:
        raise ValueError('未知计分版本')
    results, report = calculate_report(inputs)
    total = next(item for item in results if item['result_type'] == 'PERSON_TOTAL')
    if (
        total['score'] != persisted_score
        or report != basis['report']
        or total['calculation_basis']['score'] != basis['score']
    ):
        raise ValueError('冻结依据与正式结果不一致')
    rows = []

    def add(
        key: str,
        parent: str | None,
        level: str,
        label: str,
        formula: str,
        value: Decimal | None,
        note: str = '',
        indicator_id: int | None = None,
        relation_id: int | None = None,
    ) -> None:
        rows.append(
            {
                'key': key,
                'parentKey': parent,
                'level': level,
                'label': label,
                'formula': formula,
                'result': display_decimal(value),
                'exactResult': str(value) if value is not None else None,
                'note': note,
                'indicatorId': indicator_id,
                'relationId': relation_id,
            }
        )

    composites = {r['indicator_id']: r for r in results if r['result_type'] == 'INDICATOR_COMPOSITE'}
    relations = {(r['indicator_id'], r['relation_id']): r for r in results if r['result_type'] == 'INDICATOR_RELATION'}
    indicators = inputs['indicators']
    total_terms = [
        f'{composites[i["indicatorId"]]["score"]} × {i["weight"]}%' for i in indicators if Decimal(i['weight']) > 0
    ]
    if detail is None:
        add(
            'total',
            None,
            'total',
            '最终得分',
            ' + '.join(total_terms) if total['score'] is not None else '有效指标数据不足，不能合成最终得分',
            total['score'],
            '各指标最终得分 × 指标权重；按未舍入数值计算。',
        )
    for ind in indicators:
        iid = ind['indicatorId']
        if detail and detail[0] != iid:
            continue
        ikey = f'i-{iid}'
        composite = composites[iid]
        effective = [
            relations[(iid, r['relationId'])]
            for r in inputs['relations']
            if relations[(iid, r['relationId'])]['effective_weight'] > 0
        ]
        indicator_formula = _indicator_formula(inputs['onlySelfEvaluation'], effective)
        if detail is None:
            add(
                ikey,
                'total',
                'indicator',
                ind['indicatorName'],
                indicator_formula,
                composite['score'],
                f'指标权重 {ind["weight"]}%；'
                + ('仅自评计分。' if inputs['onlySelfEvaluation'] else '自评不计入本指标最终得分。'),
                iid,
            )
        for rel in inputs['relations']:
            rid = rel['relationId']
            if detail and detail[1] != rid:
                continue
            rkey = f'{ikey}-r-{rid}'
            item = relations[(iid, rid)]
            sheets = item['calculation_basis']['sheetScores']
            values = [Decimal(s['score']) for s in sheets if s['score'] is not None]
            formula = f'{sum(values, Decimal(0))} ÷ {len(values)}' if values else '没有有效已提交答卷'
            add(
                rkey,
                ikey if detail is None else None,
                'relation',
                f'{ind["indicatorName"]} · {rel["relationName"]}',
                formula,
                item['score'],
                f'已提交 {item["submitted_count"]}/{item["expected_count"]} 份；各答卷指标分之和 ÷ 有效份数；原权重 {item["original_weight"]}%，实际权重 {item["effective_weight"]}%。',
                iid,
                rid,
            )
            if detail is None:
                continue
            rows[-1]['formula'] = (
                f'({" + ".join(str(value) for value in values)}) ÷ {len(values)}' if values else '没有有效已提交答卷'
            )
            questions = [q for q in inputs['questions'] if q['questionId'] in ind['questionIds'] and q['isScored']]
            for index, sheet in enumerate(sheets, 1):
                skey = f'{rkey}-s-{index}'
                value = Decimal(sheet['score']) if sheet['score'] is not None else None
                add(
                    skey,
                    rkey,
                    'sheet',
                    f'{rel["relationName"]}答卷 {index}',
                    f'{sheet["rawSum"]} ÷ {sheet["maximum"]} × 100'
                    if value is not None
                    else '没有计分题满分，无法换算',
                    value,
                    '指标绑定题目实得分合计 ÷ 满分合计 × 100。',
                    iid,
                    rid,
                )
                frozen = next(
                    task['sheet']
                    for task in inputs['assignments']
                    if task.get('sheet', {}).get('sheetId') == sheet['sheetId']
                )
                earned_terms = [frozen['rawScores'].get(str(q['questionId'])) or '0（漏答）' for q in questions]
                rows[-1]['earnedFormula'] = ' + '.join(earned_terms) + f' = {sheet["rawSum"]}'
                rows[-1]['maximumFormula'] = ' + '.join(q['maxScore'] for q in questions) + f' = {sheet["maximum"]}'
                for q in questions:
                    raw = frozen['rawScores'].get(str(q['questionId']))
                    add(
                        f'{skey}-q-{q["questionId"]}',
                        skey,
                        'question',
                        q['title'],
                        f'实得分 {raw if raw is not None else "未作答"} / 满分 {q["maxScore"]}',
                        Decimal(raw) if raw is not None else None,
                        '原始题分（非百分制）。'
                        + ('漏答：不增加分子，满分仍计入分母。' if raw is None else '取自提交时保存的题目计分结果。'),
                        iid,
                        rid,
                    )
                    rows[-1].update(rawScore=raw, maxScore=q['maxScore'])
    if detail and not rows:
        raise ValueError('指标或关系不存在')
    return rows


def _indicator_formula(only_self: bool, effective: list[dict]) -> str:
    if only_self:
        return f'{effective[0]["score"]} × 100%' if effective else '没有有效自评答卷'
    terms = [f'{row["score"]} × {row["original_weight"]}' for row in effective]
    denominator = sum((row['original_weight'] for row in effective), Decimal(0))
    return f'({" + ".join(terms)}) ÷ {denominator}' if terms else '没有有效计分关系'
