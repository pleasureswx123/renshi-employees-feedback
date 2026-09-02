from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from module_feedback.entity.do import FbScoreResult


class FeedbackScoreResultDao:
    """计分结果数据库访问。"""

    @classmethod
    async def add_result(cls, db: AsyncSession, result: FbScoreResult) -> FbScoreResult:
        """新增一条可追溯计分结果，不提交事务。"""
        db.add(result)
        await db.flush()
        return result

    @classmethod
    async def list_target_results(cls, db: AsyncSession, project_id: int, target_user_id: int) -> list[FbScoreResult]:
        """读取指定项目和被评价人的全部计分粒度结果。"""
        statement = (
            select(FbScoreResult)
            .where(
                FbScoreResult.project_id == project_id,
                FbScoreResult.target_user_id == target_user_id,
            )
            .order_by(FbScoreResult.result_type, FbScoreResult.indicator_id, FbScoreResult.relation_id)
        )
        return list((await db.execute(statement)).scalars().all())
