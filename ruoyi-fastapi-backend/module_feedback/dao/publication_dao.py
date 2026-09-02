from collections.abc import Sequence

from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.user_do import SysUser
from module_feedback.entity.do import (
    FbAssignment,
    FbEvaluatorSelection,
    FbIndicator,
    FbProjectTarget,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
    FbRelation,
)
from module_feedback.entity.vo import ParticipantOptionQueryModel

ParticipantRow = tuple[SysUser, SysDept | None]
SelectionSpec = tuple[int, str, int]


class FeedbackPublicationDao:
    """发布配置、人员锁定和正式任务物化数据库访问。"""

    @staticmethod
    def _active_participant_filters(user_scope_sql: ColumnElement | None = None) -> list[ColumnElement]:
        filters: list[ColumnElement] = [
            SysUser.del_flag == '0',
            SysUser.status == '0',
            or_(
                SysUser.dept_id.is_(None),
                and_(SysDept.dept_id.is_not(None), SysDept.del_flag == '0', SysDept.status == '0'),
            ),
        ]
        if user_scope_sql is not None:
            filters.append(user_scope_sql)
        return filters

    @classmethod
    async def list_participant_options(
        cls,
        db: AsyncSession,
        query_object: ParticipantOptionQueryModel,
        user_scope_sql: ColumnElement,
    ) -> tuple[list[ParticipantRow], int]:
        """按RuoYi数据范围分页读取项目可用人员。"""
        filters = cls._active_participant_filters(user_scope_sql)
        if query_object.keyword:
            keyword = f'%{query_object.keyword}%'
            filters.append(or_(SysUser.user_name.ilike(keyword), SysUser.nick_name.ilike(keyword)))
        if query_object.dept_id:
            filters.append(SysUser.dept_id == query_object.dept_id)

        joined = select(SysUser.user_id).outerjoin(SysDept, SysDept.dept_id == SysUser.dept_id).where(*filters)
        total = int((await db.scalar(select(func.count()).select_from(joined.subquery()))) or 0)
        statement = (
            select(SysUser, SysDept)
            .outerjoin(SysDept, SysDept.dept_id == SysUser.dept_id)
            .where(*filters)
            .order_by(SysUser.nick_name, SysUser.user_id)
            .offset((query_object.page_num - 1) * query_object.page_size)
            .limit(query_object.page_size)
        )
        return [(row[0], row[1]) for row in (await db.execute(statement)).all()], total

    @classmethod
    async def get_available_participants(
        cls,
        db: AsyncSession,
        user_ids: set[int],
        user_scope_sql: ColumnElement,
        *,
        lock: bool = False,
    ) -> dict[int, ParticipantRow]:
        """读取并可按固定顺序共享锁定全部有效参与人及部门。"""
        if not user_ids:
            return {}
        user_statement = (
            select(SysUser)
            .where(
                SysUser.user_id.in_(sorted(user_ids)),
                SysUser.del_flag == '0',
                SysUser.status == '0',
                user_scope_sql,
            )
            .order_by(SysUser.user_id)
        )
        if lock:
            user_statement = user_statement.with_for_update(read=True, of=SysUser)
        users = list((await db.execute(user_statement)).scalars().all())
        dept_ids = sorted({int(user.dept_id) for user in users if user.dept_id is not None})
        departments: dict[int, SysDept] = {}
        if dept_ids:
            dept_statement = (
                select(SysDept)
                .where(SysDept.dept_id.in_(dept_ids), SysDept.del_flag == '0', SysDept.status == '0')
                .order_by(SysDept.dept_id)
            )
            if lock:
                dept_statement = dept_statement.with_for_update(read=True, of=SysDept)
            departments = {item.dept_id: item for item in (await db.execute(dept_statement)).scalars().all()}

        return {
            int(user.user_id): (user, departments.get(int(user.dept_id)) if user.dept_id is not None else None)
            for user in users
            if user.dept_id is None or int(user.dept_id) in departments
        }

    @classmethod
    async def get_participant_display_rows(cls, db: AsyncSession, user_ids: set[int]) -> dict[int, ParticipantRow]:
        """读取配置中已引用人员的当前展示信息，不扩大候选人员范围。"""
        if not user_ids:
            return {}
        statement = (
            select(SysUser, SysDept)
            .outerjoin(SysDept, SysDept.dept_id == SysUser.dept_id)
            .where(SysUser.user_id.in_(sorted(user_ids)))
            .order_by(SysUser.user_id)
        )
        return {int(row[0].user_id): (row[0], row[1]) for row in (await db.execute(statement)).all()}

    @classmethod
    async def get_version_document(
        cls,
        db: AsyncSession,
        project_id: int,
        version_id: int,
        *,
        lock: bool = False,
    ) -> FbQuestionnaireVersion | None:
        """读取问卷完整文档和关系；发布时锁定版本主记录。"""
        statement = (
            select(FbQuestionnaireVersion)
            .where(
                FbQuestionnaireVersion.project_id == project_id,
                FbQuestionnaireVersion.version_id == version_id,
            )
            .options(
                selectinload(FbQuestionnaireVersion.pages)
                .selectinload(FbQuestionnairePage.questions)
                .selectinload(FbQuestion.options),
                selectinload(FbQuestionnaireVersion.indicators).selectinload(FbIndicator.question_bindings),
                selectinload(FbQuestionnaireVersion.relations),
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return (await db.execute(statement)).scalars().unique().first()

    @classmethod
    async def list_targets(
        cls,
        db: AsyncSession,
        project_id: int,
        version_id: int,
    ) -> list[FbProjectTarget]:
        statement = (
            select(FbProjectTarget)
            .where(FbProjectTarget.project_id == project_id, FbProjectTarget.version_id == version_id)
            .order_by(FbProjectTarget.target_id)
        )
        return list((await db.execute(statement)).scalars().all())

    @classmethod
    async def list_selections(
        cls,
        db: AsyncSession,
        project_id: int,
        version_id: int,
    ) -> list[FbEvaluatorSelection]:
        statement = (
            select(FbEvaluatorSelection)
            .where(
                FbEvaluatorSelection.project_id == project_id,
                FbEvaluatorSelection.version_id == version_id,
            )
            .order_by(
                FbEvaluatorSelection.target_id,
                FbEvaluatorSelection.relation_id,
                FbEvaluatorSelection.evaluator_user_id,
            )
        )
        return list((await db.execute(statement)).scalars().all())

    @classmethod
    async def list_assignments(
        cls,
        db: AsyncSession,
        project_id: int,
        version_id: int,
    ) -> list[FbAssignment]:
        statement = (
            select(FbAssignment)
            .where(FbAssignment.project_id == project_id, FbAssignment.version_id == version_id)
            .order_by(FbAssignment.target_id, FbAssignment.relation_id, FbAssignment.evaluator_user_id)
        )
        return list((await db.execute(statement)).scalars().all())

    @classmethod
    async def replace_configuration(
        cls,
        db: AsyncSession,
        project_id: int,
        version_id: int,
        relations: Sequence[FbRelation],
        targets: Sequence[FbProjectTarget],
        selection_specs: Sequence[SelectionSpec],
        operator_name: str,
    ) -> tuple[list[FbRelation], list[FbProjectTarget], list[FbEvaluatorSelection]]:
        """整体替换关系、目标和选择配置，不提交事务。"""
        await db.execute(
            delete(FbEvaluatorSelection).where(
                FbEvaluatorSelection.project_id == project_id,
                FbEvaluatorSelection.version_id == version_id,
            )
        )
        await db.execute(
            delete(FbProjectTarget).where(
                FbProjectTarget.project_id == project_id,
                FbProjectTarget.version_id == version_id,
            )
        )
        await db.execute(
            delete(FbRelation).where(FbRelation.project_id == project_id, FbRelation.version_id == version_id)
        )
        await db.flush()

        relation_list = list(relations)
        target_list = list(targets)
        db.add_all(relation_list)
        db.add_all(target_list)
        await db.flush()
        relation_by_code = {item.relation_code: item for item in relation_list}
        target_by_user_id = {int(item.target_user_id): item for item in target_list}
        selections = [
            FbEvaluatorSelection(
                project_id=project_id,
                version_id=version_id,
                target_id=target_by_user_id[target_user_id].target_id,
                target_user_id=target_user_id,
                relation_id=relation_by_code[relation_code].relation_id,
                evaluator_user_id=evaluator_user_id,
                create_by=operator_name,
                update_by=operator_name,
            )
            for target_user_id, relation_code, evaluator_user_id in selection_specs
        ]
        db.add_all(selections)
        await db.flush()
        return relation_list, target_list, selections

    @classmethod
    async def add_assignments(
        cls,
        db: AsyncSession,
        assignments: Sequence[FbAssignment],
    ) -> list[FbAssignment]:
        assignment_list = list(assignments)
        db.add_all(assignment_list)
        await db.flush()
        return assignment_list
