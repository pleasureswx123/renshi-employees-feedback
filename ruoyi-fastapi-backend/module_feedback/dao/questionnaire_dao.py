from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module_feedback.entity.do import (
    FbProject,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
)
from module_feedback.enums import QuestionnaireVersionStatus


class FeedbackQuestionnaireDao:
    """问卷草稿数据库访问。"""

    @classmethod
    async def get_draft_by_project_id(
        cls,
        db: AsyncSession,
        project_id: int,
        data_scope_sql: ColumnElement,
    ) -> tuple[FbProject, FbQuestionnaireVersion] | None:
        """按数据范围读取项目及其唯一草稿版本完整文档。"""
        statement = (
            select(FbProject, FbQuestionnaireVersion)
            .join(FbQuestionnaireVersion, FbQuestionnaireVersion.project_id == FbProject.project_id)
            .where(
                FbProject.project_id == project_id,
                FbProject.del_flag == '0',
                FbQuestionnaireVersion.status == QuestionnaireVersionStatus.DRAFT.value,
                data_scope_sql,
            )
            .options(
                selectinload(FbQuestionnaireVersion.pages)
                .selectinload(FbQuestionnairePage.questions)
                .selectinload(FbQuestion.options)
            )
        )
        row = (await db.execute(statement)).unique().first()
        if row is None:
            return None
        return row[0], row[1]

    @classmethod
    async def get_draft_for_update(
        cls,
        db: AsyncSession,
        project_id: int,
        version_id: int,
    ) -> FbQuestionnaireVersion | None:
        """锁定指定项目的草稿版本。"""
        statement = (
            select(FbQuestionnaireVersion)
            .where(
                FbQuestionnaireVersion.project_id == project_id,
                FbQuestionnaireVersion.version_id == version_id,
                FbQuestionnaireVersion.status == QuestionnaireVersionStatus.DRAFT.value,
            )
            .with_for_update()
        )
        return (await db.execute(statement)).scalars().first()

    @classmethod
    async def replace_draft_pages(
        cls,
        db: AsyncSession,
        version_id: int,
        pages: list[FbQuestionnairePage],
    ) -> None:
        """删除旧草稿页面并写入新文档，不提交事务。"""
        await db.execute(delete(FbQuestionnairePage).where(FbQuestionnairePage.version_id == version_id))
        await db.flush()
        db.add_all(pages)
        await db.flush()
