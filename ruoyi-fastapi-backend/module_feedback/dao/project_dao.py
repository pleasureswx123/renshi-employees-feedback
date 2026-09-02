from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module_feedback.entity.do import (
    FbIndicator,
    FbProject,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
)


class FeedbackProjectDao:
    """评价项目及问卷骨架数据库访问。"""

    @classmethod
    async def add_project(cls, db: AsyncSession, project: FbProject) -> FbProject:
        """新增项目并刷新数据库生成的主键，不提交事务。"""
        db.add(project)
        await db.flush()
        return project

    @classmethod
    async def add_questionnaire_version(
        cls, db: AsyncSession, questionnaire_version: FbQuestionnaireVersion
    ) -> FbQuestionnaireVersion:
        """新增问卷版本，不提交事务。"""
        db.add(questionnaire_version)
        await db.flush()
        return questionnaire_version

    @classmethod
    async def get_project_by_id(cls, db: AsyncSession, project_id: int) -> FbProject | None:
        """读取项目、问卷结构和被评价人快照。"""
        statement = (
            select(FbProject)
            .where(FbProject.project_id == project_id, FbProject.del_flag == '0')
            .options(
                selectinload(FbProject.questionnaire_versions)
                .selectinload(FbQuestionnaireVersion.pages)
                .selectinload(FbQuestionnairePage.questions)
                .selectinload(FbQuestion.options),
                selectinload(FbProject.questionnaire_versions)
                .selectinload(FbQuestionnaireVersion.indicators)
                .selectinload(FbIndicator.question_bindings),
                selectinload(FbProject.questionnaire_versions).selectinload(FbQuestionnaireVersion.relations),
                selectinload(FbProject.targets),
            )
        )
        return (await db.execute(statement)).scalars().unique().first()

    @classmethod
    async def get_project_for_update(cls, db: AsyncSession, project_id: int) -> FbProject | None:
        """锁定项目主记录，由服务层在同一事务内完成状态变更。"""
        statement = (
            select(FbProject).where(FbProject.project_id == project_id, FbProject.del_flag == '0').with_for_update()
        )
        return (await db.execute(statement)).scalars().first()
