from typing import Any

from fastapi import HTTPException

from module_feedback.dao.report_dao import FeedbackReportDao
from module_feedback.dao.schema_dao import FeedbackSchemaDao

FEEDBACK_SCHEMA_REVISION = '20260903_08_feedback_scoring'


class FeedbackSchemaService:
    """只读检查迁移版本和正式得分精度，不在运行时创建或修改业务表。"""

    @staticmethod
    async def health(db: Any) -> dict[str, str]:
        migrated = await FeedbackSchemaDao.migration_revisions(db) == [FEEDBACK_SCHEMA_REVISION]
        if not migrated or not await FeedbackReportDao.scoring_precision_ready(db):
            raise HTTPException(
                status_code=503,
                detail={'code': 'FEEDBACK_SCHEMA_NOT_READY', 'message': '评价数据库尚未完成迁移，请联系管理员'},
            )
        return {
            'module': 'feedback',
            'status': 'ready',
            'phase': 'P9',
            'apiPrefix': '/feedback',
            'schemaRevision': FEEDBACK_SCHEMA_REVISION,
        }
