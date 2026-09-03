from collections import defaultdict
from decimal import Decimal
from typing import Any

from module_feedback.calculators.raw_score import calculate_raw_score
from module_feedback.service.publication_service import FeedbackPublicationService
from module_feedback.validators.questionnaire_validator import calculate_question_max_score


def _submitted_sheet(sheet: Any, task: Any, version: Any, rule: dict, questions: dict, answers_by_sheet: dict) -> dict:
    snapshot = sheet.submission_snapshot
    expected = {
        'schemaVersion': 1,
        'versionId': version.version_id,
        'evaluatorUserId': task.evaluator_user_id,
        'targetUserId': task.target_user_id,
        'relationId': task.relation_id,
        'scoringRule': rule,
    }
    if any(snapshot.get(key) != value for key, value in expected.items()) or not snapshot.get('answerDigest'):
        raise ValueError('提交快照与任务不一致')
    raw_scores = {}
    recorded = {item['questionId']: item['rawScore'] for item in snapshot['questionScores']}
    sheet_answers = answers_by_sheet[sheet.sheet_id]
    for answer in sheet_answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise ValueError('答案不属于冻结版本')
        raw_score = calculate_raw_score(question, answer)
        recorded_score = recorded.get(answer.question_id)
        recorded_score = Decimal(recorded_score) if recorded_score is not None else None
        if raw_score != answer.raw_score or raw_score != recorded_score:
            raise ValueError('原始题分与冻结题目或提交快照不一致')
        if raw_score is not None:
            if not Decimal('0') <= raw_score <= calculate_question_max_score(question):
                raise ValueError('正式原始分超出冻结题目范围')
            raw_scores[str(answer.question_id)] = str(raw_score)
    answered = {answer.question_id for answer in sheet_answers}
    if set(recorded) != answered or any(q.is_required and q.question_id not in answered for q in questions.values()):
        raise ValueError('正式答案集合与提交快照或必答规则不一致')
    if sum((Decimal(value) for value in raw_scores.values()), Decimal('0')) != sheet.raw_total_score:
        raise ValueError('正式原始总分与题分不一致')
    return {
        'sheetId': sheet.sheet_id,
        'answerDigest': snapshot['answerDigest'],
        'answeredQuestionIds': sorted(answered),
        'rawScores': raw_scores,
    }


def build_scoring_inputs(version: Any, targets: list, tasks: list, sheets: list, answers: list) -> dict[int, dict]:
    """交叉核对冻结版本与提交事实，生成可永久复算且无答案原文的输入。"""
    rule = version.scoring_rule_snapshot
    if version.status != 'FROZEN' or rule != FeedbackPublicationService._scoring_snapshot(version, version.relations):
        raise ValueError('冻结配置与发布计分快照不一致')
    questions = {q.question_id: q for page in version.pages for q in page.questions}
    sheet_by_task = {sheet.assignment_id: sheet for sheet in sheets}
    answers_by_sheet = defaultdict(list)
    for answer in answers:
        answers_by_sheet[answer.sheet_id].append(answer)
    task_groups = defaultdict(list)
    for task in tasks:
        if task.status not in {'SUBMITTED', 'CLOSED_INCOMPLETE'}:
            raise ValueError('已完成项目仍有可编辑任务')
        entry = {'assignmentId': task.assignment_id, 'relationId': task.relation_id, 'status': task.status}
        if task.status == 'SUBMITTED':
            sheet = sheet_by_task.get(task.assignment_id)
            if sheet is None or sheet.submitted_time is None:
                raise ValueError('已提交任务缺少正式答卷')
            entry['sheet'] = _submitted_sheet(sheet, task, version, rule, questions, answers_by_sheet)
        task_groups[task.target_id].append(entry)
    common = {
        'versionId': version.version_id,
        'scoringRule': rule,
        'questions': [
            {
                'questionId': q.question_id,
                'title': q.title,
                'questionType': q.question_type,
                'isScored': q.is_scored and q.question_type != 'TEXT',
                'isRequired': q.is_required,
                'maxScore': str(calculate_question_max_score(q)),
            }
            for q in questions.values()
        ],
        'indicators': [
            {
                'indicatorId': i.indicator_id,
                'indicatorName': i.indicator_name,
                'weight': str(i.weight),
                'questionIds': sorted(binding.question_id for binding in i.question_bindings),
            }
            for i in version.indicators
        ],
        'relations': [
            {
                'relationId': r.relation_id,
                'relationName': r.relation_name,
                'relationCode': r.relation_code,
                'relationType': r.relation_type,
                'participatesInScore': r.participates_in_score,
                'weight': str(r.weight),
            }
            for r in version.relations
            if r.is_enabled
        ],
    }
    relation_ids = {r['relationId'] for r in common['relations']}
    if any(task.relation_id not in relation_ids for task in tasks):
        raise ValueError('任务引用了未启用的冻结关系')
    return {
        target.target_id: {
            **common,
            'targetUserId': target.target_user_id,
            'onlySelfEvaluation': target.only_self_evaluation,
            'assignments': task_groups[target.target_id],
        }
        for target in targets
    }
