from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, and_, any_, bindparam, case, func, select
from sqlalchemy.dialects.postgresql import ARRAY

from module_feedback.entity.do import (
    FbAssignment,
    FbProject,
    FbProjectCompletionAudit,
    FbProjectTarget,
    FbRelation,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql import Select

    from module_feedback.entity.vo.progress_vo import ProgressQueryModel


@dataclass
class ProgressAssignmentRecord:
    assignment_id: int
    evaluator_user_id: int
    evaluator_user_name: str
    evaluator_dept_name: str | None
    target_user_id: int
    target_id: int
    target_user_name: str
    target_dept_id: int | None
    target_dept_name: str | None
    relation_id: int
    relation_code: str
    relation_name: str
    relation_sort_order: int
    status: str
    saved_time: datetime | None
    submitted_time: datetime | None
    closed_time: datetime | None


class FeedbackProgressDao:
    @staticmethod
    def _bigint_array_filter(column: Any, values: tuple[int, ...] | set[int], parameter_name: str) -> Any:
        """用单个PostgreSQL数组参数承载大范围ID，避开asyncpg参数硬上限。"""

        return column == any_(
            bindparam(
                parameter_name,
                value=list(values),
                type_=ARRAY(BigInteger()),
            )
        )

    @staticmethod
    async def add_completion_audit(db: AsyncSession, audit: FbProjectCompletionAudit) -> FbProjectCompletionAudit:
        db.add(audit)
        return audit

    @staticmethod
    async def get_project_scoped(
        db: AsyncSession,
        project_id: int,
        project_scope_sql: Any,
        *,
        for_update: bool = False,
        for_share: bool = False,
    ) -> FbProject | None:
        if for_update and for_share:
            raise ValueError('项目锁不能同时使用FOR UPDATE和FOR SHARE')
        statement = select(FbProject).where(
            FbProject.project_id == project_id, FbProject.del_flag == '0', project_scope_sql
        )
        if for_update:
            statement = statement.with_for_update()
        elif for_share:
            statement = statement.with_for_update(read=True)
        return (await db.execute(statement)).scalars().first()

    @staticmethod
    async def get_visible_target_ids(
        db: AsyncSession, project_id: int, version_id: int, target_scope_sql: Any
    ) -> tuple[set[int], int]:
        all_ids = set(
            (
                await db.scalars(
                    select(FbProjectTarget.target_id).where(
                        FbProjectTarget.project_id == project_id, FbProjectTarget.version_id == version_id
                    )
                )
            ).all()
        )
        visible = set(
            (
                await db.scalars(
                    select(FbProjectTarget.target_id).where(
                        FbProjectTarget.project_id == project_id,
                        FbProjectTarget.version_id == version_id,
                        target_scope_sql,
                    )
                )
            ).all()
        )
        return visible, len(all_ids)

    @staticmethod
    async def lock_visible_assignments_for_share(
        db: AsyncSession, project_id: int, version_id: int, visible_target_ids: set[int]
    ) -> tuple[int, ...]:
        if not visible_target_ids:
            return ()
        statement = (
            select(FbAssignment.assignment_id)
            .where(
                FbAssignment.project_id == project_id,
                FbAssignment.version_id == version_id,
                FeedbackProgressDao._bigint_array_filter(
                    FbAssignment.target_id,
                    visible_target_ids,
                    'visible_target_ids',
                ),
            )
            .order_by(FbAssignment.assignment_id)
            .with_for_update(read=True, of=FbAssignment)
            .execution_options(populate_existing=True)
        )
        return tuple((await db.scalars(statement)).all())

    @staticmethod
    def _base(project_id: int, version_id: int, assignment_ids: tuple[int, ...]) -> Select:
        return (
            select(
                FbAssignment.assignment_id,
                FbAssignment.evaluator_user_id,
                FbAssignment.evaluator_user_name,
                FbAssignment.evaluator_dept_name,
                FbAssignment.target_user_id,
                FbAssignment.target_id,
                FbProjectTarget.target_user_name,
                FbProjectTarget.target_dept_id,
                FbProjectTarget.target_dept_name,
                FbAssignment.relation_id,
                FbRelation.relation_code,
                FbRelation.relation_name,
                FbRelation.sort_order.label('relation_sort_order'),
                FbAssignment.status,
                FbAssignment.saved_time,
                FbAssignment.submitted_time,
                FbAssignment.closed_time,
            )
            .join(
                FbProjectTarget,
                and_(
                    FbProjectTarget.project_id == FbAssignment.project_id,
                    FbProjectTarget.version_id == FbAssignment.version_id,
                    FbProjectTarget.target_id == FbAssignment.target_id,
                ),
            )
            .join(
                FbRelation,
                and_(
                    FbRelation.project_id == FbAssignment.project_id,
                    FbRelation.version_id == FbAssignment.version_id,
                    FbRelation.relation_id == FbAssignment.relation_id,
                ),
            )
            .where(
                FbAssignment.project_id == project_id,
                FbAssignment.version_id == version_id,
                FeedbackProgressDao._bigint_array_filter(
                    FbAssignment.assignment_id,
                    assignment_ids,
                    'visible_assignment_ids',
                ),
            )
        )

    @classmethod
    async def list_assignments(
        cls,
        db: AsyncSession,
        project_id: int,
        version_id: int,
        assignment_ids: tuple[int, ...],
        query: ProgressQueryModel,
    ) -> tuple[list[ProgressAssignmentRecord], int]:
        if not assignment_ids:
            return [], 0
        statement = cls._base(project_id, version_id, assignment_ids)
        if query.evaluator_user_id is not None:
            statement = statement.where(FbAssignment.evaluator_user_id == query.evaluator_user_id)
        if query.target_user_id is not None:
            statement = statement.where(FbAssignment.target_user_id == query.target_user_id)
        if query.relation_id is not None:
            statement = statement.where(FbAssignment.relation_id == query.relation_id)
        if query.status is not None:
            statement = statement.where(FbAssignment.status == query.status.value)
        if query.evaluator_keyword:
            statement = statement.where(
                FbAssignment.evaluator_user_name.icontains(query.evaluator_keyword, autoescape=True)
            )
        if query.target_keyword:
            statement = statement.where(
                FbProjectTarget.target_user_name.icontains(query.target_keyword, autoescape=True)
            )
        total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        status_order = case(
            {'DRAFT': 1, 'PENDING': 2, 'SUBMITTED': 3, 'CLOSED_INCOMPLETE': 4}, value=FbAssignment.status, else_=5
        )
        statement = statement.order_by(
            status_order,
            FbProjectTarget.target_user_name,
            FbAssignment.evaluator_user_name,
            FbRelation.sort_order,
            FbAssignment.assignment_id,
        )
        if query.page_size:
            statement = statement.offset((query.page_num - 1) * query.page_size).limit(query.page_size)
        return [ProgressAssignmentRecord(**dict(row._mapping)) for row in (await db.execute(statement)).all()], total

    @classmethod
    async def list_all_assignments(
        cls, db: AsyncSession, project_id: int, version_id: int, assignment_ids: tuple[int, ...]
    ) -> list[ProgressAssignmentRecord]:
        if not assignment_ids:
            return []
        statement = cls._base(project_id, version_id, assignment_ids).order_by(
            FbProjectTarget.target_user_name, FbRelation.sort_order, FbRelation.relation_id, FbAssignment.assignment_id
        )
        return [ProgressAssignmentRecord(**dict(row._mapping)) for row in (await db.execute(statement)).all()]

    @staticmethod
    async def summarize_assignments(
        db: AsyncSession, project_id: int, version_id: int, assignment_ids: tuple[int, ...]
    ) -> dict[str, int]:
        if not assignment_ids:
            return {}
        statement = (
            select(FbAssignment.status, func.count())
            .where(
                FbAssignment.project_id == project_id,
                FbAssignment.version_id == version_id,
                FeedbackProgressDao._bigint_array_filter(
                    FbAssignment.assignment_id,
                    assignment_ids,
                    'visible_assignment_ids',
                ),
            )
            .group_by(FbAssignment.status)
        )
        return {str(row[0]): int(row[1]) for row in (await db.execute(statement)).all()}

    @staticmethod
    async def list_relation_options(
        db: AsyncSession, project_id: int, version_id: int, assignment_ids: tuple[int, ...]
    ) -> list[tuple[int, str, str, int]]:
        if not assignment_ids:
            return []
        statement = (
            select(FbRelation.relation_id, FbRelation.relation_code, FbRelation.relation_name, FbRelation.sort_order)
            .join(
                FbAssignment,
                and_(
                    FbAssignment.project_id == FbRelation.project_id,
                    FbAssignment.version_id == FbRelation.version_id,
                    FbAssignment.relation_id == FbRelation.relation_id,
                ),
            )
            .where(
                FbAssignment.project_id == project_id,
                FbAssignment.version_id == version_id,
                FeedbackProgressDao._bigint_array_filter(
                    FbAssignment.assignment_id,
                    assignment_ids,
                    'visible_assignment_ids',
                ),
            )
            .distinct()
            .order_by(FbRelation.sort_order, FbRelation.relation_id)
        )
        return [tuple(row) for row in (await db.execute(statement)).all()]

    @staticmethod
    async def relation_belongs_to_version(db: AsyncSession, project_id: int, version_id: int, relation_id: int) -> bool:
        statement = select(FbRelation.relation_id).where(
            FbRelation.project_id == project_id,
            FbRelation.version_id == version_id,
            FbRelation.relation_id == relation_id,
        )
        return await db.scalar(statement) is not None

    @staticmethod
    async def lock_assignments(db: AsyncSession, project_id: int, version_id: int) -> list[FbAssignment]:
        statement = (
            select(FbAssignment)
            .where(FbAssignment.project_id == project_id, FbAssignment.version_id == version_id)
            .order_by(FbAssignment.assignment_id)
            .with_for_update()
        )
        return list((await db.execute(statement)).scalars().all())
