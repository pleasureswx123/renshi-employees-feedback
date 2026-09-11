import json
from decimal import Decimal
from typing import Any

ALLOWED_RICH_TEXT_NODES = {
    'doc',
    'paragraph',
    'heading',
    'bulletList',
    'orderedList',
    'listItem',
    'blockquote',
    'hardBreak',
    'text',
}
ALLOWED_RICH_TEXT_MARKS = {'bold', 'italic', 'underline', 'strike'}
MAX_RICH_TEXT_BYTES = 100 * 1024
MAX_RICH_TEXT_NODES = 1000
MAX_RICH_TEXT_DEPTH = 20
MAX_RICH_TEXT_CHARACTERS = 5000
MAX_QUESTION_COUNT = 500


def _validate_rich_text_attributes(node_type: str, attrs: Any) -> None:
    if attrs is None:
        return
    if not isinstance(attrs, dict):
        raise ValueError('富文本节点属性必须是对象')
    if node_type == 'heading':
        if set(attrs) != {'level'} or attrs['level'] not in {2, 3}:
            raise ValueError('富文本标题只允许二级或三级')
        return
    if node_type == 'orderedList':
        if set(attrs) - {'start', 'type'}:
            raise ValueError('富文本有序列表包含未知属性')
        start = attrs.get('start', 1)
        if not isinstance(start, int) or isinstance(start, bool) or start < 1:
            raise ValueError('富文本有序列表起始序号非法')
        if attrs.get('type') not in {None, '1'}:
            raise ValueError('富文本有序列表类型非法')
        return
    if attrs:
        raise ValueError(f'富文本节点{node_type}不允许附加属性')


def extract_rich_text(document: dict[str, Any] | None) -> str | None:  # noqa: PLR0915
    """校验受限Tiptap JSON并提取纯文本摘要。"""
    if document is None:
        return None
    if not isinstance(document, dict) or document.get('type') != 'doc':
        raise ValueError('富文本根节点必须为doc')
    serialized = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(serialized) > MAX_RICH_TEXT_BYTES:
        raise ValueError('富文本JSON不能超过100KB')

    text_parts: list[str] = []
    node_count = 0

    def visit(node: Any, depth: int) -> None:  # noqa: PLR0912
        nonlocal node_count
        if depth > MAX_RICH_TEXT_DEPTH:
            raise ValueError('富文本嵌套深度不能超过20层')
        if not isinstance(node, dict):
            raise ValueError('富文本节点必须是对象')
        if set(node) - {'type', 'attrs', 'content', 'text', 'marks'}:
            raise ValueError('富文本节点包含未知字段')
        node_type = node.get('type')
        if node_type not in ALLOWED_RICH_TEXT_NODES:
            raise ValueError(f'富文本包含未允许节点：{node_type}')
        node_count += 1
        if node_count > MAX_RICH_TEXT_NODES:
            raise ValueError('富文本节点数不能超过1000个')
        _validate_rich_text_attributes(str(node_type), node.get('attrs'))

        marks = node.get('marks', [])
        if not isinstance(marks, list):
            raise ValueError('富文本marks必须是数组')
        for mark in marks:
            if not isinstance(mark, dict) or set(mark) - {'type'}:
                raise ValueError('富文本mark结构非法')
            if mark.get('type') not in ALLOWED_RICH_TEXT_MARKS:
                raise ValueError(f'富文本包含未允许mark：{mark.get("type")}')

        if node_type == 'text':
            if set(node) - {'type', 'text', 'marks'}:
                raise ValueError('富文本text节点包含非法字段')
            text_value = node.get('text')
            if not isinstance(text_value, str):
                raise ValueError('富文本text节点必须包含字符串')
            text_parts.append(text_value)
            return
        if 'text' in node or 'marks' in node:
            raise ValueError(f'富文本节点{node_type}不允许text或marks字段')

        content = node.get('content', [])
        if not isinstance(content, list):
            raise ValueError('富文本content必须是数组')
        for child in content:
            visit(child, depth + 1)
        if node_type in {'paragraph', 'heading', 'listItem', 'blockquote'} and text_parts:
            text_parts.append('\n')
        if node_type == 'hardBreak':
            text_parts.append('\n')

    visit(document, 1)
    plain_text = ''.join(text_parts).strip()
    if len(plain_text) > MAX_RICH_TEXT_CHARACTERS:
        raise ValueError('问卷说明纯文本不能超过5000字符')
    return plain_text or None


def _ensure_continuous(values: list[int], label: str) -> None:
    if values != list(range(1, len(values) + 1)):
        raise ValueError(f'{label}必须从1开始连续排列')


