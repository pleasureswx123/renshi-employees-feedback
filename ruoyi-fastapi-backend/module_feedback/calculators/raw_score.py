from decimal import Decimal

from module_feedback.entity.do import FbQuestion
from module_feedback.entity.vo.employee_vo import AnswerInputModel


def calculate_raw_score(question: FbQuestion, answer: AnswerInputModel) -> Decimal | None:
    """对通过校验的答案按冻结题目计算原始分；不做报告汇总。"""
    if not question.is_scored or question.question_type == 'TEXT':
        return None
    if question.question_type == 'SINGLE_CHOICE':
        return next(option.score for option in question.options if option.option_id == answer.option_id)
    return answer.numeric_value
