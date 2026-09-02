from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module_feedback.entity.do import FbAssignment
from module_feedback.enums import AssignmentStatus


class FeedbackAssignmentDao:
    """评价任务数据库访问。"""

    @classmethod
    async def add_assignments(cls, db: AsyncSession, assignments: Sequence[FbAssignment]) -> list[FbAssignment]:
        """批量新增任务并刷新主键，不提交事务。"""
        assignment_list = list(assignments)
        db.add_all(assignment_list)
        await db.flush()
        return assignment_list

    @classmethod
    async def get_assignment_by_id(cls, db: AsyncSession, assignment_id: int) -> FbAssignment | None:
        """读取任务及关系、被评价人快照和答卷。"""
        statement = (
            select(FbAssignment)
            .where(FbAssignment.assignment_id == assignment_id)
            .options(
                selectinload(FbAssignment.relation),
                selectinload(FbAssignment.target_snapshot),
                selectinload(FbAssignment.answer_sheet),
            )
        )
        return (await db.execute(statement)).scalars().first()

    @classmethod
    async def get_assignment_for_update(cls, db: AsyncSession, assignment_id: int) -> FbAssignment | None:
        """锁定任务主记录，由服务层在同一事务内暂存、提交或关闭。"""
        statement = select(FbAssignment).where(FbAssignment.assignment_id == assignment_id).with_for_update()
        return (await db.execute(statement)).scalars().first()

    @classmethod
    async def list_evaluator_assignments(
        cls,
        db: AsyncSession,
        evaluator_user_id: int,
        statuses: Sequence[AssignmentStatus | str] | None = None,
    ) -> list[FbAssignment]:
        """按登录评价人查询任务，调用方不得传入其他人的身份替代登录上下文。"""
        statement = select(FbAssignment).where(FbAssignment.evaluator_user_id == evaluator_user_id)
        if statuses:
            normalized_statuses = [AssignmentStatus(status).value for status in statuses]
            statement = statement.where(FbAssignment.status.in_(normalized_statuses))
        statement = statement.options(
            selectinload(FbAssignment.relation),
            selectinload(FbAssignment.target_snapshot),
        ).order_by(FbAssignment.project_id, FbAssignment.target_id, FbAssignment.assignment_id)
        return list((await db.execute(statement)).scalars().all())