def validate_draft_structure(draft: Any) -> None:
    """校验整份草稿的顺序、稳定标识和指标引用。"""
    _ensure_continuous([page.sort_order for page in draft.pages], '页面顺序')
    page_codes = [page.page_code for page in draft.pages]
    if len(page_codes) != len(set(page_codes)):
        raise ValueError('同一问卷版本的页面标识不能重复')

    questions = [question for page in draft.pages for question in page.questions]
    if len(questions) > MAX_QUESTION_COUNT:
        raise ValueError('整份问卷最多包含500道题')
    question_codes = [question.question_code for question in questions]
    if len(question_codes) != len(set(question_codes)):
        raise ValueError('同一问卷版本的题目标识不能重复')
    for page in draft.pages:
        _ensure_continuous([question.sort_order for question in page.questions], f'页面“{page.page_title}”的题目顺序')

    _ensure_continuous([indicator.sort_order for indicator in draft.indicators], '指标顺序')
    indicator_codes = [indicator.indicator_code for indicator in draft.indicators]
    if len(indicator_codes) != len(set(indicator_codes)):
        raise ValueError('同一问卷版本的指标标识不能重复')
    indicator_names = [indicator.indicator_name for indicator in draft.indicators]
    if len(indicator_names) != len(set(indicator_names)):
        raise ValueError('同一问卷版本的指标名称不能重复')

    known_question_codes = set(question_codes)
    bound_question_codes: set[str] = set()
    for indicator in draft.indicators:
        unknown_codes = set(indicator.question_codes) - known_question_codes
        if unknown_codes:
            raise ValueError(f'指标“{indicator.indicator_name}”绑定了不存在的题目')
        duplicate_bindings = bound_question_codes.intersection(indicator.question_codes)
        if duplicate_bindings:
            raise ValueError('一道题最多绑定一个指标')
        bound_question_codes.update(indicator.question_codes)


def calculate_question_max_score(question: Any) -> Decimal:
    """返回一道题参与计分时的原始满分贡献。"""
    if not question.is_scored or question.question_type == 'TEXT':
        return Decimal('0')
    if question.question_type == 'SINGLE_CHOICE':
        return max((option.score for option in question.options), default=Decimal('0'))
    return question.max_score


def get_option_score_validation_issues(draft: Any) -> list[dict[str, str]]:
    """限制新保存、发布的单选题分值，不改写历史冻结数据。"""
    return [
        {
            'code': 'OPTION_SCORE_POSITIVE_REQUIRED' if option.score < 1 else 'OPTION_SCORE_INTEGER_REQUIRED',
            'path': f'pages.{page_index}.questions.{question_index}.options.{option_index}.score',
            'message': f'单选题“{question.title}”的选项“{option.option_label}”分值必须是大于等于1的整数',
        }
        for page_index, page in enumerate(draft.pages)
        for question_index, question in enumerate(page.questions)
        if question.question_type == 'SINGLE_CHOICE'
        for option_index, option in enumerate(question.options)
        if option.score < 1 or option.score != option.score.to_integral_value()
    ]


def get_publish_validation_issues(draft: Any) -> list[dict[str, str]]:
    """返回P4问卷和指标达到发布条件前的稳定问题清单。"""
    issues: list[dict[str, str]] = get_option_score_validation_issues(draft)
    question_entries = [
        (page_index, question_index, question)
        for page_index, page in enumerate(draft.pages)
        for question_index, question in enumerate(page.questions)
    ]
    if not question_entries:
        issues.append(
            {
                'code': 'QUESTIONNAIRE_NO_QUESTIONS',
                'path': 'pages',
                'message': '问卷至少需要一道题',
            }
        )

    total_weight = sum((indicator.weight for indicator in draft.indicators), Decimal('0'))
    if total_weight != Decimal('100.0000'):
        issues.append(
            {
                'code': 'INDICATOR_WEIGHT_TOTAL_INVALID',
                'path': 'indicators',
                'message': f'指标权重合计必须为100.0000，当前为{total_weight:.4f}',
            }
        )

    indicator_by_question = {
        question_code: (indicator_index, indicator)
        for indicator_index, indicator in enumerate(draft.indicators)
        for question_code in indicator.question_codes
    }
    for page_index, question_index, question in question_entries:
        if question.is_scored and question.question_code not in indicator_by_question:
            issues.append(
                {
                    'code': 'SCORED_QUESTION_INDICATOR_REQUIRED',
                    'path': f'pages.{page_index}.questions.{question_index}',
                    'message': f'计分题“{question.title}”必须绑定一个指标',
                }
            )

    question_by_code = {question.question_code: question for _, _, question in question_entries}
    for indicator_index, indicator in enumerate(draft.indicators):
        scored_max = sum(
            (
                calculate_question_max_score(question_by_code[code])
                for code in indicator.question_codes
                if code in question_by_code
            ),
            Decimal('0'),
        )
        if scored_max <= 0:
            issues.append(
                {
                    'code': 'INDICATOR_SCORED_QUESTION_REQUIRED',
                    'path': f'indicators.{indicator_index}.questionCodes',
                    'message': f'指标“{indicator.indicator_name}”至少需要一道满分大于0的计分题',
                }
            )
    return issues
