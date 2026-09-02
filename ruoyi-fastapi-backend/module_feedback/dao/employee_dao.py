from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module_feedback.entity.do import (
    FbAnswerSheet,
    FbAssignment,
    FbIndicator,
    FbProject,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
)
from module_feedback.entity.vo.employee_vo import EmployeePageQueryModel


class FeedbackEmployeeDao:
    """员工归属约束查询与写入锁；事务由服务层控制。"""

    @staticmethod
    def _task_options(*, answers: bool = False) -> tuple:
        options = (
            selectinload(FbAssignment.project),
            selectinload(FbAssignment.target_snapshot),
            selectinload(FbAssignment.relation),
        )
        if answers:
            return (*options, selectinload(FbAssignment.answer_sheet).selectinload(FbAnswerSheet.answers))
        return options

    @classmethod
    async def get_task(cls, db: AsyncSession, assignment_id: int, evaluator_id: int) -> FbAssignment | None:
        statement = (
            select(FbAssignment)
            .join(FbProject, FbProject.project_id == FbAssignment.project_id)
            .where(
                FbAssignment.assignment_id == assignment_id,
                FbAssignment.evaluator_user_id == evaluator_id,
                FbProject.del_flag == '0',
                FbProject.status.in_(['ACTIVE', 'COMPLETED']),
            )
            .options(*cls._task_options(answers=True))
            .execution_options(populate_existing=True)
        )
        return (await db.scalars(statement)).first()

    @classmethod
    async def list_project_tasks(cls, db: AsyncSession, project_id: int, evaluator_id: int) -> list[FbAssignment]:
        statement = (
            select(FbAssignment)
            .join(FbProject, FbProject.project_id == FbAssignment.project_id)
            .where(
                FbAssignment.project_id == project_id,
                FbAssignment.evaluator_user_id == evaluator_id,
                FbProject.del_flag == '0',
                FbProject.status.in_(['ACTIVE', 'COMPLETED']),
            )
            .options(*cls._task_options())
            .order_by(FbAssignment.target_id, FbAssignment.relation_id, FbAssignment.assignment_id)
        )
        return list((await db.scalars(statement)).all())

    @classmethod
    async def list_projects(cls, db: AsyncSession, evaluator_id: int, query: EmployeePageQueryModel) -> tuple:
        counts = (
            select(
                FbAssignment.project_id,
                func.count().label('total_count'),
                *[
                    func.count().filter(FbAssignment.status == status).label(label)
                    for status, label in (
                        ('PENDING', 'pending_count'),
                        ('DRAFT', 'draft_count'),
                        ('SUBMITTED', 'submitted_count'),
                        ('CLOSED_INCOMPLETE', 'closed_count'),
                    )
                ],
            )
            .where(FbAssignment.evaluator_user_id == evaluator_id)
            .group_by(FbAssignment.project_id)
            .subquery()
        )
        statement = (
            select(
                FbProject.project_id,
                FbProject.project_name,
                FbProject.status.label('project_status'),
                FbProject.published_time,
                counts.c.total_count,
                counts.c.pending_count,
                counts.c.draft_count,
                counts.c.submitted_count,
                counts.c.closed_count,
            )
            .join(counts, counts.c.project_id == FbProject.project_id)
            .where(
                FbProject.del_flag == '0',
                FbProject.status == 'ACTIVE',
                counts.c.pending_count + counts.c.draft_count > 0,
                FbProject.project_name.contains(query.keyword.strip(), autoescape=True),
            )
        )
        total = await db.scalar(select(func.count()).select_from(statement.subquery()))
        rows = await db.execute(
            statement.order_by(FbProject.published_time.desc(), FbProject.project_id.desc())
            .offset((query.page_num - 1) * query.page_size)
            .limit(query.page_size)
        )
        return rows.mappings().all(), total or 0

    @classmethod
    async def list_history(cls, db: AsyncSession, evaluator_id: int, query: EmployeePageQueryModel) -> tuple:
        statement = (
            select(FbAssignment)
            .join(FbProject, FbProject.project_id == FbAssignment.project_id)
            .where(
                FbAssignment.evaluator_user_id == evaluator_id,
                FbAssignment.status == 'SUBMITTED',
                FbProject.del_flag == '0',
                FbProject.project_name.contains(query.keyword.strip(), autoescape=True),
            )
        )
        total = await db.scalar(select(func.count()).select_from(statement.subquery()))
        rows = await db.scalars(
            statement.options(*cls._task_options())
            .order_by(FbAssignment.submitted_time.desc(), FbAssignment.assignment_id.desc())
            .offset((query.page_num - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(rows.all()), total or 0

    @classmethod
    async def get_frozen_version(
        cls, db: AsyncSession, project_id: int, version_id: int
    ) -> FbQuestionnaireVersion | None:
        statement = (
            select(FbQuestionnaireVersion)
            .where(
                FbQuestionnaireVersion.project_id == project_id,
                FbQuestionnaireVersion.version_id == version_id,
                FbQuestionnaireVersion.status == 'FROZEN',
            )
            .options(
                selectinload(FbQuestionnaireVersion.pages)
                .selectinload(FbQuestionnairePage.questions)
                .selectinload(FbQuestion.options),
                selectinload(FbQuestionnaireVersion.indicators).selectinload(FbIndicator.question_bindings),
            )
        )
        return (await db.scalars(statement)).first()

    @classmethod
    async def lock_context(cls, db: AsyncSession, assignment_id: int, evaluator_id: int) -> tuple:
        """先项目共享锁，再任务排他锁；与P7项目排他锁互斥。"""
        project_id = await db.scalar(
            select(FbAssignment.project_id).where(
                FbAssignment.assignment_id == assignment_id,
                FbAssignment.evaluator_user_id == evaluator_id,
            )
        )
        if project_id is None:
            return None, None
        project = await db.scalar(
            select(FbProject)
            .where(FbProject.project_id == project_id, FbProject.del_flag == '0')
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        task = await db.scalar(
            select(FbAssignment)
            .where(FbAssignment.assignment_id == assignment_id, FbAssignment.evaluator_user_id == evaluator_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return project, task
