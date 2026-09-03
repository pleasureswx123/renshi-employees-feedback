"""评价业务数据库访问层。"""

from module_feedback.dao.answer_dao import FeedbackAnswerDao
from module_feedback.dao.assignment_dao import FeedbackAssignmentDao
from module_feedback.dao.progress_dao import FeedbackProgressDao
from module_feedback.dao.project_dao import FeedbackProjectDao
from module_feedback.dao.publication_dao import FeedbackPublicationDao
from module_feedback.dao.questionnaire_dao import FeedbackQuestionnaireDao
from module_feedback.dao.score_result_dao import FeedbackScoreResultDao

__all__ = [
    'FeedbackAnswerDao',
    'FeedbackAssignmentDao',
    'FeedbackProgressDao',
    'FeedbackProjectDao',
    'FeedbackPublicationDao',
    'FeedbackQuestionnaireDao',
    'FeedbackScoreResultDao',
]
