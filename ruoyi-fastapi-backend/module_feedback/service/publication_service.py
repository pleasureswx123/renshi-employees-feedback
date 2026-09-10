import math
from collections import defaultdict
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from exceptions.exception import ConflictException, ServiceException
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.user_do import SysUser
from module_feedback.constants import BUILTIN_ADMIN_USER_ID, FIXED_RELATION_CODES, SELF_RELATION_CODE
from module_feedback.dao import FeedbackProjectDao, FeedbackPublicationDao
from module_feedback.entity.do import (
    FbAssignment,
    FbEvaluatorSelection,
    FbProject,
    FbProjectTarget,
    FbQuestionnaireVersion,
    FbRelation,
)
from module_feedback.entity.vo import (
    EvaluatorSelectionModel,
    ParticipantOptionModel,
    ParticipantOptionQueryModel,
    PublicationConfigModel,
    PublicationConfigSaveModel,
    PublicationPreviewModel,
    PublicationRelationModel,
    PublicationTargetModel,
    PublicationTargetPreviewModel,
    PublishRequestModel,
    PublishResultModel,
    QuestionnaireDraftSaveModel,
    ValidationIssueModel,
)
from module_feedback.enums import AssignmentStatus, ProjectStatus, QuestionnaireVersionStatus
from module_feedback.service.questionnaire_service import FeedbackQuestionnaireService
from module_feedback.validators import get_publication_validation_issues

ParticipantRow = tuple[SysUser, SysDept | None]


