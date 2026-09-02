from collections import Counter

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from exceptions.exception import ConflictException
from module_feedback.dao.employee_dao import FeedbackEmployeeDao
from module_feedback.entity.do import FbAssignment
from module_feedback.entity.vo.employee_vo import (
    AnswerValueModel,
    EmployeeAnswerDetailModel,
    EmployeePageQueryModel,
    EmployeeProjectDetailModel,
    EmployeeProjectModel,
    EmployeeQuestionnaireModel,
    EmployeeTaskModel,
)
from module_feedback.service.questionnaire_service import FeedbackQuestionnaireService


class FeedbackEmployeeService:
    """当前登录评价人的待办、冻结问卷与只读历史。"""

    @staticmethod
    def task_model(task: FbAssignment) -> EmployeeTaskModel:
        return EmployeeTaskModel(
            assignmentId=task.assignment_id,
            projectId=task.project_id,
            projectName=task.project.project_name,
            projectStatus=task.project.status,
            versionId=task.version_id,
            targetUserId=task.target_user_id,
            targetName=task.target_snapshot.target_user_name,
            targetDeptName=task.target_snapshot.target_dept_name,
            relationId=task.relation_id,
            relationName=task.relation.relation_name,
            status=task.status,
            savedTime=task.saved_time,
            submittedTime=task.submitted_time,
        )

    @classmethod
    async def list_projects(
        cls, db: AsyncSession, evaluator_id: int, query: EmployeePageQueryModel
    ) -> PageModel[EmployeeProjectModel]:
        rows, total = await FeedbackEmployeeDao.list_projects(db, evaluator_id, query)
        return PageModel[EmployeeProjectModel](
            rows=[EmployeeProjectModel.model_validate(row) for row in rows],
            total=total,
            pageNum=query.page_num,
            pageSize=query.page_size,
            hasNext=query.page_num * query.page_size < total,
        )

    @classmethod
    async def get_project(cls, db: AsyncSession, project_id: int, evaluator_id: int) -> EmployeeProjectDetailModel:
        tasks = await FeedbackEmployeeDao.list_project_tasks(db, project_id, evaluator_id)
        if not tasks:
            raise HTTPException(status_code=404, detail='项目不存在或没有分配给你的评价任务')
        project = tasks[0].project
        counts = Counter(task.status for task in tasks)
        return EmployeeProjectDetailModel(
            projectId=project_id,
            projectName=project.project_name,
            projectStatus=project.status,
            publishedTime=project.published_time,
            totalCount=len(tasks),
            pendingCount=counts['PENDING'],
            draftCount=counts['DRAFT'],
            submittedCount=counts['SUBMITTED'],
            closedCount=counts['CLOSED_INCOMPLETE'],
            tasks=[cls.task_model(task) for task in tasks],
        )

    @classmethod
    async def list_history(
        cls, db: AsyncSession, evaluator_id: int, query: EmployeePageQueryModel
    ) -> PageModel[EmployeeTaskModel]:
        tasks, total = await FeedbackEmployeeDao.list_history(db, evaluator_id, query)
        return PageModel[EmployeeTaskModel](
            rows=[cls.task_model(task) for task in tasks],
            total=total,
            pageNum=query.page_num,
            pageSize=query.page_size,
            hasNext=query.page_num * query.page_size < total,
        )

    @classmethod
    async def get_task(
        cls, db: AsyncSession, assignment_id: int, evaluator_id: int, *, history: bool = False
    ) -> EmployeeAnswerDetailModel:
        task = await FeedbackEmployeeDao.get_task(db, assignment_id, evaluator_id)
        if task is None or (history and task.status != 'SUBMITTED'):
            raise HTTPException(status_code=404, detail='评价记录不存在或无权访问')
        if not history and task.status == 'SUBMITTED':
            raise ConflictException(
                message='该任务已提交，请从“我评价的”查看只读答案', data={'taskStatus': task.status}
            )
        return await cls.detail_model(db, task)

    @classmethod
    async def detail_model(cls, db: AsyncSession, task: FbAssignment) -> EmployeeAnswerDetailModel:
        """仅对已完成归属校验的任务构建详情。"""
        version = await FeedbackEmployeeDao.get_frozen_version(db, task.project_id, task.version_id)
        if version is None:
            raise ConflictException(message='任务绑定的冻结问卷不可用')
        document = FeedbackQuestionnaireService._document_payload(version)
        questionnaire = EmployeeQuestionnaireModel(
            **{key: document[key] for key in ('versionId', 'title', 'description', 'descriptionDoc', 'pages')}
        )
        sheet = task.answer_sheet
        return EmployeeAnswerDetailModel(
            task=cls.task_model(task),
            questionnaire=questionnaire,
            sheetId=sheet.sheet_id if sheet else None,
            lockVersion=sheet.lock_version if sheet else 0,
            lastPageId=sheet.last_page_id if sheet and sheet.last_page_id else version.pages[0].page_id,
            answeredCount=sheet.answered_count if sheet else 0,
            answers=[AnswerValueModel.model_validate(item) for item in sheet.answers] if sheet else [],
            editable=task.project.status == 'ACTIVE' and task.status in ('PENDING', 'DRAFT'),
        )
