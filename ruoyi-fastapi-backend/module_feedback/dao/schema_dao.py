from typing import Any

from sqlalchemy import text


class FeedbackSchemaDao:
    @staticmethod
    async def migration_revisions(db: Any) -> list[str]:
        """读取实际迁移标记，缺少版本表时返回空列表，不执行运行时建表。"""
        if not await db.scalar(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")):
            return []
        return list(await db.scalars(text('SELECT version_num FROM alembic_version')))