class FeedbackPublicationService:
    """人员配置、发布校验、冻结和任务生成应用服务。"""

    @staticmethod
    def _is_available(row: ParticipantRow | None) -> bool:
        if row is None:
            return False
        user, dept = row
        return bool(
            user.user_id != BUILTIN_ADMIN_USER_ID
            and user.del_flag == '0'
            and user.status == '0'
            and (user.dept_id is None or (dept is not None and dept.del_flag == '0' and dept.status == '0'))
        )

    @staticmethod
    def _system_account_issues(target_ids: set[int], evaluator_ids: set[int]) -> list[dict[str, str]]:
        """只限制参评身份，保留内置账号作为项目管理者和历史审计操作人的能力。"""
        if BUILTIN_ADMIN_USER_ID not in target_ids | evaluator_ids:
            return []
        return [
            {
                'code': 'SYSTEM_ACCOUNT_NOT_ALLOWED',
                'path': 'targets' if BUILTIN_ADMIN_USER_ID in target_ids else 'evaluatorSelections',
                'message': '系统维护账号不能参与评价，请移除后继续',
            }
        ]

    @classmethod
    def _participant_option(
        cls,
        row: ParticipantRow | None,
        user_id: int,
        *,
        snapshot_name: str | None = None,
        snapshot_dept_id: int | None = None,
        snapshot_dept_name: str | None = None,
    ) -> ParticipantOptionModel:
        user, dept = row if row is not None else (None, None)
        return ParticipantOptionModel(
            userId=user_id,
            userName=user.user_name if user is not None else None,
            nickName=snapshot_name or (user.nick_name if user is not None else f'用户{user_id}'),
            deptId=snapshot_dept_id if snapshot_name is not None else (user.dept_id if user is not None else None),
            deptName=(
                snapshot_dept_name if snapshot_name is not None else (dept.dept_name if dept is not None else None)
            ),
            available=cls._is_available(row),
        )

    @classmethod
    async def list_participant_options(
        cls,
        query_db: AsyncSession,
        project_id: int,
        query_object: ParticipantOptionQueryModel,
        project_scope_sql: ColumnElement,
        user_scope_sql: ColumnElement,
    ) -> PageModel[ParticipantOptionModel]:
        project = await FeedbackProjectDao.get_project_by_id_scoped(query_db, project_id, project_scope_sql)
        if project is None:
            raise ServiceException(message='项目不存在或不在当前数据范围内')
        rows, total = await FeedbackPublicationDao.list_participant_options(query_db, query_object, user_scope_sql)
        return PageModel[ParticipantOptionModel](
            rows=[cls._participant_option(row, int(row[0].user_id)) for row in rows],
            pageNum=query_object.page_num,
            pageSize=query_object.page_size,
            total=total,
            hasNext=math.ceil(total / query_object.page_size) > query_object.page_num,
        )

    @classmethod
    async def list_participant_departments(
        cls,
        query_db: AsyncSession,
        project_id: int,
        project_scope_sql: ColumnElement,
        user_scope_sql: ColumnElement,
    ) -> list[dict[str, int | str | None]]:
        """仅返回可选员工所在部门及必要祖先，不暴露其他部门的人员数量。"""
        project = await FeedbackProjectDao.get_project_by_id_scoped(query_db, project_id, project_scope_sql)
        if project is None:
            raise ServiceException(message='项目不存在或不在当前数据范围内')
        counts, departments = await FeedbackPublicationDao.participant_department_counts(query_db, user_scope_sql)
        by_id = {int(dept.dept_id): dept for dept in departments}
        visible = set()
        for dept_id in counts:
            current = dept_id
            while current in by_id and current not in visible:
                visible.add(current)
                current = by_id[current].parent_id
        result = [
            {
                'deptId': int(dept.dept_id),
                'parentId': int(dept.parent_id) if dept.parent_id in visible else 0,
                'label': dept.dept_name,
                'directCount': int(counts.get(dept.dept_id, 0)),
            }
            for dept in departments
            if dept.dept_id in visible
        ]
        if counts.get(None):
            result.append({'deptId': 0, 'parentId': None, 'label': '未分配部门', 'directCount': int(counts[None])})
        return result

    @staticmethod
    def _version_id_for_project(project: FbProject) -> int:
        if project.status == ProjectStatus.PREPARING.value:
            draft_ids = [
                int(version.version_id)
                for version in project.questionnaire_versions
                if version.status == QuestionnaireVersionStatus.DRAFT.value
            ]
            if len(draft_ids) != 1:
                raise ServiceException(message='项目草稿版本缺失或不唯一')
            return draft_ids[0]
        if project.current_questionnaire_version_id is None:
            raise ServiceException(message='已发布项目缺少冻结问卷版本')
        return int(project.current_questionnaire_version_id)

    @staticmethod
    def _questionnaire_model(version: FbQuestionnaireVersion) -> QuestionnaireDraftSaveModel:
        return QuestionnaireDraftSaveModel.model_validate(FeedbackQuestionnaireService._document_payload(version))

    @staticmethod
    def _preview(
        targets: list[FbProjectTarget],
        relations: list[FbRelation],
        selections: list[FbEvaluatorSelection],
    ) -> PublicationPreviewModel:
        relation_by_id = {item.relation_id: item for item in relations}
        summaries: list[PublicationTargetPreviewModel] = []
        for target in targets:
            target_selections = [item for item in selections if item.target_id == target.target_id]
            self_count = sum(
                1
                for item in target_selections
                if relation_by_id.get(item.relation_id) is not None
                and relation_by_id[item.relation_id].relation_code == SELF_RELATION_CODE
            )
            summaries.append(
                PublicationTargetPreviewModel(
                    targetUserId=target.target_user_id,
                    selfCount=self_count,
                    nonSelfCount=len(target_selections) - self_count,
                    assignmentCount=len(target_selections),
                )
            )
        return PublicationPreviewModel(
            targetCount=len(targets),
            assignmentCount=len(selections),
            evaluatorCount=len({item.evaluator_user_id for item in selections}),
            targetSummaries=summaries,
        )

    @classmethod
    async def _to_config_model(
        cls,
        query_db: AsyncSession,
        project: FbProject,
        version: FbQuestionnaireVersion,
        targets: list[FbProjectTarget],
        selections: list[FbEvaluatorSelection],
        assignments: list[FbAssignment],
    ) -> PublicationConfigModel:
        relations = sorted(version.relations, key=lambda item: (item.sort_order, item.relation_code))
        relation_by_id = {item.relation_id: item for item in relations}
        target_order = {item.target_user_id: index for index, item in enumerate(targets)}
        relation_order = {item.relation_code: index for index, item in enumerate(relations)}
        grouped: dict[tuple[int, str], list[int]] = defaultdict(list)
        for item in selections:
            relation = relation_by_id.get(item.relation_id)
            if relation is not None:
                grouped[(item.target_user_id, relation.relation_code)].append(item.evaluator_user_id)
        selection_models = [
            EvaluatorSelectionModel(
                targetUserId=target_user_id,
                relationCode=relation_code,
                evaluatorUserIds=sorted(evaluator_ids),
                systemManaged=relation_code == SELF_RELATION_CODE,
            )
            for (target_user_id, relation_code), evaluator_ids in sorted(
                grouped.items(),
                key=lambda item: (
                    target_order.get(item[0][0], 10**9),
                    relation_order.get(item[0][1], 10**9),
                ),
            )
        ]

        configured_user_ids = {item.target_user_id for item in targets} | {
            item.evaluator_user_id for item in selections
        }
        display_user_ids = configured_user_ids | ({int(project.published_by)} if project.published_by else set())
        display_rows = await FeedbackPublicationDao.get_participant_display_rows(query_db, display_user_ids)
        snapshot_by_user_id: dict[int, tuple[str, int | None, str | None]] = {
            int(target.target_user_id): (
                target.target_user_name,
                target.target_dept_id,
                target.target_dept_name,
            )
            for target in targets
        }
        if project.status != ProjectStatus.PREPARING.value:
            for assignment in assignments:
                snapshot_by_user_id.setdefault(
                    int(assignment.evaluator_user_id),
                    (
                        assignment.evaluator_user_name,
                        assignment.evaluator_dept_id,
                        assignment.evaluator_dept_name,
                    ),
                )

        configured_participants = []
        for user_id in sorted(configured_user_ids):
            snapshot = snapshot_by_user_id.get(int(user_id))
            configured_participants.append(
                cls._participant_option(
                    display_rows.get(int(user_id)),
                    int(user_id),
                    snapshot_name=snapshot[0] if snapshot else None,
                    snapshot_dept_id=snapshot[1] if snapshot else None,
                    snapshot_dept_name=snapshot[2] if snapshot else None,
                )
            )

        target_models = []
        for target in targets:
            current_row = display_rows.get(int(target.target_user_id))
            target_models.append(
                PublicationTargetModel(
                    **cls._participant_option(
                        current_row,
                        int(target.target_user_id),
                        snapshot_name=target.target_user_name,
                        snapshot_dept_id=target.target_dept_id,
                        snapshot_dept_name=target.target_dept_name,
                    ).model_dump(),
                    targetId=target.target_id,
                    onlySelfEvaluation=target.only_self_evaluation,
                )
            )

        questionnaire = cls._questionnaire_model(version)
        issue_payloads = get_publication_validation_issues(questionnaire, targets, relations, selections)
        if project.status == ProjectStatus.PREPARING.value:
            issue_payloads.extend(
                cls._system_account_issues(
                    {item.target_user_id for item in targets}, {item.evaluator_user_id for item in selections}
                )
            )
        return PublicationConfigModel(
            projectId=project.project_id,
            projectName=project.project_name,
            projectStatus=project.status,
            projectLockVersion=project.lock_version,
            versionId=version.version_id,
            versionLockVersion=version.lock_version,
            versionStatus=version.status,
            editable=project.status == ProjectStatus.PREPARING.value
            and version.status == QuestionnaireVersionStatus.DRAFT.value,
            targets=target_models,
            relations=[
                PublicationRelationModel(
                    relationId=item.relation_id,
                    relationCode=item.relation_code,
                    relationType=item.relation_type,
                    relationName=item.relation_name,
                    isEnabled=item.is_enabled,
                    participatesInScore=item.participates_in_score,
                    weight=item.weight,
                    sortOrder=item.sort_order,
                    fixed=item.relation_code in FIXED_RELATION_CODES,
                )
                for item in relations
            ],
            evaluatorSelections=selection_models,
            configuredParticipants=configured_participants,
            preview=cls._preview(targets, relations, selections),
            isPublishReady=not issue_payloads,
            validationIssues=[ValidationIssueModel.model_validate(item) for item in issue_payloads],
            frozenDetails=(
                {
                    'publishedBy': project.published_by,
                    'publishedByName': (
                        display_rows[int(project.published_by)][0].user_name
                        if int(project.published_by) in display_rows
                        else f'用户{project.published_by}'
                    ),
                    'publishedTime': project.published_time,
                    'versionNo': version.version_no,
                    'questionnaire': questionnaire,
                }
                if project.status != ProjectStatus.PREPARING.value
                else None
            ),
        )

    @classmethod
    async def get_config(
        cls,
        query_db: AsyncSession,
        project_id: int,
        project_scope_sql: ColumnElement,
    ) -> PublicationConfigModel:
        project = await FeedbackProjectDao.get_project_by_id_scoped(query_db, project_id, project_scope_sql)
        if project is None:
            raise ServiceException(message='项目不存在或不在当前数据范围内')
        version_id = cls._version_id_for_project(project)
        version = await FeedbackPublicationDao.get_version_document(query_db, project_id, version_id)
        if version is None:
            raise ServiceException(message='项目问卷版本不存在')
        targets = await FeedbackPublicationDao.list_targets(query_db, project_id, version_id)
        selections = await FeedbackPublicationDao.list_selections(query_db, project_id, version_id)
        assignments = await FeedbackPublicationDao.list_assignments(query_db, project_id, version_id)
        return await cls._to_config_model(query_db, project, version, targets, selections, assignments)

    @staticmethod
    def _build_relations(
        page_object: PublicationConfigSaveModel,
        project_id: int,
        operator_name: str,
    ) -> list[FbRelation]:
        return [
            FbRelation(
                project_id=project_id,
                version_id=page_object.version_id,
                relation_code=item.relation_code,
                relation_type=item.relation_type.value,
                relation_name=item.relation_name,
                is_enabled=item.is_enabled,
                participates_in_score=item.participates_in_score,
                weight=item.weight,
                sort_order=item.sort_order,
                create_by=operator_name,
                update_by=operator_name,
            )
            for item in page_object.relations
        ]

    @staticmethod
    def _selection_specs(page_object: PublicationConfigSaveModel) -> list[tuple[int, str, int]]:
        specs = [(target.target_user_id, SELF_RELATION_CODE, target.target_user_id) for target in page_object.targets]
        specs.extend(
            (selection.target_user_id, selection.relation_code, evaluator_user_id)
            for selection in page_object.evaluator_selections
            for evaluator_user_id in selection.evaluator_user_ids
        )
        return sorted(specs, key=lambda item: (item[0], item[1], item[2]))

    @classmethod
    async def save_config(
        cls,
        query_db: AsyncSession,
        project_id: int,
        page_object: PublicationConfigSaveModel,
        operator_name: str,
        project_scope_sql: ColumnElement,
        user_scope_sql: ColumnElement,
    ) -> PublicationConfigModel:
        try:
            project = await FeedbackProjectDao.get_project_for_update_scoped(query_db, project_id, project_scope_sql)
            if project is None:
                raise ServiceException(message='项目不存在或不在当前数据范围内')
            if project.status != ProjectStatus.PREPARING.value:
                raise ConflictException(message='项目已经发布，不能修改人员与关系配置')
            if project.lock_version != page_object.project_lock_version:
                raise ConflictException(message='项目已被其他用户修改，请刷新后重试')

            version = await FeedbackPublicationDao.get_version_document(
                query_db,
                project_id,
                page_object.version_id,
                lock=True,
            )
            if version is None or version.status != QuestionnaireVersionStatus.DRAFT.value:
                raise ConflictException(message='问卷草稿版本不存在或已经冻结')
            if version.lock_version != page_object.version_lock_version:
                raise ConflictException(message='问卷或发布配置已被其他用户修改，请刷新后重试')

            selection_specs = cls._selection_specs(page_object)
            participant_ids = {item.target_user_id for item in page_object.targets} | {
                evaluator_user_id for _, _, evaluator_user_id in selection_specs
            }
            system_account_issues = cls._system_account_issues(
                {item.target_user_id for item in page_object.targets},
                {evaluator_user_id for _, _, evaluator_user_id in selection_specs},
            )
            if system_account_issues:
                raise ConflictException(
                    message=system_account_issues[0]['message'],
                    data={
                        'unavailableUserIds': [BUILTIN_ADMIN_USER_ID],
                        'validationIssues': system_account_issues,
                    },
                )
            participants = await FeedbackPublicationDao.get_available_participants(
                query_db,
                participant_ids,
                user_scope_sql,
            )
            unavailable_ids = sorted(participant_ids - participants.keys())
            if unavailable_ids:
                raise ConflictException(
                    message='参与人员已失效或不在当前数据范围内',
                    data={'unavailableUserIds': unavailable_ids},
                )

            non_self_by_target = dict.fromkeys(participant_ids, False)
            for target_user_id, relation_code, _ in selection_specs:
                if relation_code != SELF_RELATION_CODE:
                    non_self_by_target[target_user_id] = True
            targets = [
                FbProjectTarget(
                    project_id=project_id,
                    version_id=page_object.version_id,
                    target_user_id=item.target_user_id,
                    target_user_name=participants[item.target_user_id][0].nick_name,
                    target_dept_id=participants[item.target_user_id][0].dept_id,
                    target_dept_name=(
                        participants[item.target_user_id][1].dept_name
                        if participants[item.target_user_id][1] is not None
                        else None
                    ),
                    only_self_evaluation=not non_self_by_target[item.target_user_id],
                    create_by=operator_name,
                    update_by=operator_name,
                )
                for item in page_object.targets
            ]
            relations = cls._build_relations(page_object, project_id, operator_name)
            await FeedbackPublicationDao.replace_configuration(
                query_db,
                project_id,
                page_object.version_id,
                relations,
                targets,
                selection_specs,
                operator_name,
            )
            now = datetime.now()
            version.update_by = operator_name
            version.update_time = now
            version.lock_version += 1
            project.update_by = operator_name
            project.update_time = now
            project.lock_version += 1
            await query_db.commit()
            return await cls.get_config(query_db, project_id, project_scope_sql)
        except IntegrityError as exc:
            await query_db.rollback()
            raise ConflictException(message='发布配置包含重复或跨项目引用，请刷新后重试') from exc
        except Exception:
            await query_db.rollback()
            raise

    @staticmethod
    def _scoring_snapshot(version: FbQuestionnaireVersion, relations: list[FbRelation]) -> dict[str, object]:
        return {
            'schemaVersion': 1,
            'calculationVersion': 'feedback-score-v1',
            'scoreScale': '100.0000',
            'decimalPlaces': 4,
            'missingRelationPolicy': 'RENORMALIZE_SUBMITTED_NON_SELF',
            'selfPolicy': {
                'relationCode': SELF_RELATION_CODE,
                'weightWhenNonSelfExists': '0.0000',
                'effectiveWeightWhenOnlySelf': '100.0000',
            },
            'indicatorWeights': [
                {
                    'indicatorCode': item.indicator_code,
                    'indicatorName': item.indicator_name,
                    'weight': f'{item.weight:.4f}',
                }
                for item in sorted(version.indicators, key=lambda row: (row.sort_order, row.indicator_code))
            ],
            'relationWeights': [
                {
                    'relationCode': item.relation_code,
                    'relationType': item.relation_type,
                    'relationName': item.relation_name,
                    'isEnabled': item.is_enabled,
                    'participatesInScore': item.participates_in_score,
                    'weight': f'{item.weight:.4f}',
                }
                for item in sorted(relations, key=lambda row: (row.sort_order, row.relation_code))
            ],
        }

    @staticmethod
    def _assert_idempotent_integrity(
        selections: list[FbEvaluatorSelection],
        assignments: list[FbAssignment],
    ) -> None:
        selection_keys = {(item.evaluator_user_id, item.target_user_id, item.relation_id) for item in selections}
        assignment_keys = {(item.evaluator_user_id, item.target_user_id, item.relation_id) for item in assignments}
        if selection_keys != assignment_keys or len(selections) != len(assignments):
            raise ConflictException(message='已发布项目的冻结选择与正式任务不一致，不能按幂等成功处理')

    @staticmethod
    def _publish_result(
        project: FbProject,
        version: FbQuestionnaireVersion,
        targets: list[FbProjectTarget],
        assignments: list[FbAssignment],
        *,
        already_published: bool,
    ) -> PublishResultModel:
        if project.published_by is None or project.published_time is None:
            raise ConflictException(message='已发布项目缺少发布审计信息')
        return PublishResultModel(
            projectId=project.project_id,
            projectStatus=project.status,
            versionId=version.version_id,
            versionStatus=version.status,
            publishedBy=project.published_by,
            publishedTime=project.published_time,
            targetCount=len(targets),
            assignmentCount=len(assignments),
            evaluatorCount=len({item.evaluator_user_id for item in assignments}),
            alreadyPublished=already_published,
        )

    @classmethod
    async def _idempotent_publish_result(
        cls,
        query_db: AsyncSession,
        project: FbProject,
        version_id: int,
    ) -> PublishResultModel:
        if project.current_questionnaire_version_id != version_id:
            raise ConflictException(message='项目已经发布到其他问卷版本')
        version = await FeedbackPublicationDao.get_version_document(query_db, project.project_id, version_id)
        if version is None or version.status != QuestionnaireVersionStatus.FROZEN.value:
            raise ConflictException(message='已发布项目的问卷冻结状态异常')
        targets = await FeedbackPublicationDao.list_targets(query_db, project.project_id, version.version_id)
        selections = await FeedbackPublicationDao.list_selections(query_db, project.project_id, version.version_id)
        assignments = await FeedbackPublicationDao.list_assignments(query_db, project.project_id, version.version_id)
        cls._assert_idempotent_integrity(selections, assignments)
        result = cls._publish_result(project, version, targets, assignments, already_published=True)
        await query_db.commit()
        return result

    @classmethod
    async def _load_publish_configuration(
        cls,
        query_db: AsyncSession,
        project: FbProject,
        page_object: PublishRequestModel,
        user_scope_sql: ColumnElement,
    ) -> tuple[
        FbQuestionnaireVersion,
        list[FbProjectTarget],
        list[FbRelation],
        list[FbEvaluatorSelection],
        dict[int, ParticipantRow],
    ]:
        version = await FeedbackPublicationDao.get_version_document(
            query_db,
            project.project_id,
            page_object.version_id,
            lock=True,
        )
        if version is None or version.status != QuestionnaireVersionStatus.DRAFT.value:
            raise ConflictException(message='问卷草稿版本不存在或已经冻结')
        if version.lock_version != page_object.version_lock_version:
            raise ConflictException(message='问卷或发布配置已被其他用户修改，请刷新后重试')
        targets = await FeedbackPublicationDao.list_targets(query_db, project.project_id, version.version_id)
        selections = await FeedbackPublicationDao.list_selections(query_db, project.project_id, version.version_id)
        existing_assignments = await FeedbackPublicationDao.list_assignments(
            query_db, project.project_id, version.version_id
        )
        if existing_assignments:
            raise ConflictException(message='准备阶段项目已经存在正式任务，拒绝继续发布')

        participant_ids = {item.target_user_id for item in targets} | {item.evaluator_user_id for item in selections}
        system_account_issues = cls._system_account_issues(
            {item.target_user_id for item in targets}, {item.evaluator_user_id for item in selections}
        )
        if system_account_issues:
            raise ConflictException(
                message=system_account_issues[0]['message'],
                data={'validationIssues': system_account_issues},
            )
        participants = await FeedbackPublicationDao.get_available_participants(
            query_db,
            participant_ids,
            user_scope_sql,
            lock=True,
        )
        unavailable_target_ids = {item.target_user_id for item in targets if item.target_user_id not in participants}
        unavailable_evaluator_ids = {
            item.evaluator_user_id for item in selections if item.evaluator_user_id not in participants
        }
        relations = sorted(version.relations, key=lambda item: (item.sort_order, item.relation_code))
        issue_payloads = get_publication_validation_issues(
            cls._questionnaire_model(version),
            targets,
            relations,
            selections,
            unavailable_target_ids,
            unavailable_evaluator_ids,
        )
        if issue_payloads:
            raise ConflictException(
                message='发布前检查未通过',
                data={'validationIssues': issue_payloads},
            )
        return version, targets, relations, selections, participants

    @staticmethod
    def _refresh_targets_and_build_assignments(
        project_id: int,
        version_id: int,
        targets: list[FbProjectTarget],
        relations: list[FbRelation],
        selections: list[FbEvaluatorSelection],
        participants: dict[int, ParticipantRow],
        operator_name: str,
    ) -> list[FbAssignment]:
        relation_by_id = {item.relation_id: item for item in relations}
        target_by_id = {item.target_id: item for item in targets}
        non_self_target_ids = {
            item.target_id
            for item in selections
            if relation_by_id[item.relation_id].relation_code != SELF_RELATION_CODE
        }
        now = datetime.now()
        for target in targets:
            user, dept = participants[int(target.target_user_id)]
            target.target_user_name = user.nick_name
            target.target_dept_id = user.dept_id
            target.target_dept_name = dept.dept_name if dept is not None else None
            target.only_self_evaluation = target.target_id not in non_self_target_ids
            target.update_by = operator_name
            target.update_time = now

        return [
            FbAssignment(
                project_id=project_id,
                version_id=version_id,
                evaluator_user_id=selection.evaluator_user_id,
                evaluator_user_name=participants[int(selection.evaluator_user_id)][0].nick_name,
                evaluator_dept_id=participants[int(selection.evaluator_user_id)][0].dept_id,
                evaluator_dept_name=(
                    participants[int(selection.evaluator_user_id)][1].dept_name
                    if participants[int(selection.evaluator_user_id)][1] is not None
                    else None
                ),
                target_id=selection.target_id,
                target_user_id=selection.target_user_id,
                relation_id=selection.relation_id,
                status=AssignmentStatus.PENDING.value,
            )
            for selection in sorted(
                selections,
                key=lambda item: (
                    target_by_id[item.target_id].target_user_id,
                    relation_by_id[item.relation_id].sort_order,
                    item.evaluator_user_id,
                ),
            )
        ]

    @classmethod
    def _freeze_project(
        cls,
        project: FbProject,
        version: FbQuestionnaireVersion,
        relations: list[FbRelation],
        publisher_user_id: int,
        operator_name: str,
    ) -> None:
        now = datetime.now()
        version.scoring_rule_snapshot = cls._scoring_snapshot(version, relations)
        version.status = QuestionnaireVersionStatus.FROZEN.value
        version.frozen_by = publisher_user_id
        version.frozen_time = now
        version.update_by = operator_name
        version.update_time = now
        version.lock_version += 1
        project.status = ProjectStatus.ACTIVE.value
        project.current_questionnaire_version_id = version.version_id
        project.published_by = publisher_user_id
        project.published_time = now
        project.update_by = operator_name
        project.update_time = now
        project.lock_version += 1

    @classmethod
    async def publish(
        cls,
        query_db: AsyncSession,
        project_id: int,
        page_object: PublishRequestModel,
        publisher_user_id: int,
        operator_name: str,
        project_scope_sql: ColumnElement,
        user_scope_sql: ColumnElement,
    ) -> PublishResultModel:
        try:
            project = await FeedbackProjectDao.get_project_for_update_scoped(query_db, project_id, project_scope_sql)
            if project is None:
                raise ServiceException(message='项目不存在或不在当前数据范围内')

            if project.status == ProjectStatus.ACTIVE.value:
                return await cls._idempotent_publish_result(query_db, project, page_object.version_id)
            if project.status != ProjectStatus.PREPARING.value:
                raise ConflictException(message='只有准备阶段项目允许发布')
            if project.lock_version != page_object.project_lock_version:
                raise ConflictException(message='项目已被其他用户修改，请刷新后重试')

            version, targets, relations, selections, participants = await cls._load_publish_configuration(
                query_db,
                project,
                page_object,
                user_scope_sql,
            )
            assignments = cls._refresh_targets_and_build_assignments(
                project_id,
                version.version_id,
                targets,
                relations,
                selections,
                participants,
                operator_name,
            )
            await FeedbackPublicationDao.add_assignments(query_db, assignments)
            cls._freeze_project(project, version, relations, publisher_user_id, operator_name)
            await query_db.commit()
            return cls._publish_result(project, version, targets, assignments, already_published=False)
        except IntegrityError as exc:
            await query_db.rollback()
            raise ConflictException(message='发布任务与现有数据冲突，请刷新后重试') from exc
        except Exception:
            await query_db.rollback()
            raise
