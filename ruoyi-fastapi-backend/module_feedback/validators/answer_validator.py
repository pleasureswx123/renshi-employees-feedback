from decimal import Decimal

from module_feedback.entity.do import FbQuestion, FbQuestionnaireVersion
from module_feedback.entity.vo.employee_vo import AnswerDraftSaveModel, AnswerInputModel
from module_feedback.entity.vo.questionnaire_question_vo import decimal_places


def _option_issues(question: FbQuestion, answer: AnswerInputModel, submitting: bool) -> list[tuple[str, str]]:
    option = next((item for item in question.options if item.option_id == answer.option_id), None)
    if option is None:
        return [('INVALID_OPTION', '请选择当前题目的有效选项')]
    if submitting and option.requires_reason and not answer.reason:
        return [('REASON_REQUIRED', '请填写所选选项的附加原因')]
    if not option.requires_reason and answer.reason:
        return [('UNEXPECTED_REASON', '当前选项不接受附加原因')]
    return []


def _text_issues(question: FbQuestion, answer: AnswerInputModel, submitting: bool) -> list[tuple[str, str]]:
    if answer.text_value is None or answer.reason is not None:
        return [('INVALID_ANSWER_TYPE', '问答题只接受文本答案')]
    if len(answer.text_value) > int(question.config.get('maxLength', 1000)):
        return [('TEXT_TOO_LONG', '文字回答超过允许字数')]
    if submitting and question.is_required and not answer.text_value.strip():
        return [('REQUIRED', '请完成这道必答题')]
    return []


def _numeric_issues(question: FbQuestion, answer: AnswerInputModel) -> list[tuple[str, str]]:
    value = answer.numeric_value
    if value is None or answer.reason is not None:
        return [('INVALID_ANSWER_TYPE', '评分题只接受数值答案')]
    issues = []
    if not question.min_score <= value <= question.max_score:
        issues.append(('OUT_OF_RANGE', '分值超出允许范围'))
    if decimal_places(value) > question.decimal_places:
        issues.append(('INVALID_PRECISION', '分值小数位数超过题目限制'))
    if question.question_type == 'SLIDER' and (value - question.min_score) % Decimal(question.config['step']):
        issues.append(('INVALID_STEP', '滑动评分必须落在合法步长上'))
    return issues


def validate_answers(
    version: FbQuestionnaireVersion, request: AnswerDraftSaveModel, *, submitting: bool
) -> tuple[list[AnswerInputModel], list[dict]]:
    """依据冻结版本校验整份答案，返回规范化答案和可定位问题。"""
    issues: list[dict] = []
    normalized: list[AnswerInputModel] = []
    questions = {question.question_id: (page, question) for page in version.pages for question in page.questions}
    if request.last_page_id not in {page.page_id for page in version.pages}:
        issues.append({'code': 'INVALID_PAGE', 'pageId': None, 'questionId': None, 'message': '最近页面不属于当前问卷'})
    seen: set[int] = set()

    def issue(code: str, message: str, question_id: int) -> None:
        pair = questions.get(question_id)
        issues.append(
            {
                'code': code,
                'pageId': pair[0].page_id if pair else None,
                'questionId': question_id,
                'message': message,
            }
        )

    for answer in request.answers:
        question_id = answer.question_id
        if question_id in seen:
            issue('DUPLICATE_ANSWER', '同一道题不能重复作答', question_id)
            continue
        seen.add(question_id)
        if question_id not in questions:
            issue('INVALID_QUESTION', '题目不属于当前冻结问卷', question_id)
            continue
        _, question = questions[question_id]
        current = answer.model_copy(update={'reason': answer.reason.strip() if answer.reason else None})
        if question.question_type == 'SINGLE_CHOICE':
            value_issues = _option_issues(question, current, submitting)
        elif question.question_type == 'TEXT':
            value_issues = _text_issues(question, current, submitting)
        else:
            value_issues = _numeric_issues(question, current)
        for code, message in value_issues:
            issue(code, message, question_id)
        if not value_issues and not (answer.text_value is not None and not answer.text_value.strip()):
            normalized.append(current)
    if submitting:
        for question_id, (_, question) in questions.items():
            if question.is_required and question_id not in seen:
                issue('REQUIRED', '请完成这道必答题', question_id)
    return sorted(normalized, key=lambda answer: answer.question_id), issues
