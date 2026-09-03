from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import selectinload

from module_feedback.dao.progress_dao import FeedbackProgressDao
from module_feedback.entity.do import (
    FbAnswer,
    FbAnswerSheet,
    FbAssignment,
    FbProject,
    FbProjectTarget,
    FbScoreResult,
)

SCORING_PRECISION_COLUMN_COUNT = 2


class FeedbackReportDao:
    """报告查询始终先限定项目、冻结版本和可见被评价人。"""

    @staticmethod
    async def scoring_precision_ready(db: Any) -> bool:
        """兼容后续迁移版本，但拒绝旧表在写入时悄悄截断正式结果。"""
        count = await db.scalar(
            text(
                'SELECT count(*) FROM information_schema.columns '
                "WHERE table_schema = current_schema() AND table_name = 'fb_score_result' "
                "AND column_name IN ('score', 'effective_weight') AND data_type = 'numeric' "
                'AND numeric_precision IS NULL AND numeric_scale IS NULL'
            )
        )
        return count == SCORING_PRECISION_COLUMN_COUNT

    @staticmethod
    async def list_projects(db: Any, query: Any, project_scope: Any, target_scope: Any) -> tuple:
        visible = (
            select(FbProjectTarget.target_id)
            .where(
                FbProjectTarget.project_id == FbProject.project_id,
                FbProjectTarget.version_id == FbProject.current_questionnaire_version_id,
                target_scope,
            )
            .exists()
        )
        stmt = select(FbProject).where(
            FbProject.del_flag == '0',
            FbProject.status == 'COMPLETED',
            project_scope,
            visible,
            FbProject.project_name.icontains(query.keyword.strip(), autoescape=True),
        )
        total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await db.scalars(
            stmt.order_by(FbProject.completed_time.desc(), FbProject.project_id.desc())
            .offset((query.page_num - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(rows), total or 0

    @staticmethod
    async def targets(db: Any, project_id: int, version_id: int, scope: Any) -> list:
        return list(
            await db.scalars(
                select(FbProjectTarget)
                .where(
                    FbProjectTarget.project_id == project_id,
                    FbProjectTarget.version_id == version_id,
                    scope,
                )
                .order_by(FbProjectTarget.target_id)
            )
        )

    @staticmethod
    def _target_filter(column: Any, target_ids: set[int]) -> Any:
        return FeedbackProgressDao._bigint_array_filter(column, target_ids, 'report_target_ids')

    @classmethod
    async def tasks(cls, db: Any, project_id: int, version_id: int, target_ids: set[int]) -> list:
        return list(
            await db.scalars(
                select(FbAssignment)
                .where(
                    FbAssignment.project_id == project_id,
                    FbAssignment.version_id == version_id,
                    cls._target_filter(FbAssignment.target_id, target_ids),
                )
                .order_by(FbAssignment.assignment_id)
            )
        )

    @classmethod
    async def submitted_inputs(cls, db: Any, project_id: int, version_id: int, target_ids: set[int]) -> tuple:
        """计算不读取文本、附加原因或草稿；只查询已提交的数值事实和提交依据。"""
        sheets_stmt = (
            select(FbAnswerSheet)
            .join(FbAssignment, FbAssignment.assignment_id == FbAnswerSheet.assignment_id)
            .where(
                FbAssignment.project_id == project_id,
                FbAssignment.version_id == version_id,
                cls._target_filter(FbAssignment.target_id, target_ids),
                FbAssignment.status == 'SUBMITTED',
                FbAnswerSheet.status == 'SUBMITTED',
                FbAnswerSheet.project_id == project_id,
                FbAnswerSheet.version_id == version_id,
            )
        )
        sheets = list(await db.scalars(sheets_stmt))
        sheet_ids = sheets_stmt.with_only_columns(FbAnswerSheet.sheet_id)
        answers = list(
            (
                await db.execute(
                    select(
                        FbAnswer.sheet_id,
                        FbAnswer.question_id,
                        FbAnswer.raw_score,
                        FbAnswer.option_id,
                        FbAnswer.numeric_value,
                    ).where(FbAnswer.sheet_id.in_(sheet_ids), FbAnswer.version_id == version_id)
                )
            ).all()
        )
        return sheets, answers

    @classmethod
    async def result_keys(cls, db: Any, project_id: int, version_id: int, target_ids: set[int]) -> list:
        return list(
            (
                await db.execute(
                    select(
                        FbScoreResult.target_id,
                        FbScoreResult.result_type,
                        FbScoreResult.indicator_id,
                        FbScoreResult.relation_id,
                        FbScoreResult.calculation_version,
                    ).where(
                        FbScoreResult.project_id == project_id,
                        FbScoreResult.version_id == version_id,
                        cls._target_filter(FbScoreResult.target_id, target_ids),
                    )
                )
            ).all()
        )

    @staticmethod
    async def add_results(db: Any, rows: list[FbScoreResult]) -> None:
        db.add_all(rows)
        await db.flush()

    @classmethod
    async def team_rows(cls, db: Any, project_id: int, version_id: int, target_ids: set[int], query: Any) -> tuple:
        ranked = (
            select(
                FbScoreResult.score,
                FbScoreResult.calculation_basis['report'].op('-')('questions').label('report'),
                FbProjectTarget.target_user_id,
                FbProjectTarget.target_user_name,
                FbProjectTarget.target_dept_name,
                func.rank().over(order_by=FbScoreResult.score.desc().nulls_last()).label('rank'),
            )
            .join(FbProjectTarget, FbProjectTarget.target_id == FbScoreResult.target_id)
            .where(
                FbScoreResult.project_id == project_id,
                FbScoreResult.version_id == version_id,
                FbScoreResult.result_type == 'PERSON_TOTAL',
                cls._target_filter(FbScoreResult.target_id, target_ids),
            )
            .subquery()
        )
        stmt = select(ranked).where(ranked.c.target_user_name.icontains(query.keyword.strip(), autoescape=True))
        total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await db.execute(
            stmt.order_by(ranked.c.score.desc().nulls_last(), ranked.c.target_user_id)
            .offset((query.page_num - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(rows.mappings()), total or 0

    @staticmethod
    async def personal_result(db: Any, project_id: int, version_id: int, target_id: int) -> FbScoreResult | None:
        return await db.scalar(
            select(FbScoreResult).where(
                FbScoreResult.project_id == project_id,
                FbScoreResult.version_id == version_id,
                FbScoreResult.target_id == target_id,
                FbScoreResult.result_type == 'PERSON_TOTAL',
            )
        )

    @classmethod
    def _submitted_tasks(cls, project_id: int, version_id: int, target_ids: set[int]) -> Any:
        return (
            select(FbAssignment)
            .join(
                FbAnswerSheet,
                and_(FbAnswerSheet.assignment_id == FbAssignment.assignment_id, FbAnswerSheet.status == 'SUBMITTED'),
            )
            .where(
                FbAssignment.project_id == project_id,
                FbAssignment.version_id == version_id,
                FbAssignment.status == 'SUBMITTED',
                cls._target_filter(FbAssignment.target_id, target_ids),
            )
        )

    @classmethod
    async def submitted_tasks(
        cls, db: Any, project_id: int, version_id: int, target_ids: set[int], query: Any
    ) -> tuple:
        stmt = (
            cls._submitted_tasks(project_id, version_id, target_ids)
            .join(
                FbProjectTarget,
                FbProjectTarget.target_id == FbAssignment.target_id,
            )
            .where(FbProjectTarget.target_user_name.icontains(query.keyword.strip(), autoescape=True))
        )
        if query.target_user_id:
            stmt = stmt.where(FbAssignment.target_user_id == query.target_user_id)
        total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await db.scalars(
            stmt.options(
                selectinload(FbAssignment.target_snapshot),
                selectinload(FbAssignment.relation),
            )
            .order_by(FbAssignment.target_user_id, FbAssignment.relation_id, FbAssignment.assignment_id)
            .offset((query.page_num - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(rows), total or 0

    @classmethod
    async def submitted_task(
        cls, db: Any, project_id: int, version_id: int, target_ids: set[int], assignment_id: int
    ) -> Any:
        return await db.scalar(
            cls._submitted_tasks(project_id, version_id, target_ids)
            .where(
                FbAssignment.assignment_id == assignment_id,
            )
            .options(
                selectinload(FbAssignment.target_snapshot),
                selectinload(FbAssignment.relation),
                selectinload(FbAssignment.answer_sheet).selectinload(FbAnswerSheet.answers),
            )
        )
