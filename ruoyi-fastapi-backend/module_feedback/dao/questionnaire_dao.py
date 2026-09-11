from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module_feedback.entity.do import (
    FbIndicator,
    FbIndicatorQuestion,
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
                .selectinload(FbQuestion.options),
                selectinload(FbQuestionnaireVersion.indicators).selectinload(FbIndicator.question_bindings),
            )
        )
        row = (await db.execute(statement)).unique().first()
        if row is None:
            return None
        return row[0], row[1]

    @classmethod
    async def get_source_by_project_id(
        cls,
        db: AsyncSession,
        project_id: int,
        data_scope_sql: ColumnElement,
    ) -> tuple[FbProject, FbQuestionnaireVersion] | None:
        """按数据范围读取历史来源；已发布项目只读取冻结版本。"""
        statement = (
            select(FbProject, FbQuestionnaireVersion)
            .join(FbQuestionnaireVersion, FbQuestionnaireVersion.project_id == FbProject.project_id)
            .where(
                FbProject.project_id == project_id,
                FbProject.del_flag == '0',
                (
                    (FbProject.status == 'PREPARING')
                    & (FbQuestionnaireVersion.status == QuestionnaireVersionStatus.DRAFT.value)
                )
                | (
                    (FbProject.status != 'PREPARING')
                    & (FbQuestionnaireVersion.version_id == FbProject.current_questionnaire_version_id)
                ),
                data_scope_sql,
            )
            .options(
                selectinload(FbQuestionnaireVersion.pages)
                .selectinload(FbQuestionnairePage.questions)
                .selectinload(FbQuestion.options),
                selectinload(FbQuestionnaireVersion.indicators).selectinload(FbIndicator.question_bindings),
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
    async def replace_draft_document(
        cls,
        db: AsyncSession,
        version_id: int,
        pages: list[FbQuestionnairePage],
        indicators: list[FbIndicator],
        indicator_bindings: dict[str, list[str]],
    ) -> None:
        """整体替换页面、题目、指标和绑定，不提交事务。"""
        await db.execute(delete(FbQuestionnairePage).where(FbQuestionnairePage.version_id == version_id))
        await db.execute(delete(FbIndicator).where(FbIndicator.version_id == version_id))
        await db.flush()
        db.add_all(pages)
        await db.flush()

        question_ids = {question.question_code: question.question_id for page in pages for question in page.questions}
        db.add_all(indicators)
        await db.flush()
        indicator_ids = {indicator.indicator_code: indicator.indicator_id for indicator in indicators}

        bindings: list[FbIndicatorQuestion] = []
        for indicator_code, question_codes in indicator_bindings.items():
            indicator_id = indicator_ids.get(indicator_code)
            if indicator_id is None:
                raise ValueError(f'找不到指标标识：{indicator_code}')
            for question_code in question_codes:
                question_id = question_ids.get(question_code)
                if question_id is None:
                    raise ValueError(f'找不到题目标识：{question_code}')
                bindings.append(
                    FbIndicatorQuestion(
                        version_id=version_id,
                        indicator_id=indicator_id,
                        question_id=question_id,
                    )
                )
        db.add_all(bindings)
        await db.flush()
