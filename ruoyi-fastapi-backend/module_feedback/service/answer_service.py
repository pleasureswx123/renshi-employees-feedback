import hashlib
import json
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exception import ConflictException
from module_feedback.calculators.raw_score import calculate_raw_score
from module_feedback.dao.answer_dao import FeedbackAnswerDao
from module_feedback.dao.employee_dao import FeedbackEmployeeDao
from module_feedback.entity.do import FbAnswer, FbAnswerSheet, FbAssignment, FbQuestionnaireVersion
from module_feedback.entity.vo.employee_vo import (
    AnswerDraftSaveModel,
    AnswerInputModel,
    AnswerSubmitModel,
    EmployeeAnswerDetailModel,
)
from module_feedback.service.employee_service import FeedbackEmployeeService
from module_feedback.service.state_transition_service import FeedbackStateTransitionService
from module_feedback.validators.answer_validator import validate_answers


class FeedbackAnswerService:
    """暂存与不可变提交的单事务编排。"""

    @classmethod
    async def save_draft(
        cls, db: AsyncSession, assignment_id: int, evaluator_id: int, request: AnswerDraftSaveModel
    ) -> EmployeeAnswerDetailModel:
        return await cls._write(db, assignment_id, evaluator_id, request, submitting=False)

    @classmethod
    async def submit(
        cls, db: AsyncSession, assignment_id: int, evaluator_id: int, request: AnswerSubmitModel
    ) -> EmployeeAnswerDetailModel:
        return await cls._write(db, assignment_id, evaluator_id, request, submitting=True)

    @staticmethod
    def _fingerprint(version_id: int, answers: list[AnswerInputModel]) -> str:
        values = [answer.model_dump(mode='json', by_alias=True) for answer in answers]
        for value in values:
            if value['numericValue'] is not None:
                value['numericValue'] = format(Decimal(value['numericValue']).normalize(), 'f')
        payload = json.dumps({'versionId': version_id, 'answers': values}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _answer_rows(
        sheet: FbAnswerSheet, version: FbQuestionnaireVersion, answers: list[AnswerInputModel], submitting: bool
    ) -> list[FbAnswer]:
        questions = {question.question_id: question for page in version.pages for question in page.questions}
        rows = []
        for answer in answers:
            question = questions[answer.question_id]
            option = next((item for item in question.options if item.option_id == answer.option_id), None)
            rows.append(
                FbAnswer(
                    sheet_id=sheet.sheet_id,
                    version_id=version.version_id,
                    question_id=question.question_id,
                    answer_type='OPTION' if option else ('TEXT' if question.question_type == 'TEXT' else 'NUMERIC'),
                    option_id=answer.option_id,
                    numeric_value=answer.numeric_value,
                    text_value=answer.text_value,
                    reason=answer.reason,
                    raw_score=calculate_raw_score(question, answer) if submitting else None,
                    value_snapshot={
                        'questionCode': question.question_code,
                        'questionType': question.question_type,
                        'title': question.title,
                        'optionCode': option.option_code if option else None,
                        'optionLabel': option.option_label if option else None,
                    }
                    if submitting
                    else {},
                )
            )
        return rows

    @staticmethod
    def _finalize_submission(
        sheet: FbAnswerSheet,
        task: FbAssignment,
        version: FbQuestionnaireVersion,
        rows: list[FbAnswer],
        request: AnswerSubmitModel,
        fingerprint: str,
        now: datetime,
    ) -> None:
        sheet.status = 'SUBMITTED'
        sheet.submitted_time = now
        sheet.raw_total_score = sum((row.raw_score for row in rows if row.raw_score is not None), Decimal('0'))
        sheet.submission_snapshot = {
            'schemaVersion': 1,
            'submissionId': str(request.submission_id),
            'answerDigest': fingerprint,
            'versionId': task.version_id,
            'evaluatorUserId': task.evaluator_user_id,
            'targetUserId': task.target_user_id,
            'relationId': task.relation_id,
            'scoringRule': version.scoring_rule_snapshot,
            'questionScores': [
                {'questionId': row.question_id, 'rawScore': str(row.raw_score) if row.raw_score is not None else None}
                for row in rows
            ],
        }
        task.submitted_time = now

    @classmethod
    async def _write(
        cls,
        db: AsyncSession,
        assignment_id: int,
        evaluator_id: int,
        request: AnswerDraftSaveModel | AnswerSubmitModel,
        *,
        submitting: bool,
    ) -> EmployeeAnswerDetailModel:
        try:
            project, task = await FeedbackEmployeeDao.lock_context(db, assignment_id, evaluator_id)
            if project is None or task is None:
                raise HTTPException(status_code=404, detail='评价任务不存在或无权访问')
            if project.status != 'ACTIVE' or task.status == 'CLOSED_INCOMPLETE':
                raise ConflictException(
                    message='项目已结束或任务已关闭，不能继续作答',
                    data={'code': 'PROJECT_CLOSED', 'taskStatus': task.status},
                )
            if request.version_id != task.version_id:
                raise ConflictException(message='请求问卷版本与任务不一致')
            version = await FeedbackEmployeeDao.get_frozen_version(db, task.project_id, task.version_id)
            if version is None:
                raise ConflictException(message='任务绑定的冻结问卷不可用')
            sheet = await FeedbackAnswerDao.get_by_assignment_id_for_update(db, assignment_id)
            answers, issues = validate_answers(version, request, submitting=submitting)
            if issues:
                raise ConflictException(message='请检查答案后重试', data={'validationIssues': issues})
            fingerprint = cls._fingerprint(task.version_id, answers)
            if task.status == 'SUBMITTED' or (sheet and sheet.status == 'SUBMITTED'):
                snapshot = sheet.submission_snapshot if sheet else {}
                if (
                    submitting
                    and snapshot.get('submissionId') == str(request.submission_id)
                    and snapshot.get('answerDigest') == fingerprint
                ):
                    loaded = await FeedbackEmployeeDao.get_task(db, assignment_id, evaluator_id)
                    result = await FeedbackEmployeeService.detail_model(db, loaded)
                    result.already_submitted = True
                    await db.commit()
                    return result
                raise ConflictException(message='答卷已提交，不可修改', data={'taskStatus': 'SUBMITTED'})
            current_lock = sheet.lock_version if sheet else 0
            if current_lock != request.lock_version:
                raise ConflictException(
                    message='答卷已在其他页面保存，请重新加载后继续；当前输入尚未保存',
                    data={'code': 'ANSWER_VERSION_CONFLICT', 'lockVersion': current_lock},
                )
            now = datetime.now()
            if sheet is None:
                sheet = await FeedbackAnswerDao.add_answer_sheet(
                    db,
                    FbAnswerSheet(
                        assignment_id=assignment_id,
                        project_id=task.project_id,
                        version_id=task.version_id,
                        status='DRAFT',
                    ),
                )
            rows = cls._answer_rows(sheet, version, answers, submitting)
            await FeedbackAnswerDao.replace_draft_answers(db, sheet.sheet_id, rows)
            sheet.last_page_id = request.last_page_id
            sheet.answered_count = len(answers)
            sheet.saved_time = sheet.update_time = now
            sheet.lock_version += 1
            task.saved_time = task.update_time = now
            task.lock_version += 1
            target_status = 'SUBMITTED' if submitting else 'DRAFT'
            FeedbackStateTransitionService.ensure_assignment_transition(task.status, target_status)
            task.status = target_status
            if submitting:
                cls._finalize_submission(sheet, task, version, rows, request, fingerprint, now)
            await db.flush()
            loaded = await FeedbackEmployeeDao.get_task(db, assignment_id, evaluator_id)
            result = await FeedbackEmployeeService.detail_model(db, loaded)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise
