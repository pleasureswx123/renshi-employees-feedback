from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module_feedback.entity.do import FbAnswer, FbAnswerSheet


class FeedbackAnswerDao:
    """答卷及答案数据库访问。"""

    @classmethod
    async def add_answer_sheet(cls, db: AsyncSession, answer_sheet: FbAnswerSheet) -> FbAnswerSheet:
        """新增答卷并刷新主键，不提交事务。"""
        db.add(answer_sheet)
        await db.flush()
        return answer_sheet

    @classmethod
    async def get_by_assignment_id(cls, db: AsyncSession, assignment_id: int) -> FbAnswerSheet | None:
        """读取任务答卷及其全部答案。"""
        statement = (
            select(FbAnswerSheet)
            .where(FbAnswerSheet.assignment_id == assignment_id)
            .options(selectinload(FbAnswerSheet.answers))
        )
        return (await db.execute(statement)).scalars().first()

    @classmethod
    async def get_by_assignment_id_for_update(cls, db: AsyncSession, assignment_id: int) -> FbAnswerSheet | None:
        """锁定答卷主记录，答案写入与任务状态由服务层统一提交。"""
        statement = (
            select(FbAnswerSheet)
            .where(FbAnswerSheet.assignment_id == assignment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await db.execute(statement)).scalars().first()

    @classmethod
    async def replace_draft_answers(cls, db: AsyncSession, sheet_id: int, answers: list[FbAnswer]) -> None:
        """调用方必须锁定未提交答卷；仅替换可编辑草稿，不提交事务。"""
        sheet = await db.get(FbAnswerSheet, sheet_id)
        if sheet is None or sheet.status != 'DRAFT':
            raise ValueError('正式答卷不可覆盖')
        await db.execute(delete(FbAnswer).where(FbAnswer.sheet_id == sheet_id))
        db.add_all(answers)
        await db.flush()
