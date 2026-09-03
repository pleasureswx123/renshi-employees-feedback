from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from module_feedback.dao.progress_dao import FeedbackProgressDao
from module_feedback.entity.do import FbProjectCompletionAudit
from module_feedback.entity.vo.progress_vo import (
    CompletionPrecheckModel,
    MissingRelationModel,
    ProgressFilterOptionsModel,
    ProgressPageModel,
    ProgressQueryModel,
    ProgressRelationOptionModel,
    ProgressRowModel,
    ProgressSummaryModel,
    ProjectCompleteRequestModel,
    ProjectCompleteResultModel,
)
from module_feedback.enums import AssignmentStatus, ProjectStatus
from module_feedback.service.state_transition_service import FeedbackStateTransitionService


class ProjectCompletionExecutionError(RuntimeError):
    """完成事务的未知失败；只向上层暴露稳定问题码和失败阶段。"""

    problem_code = 'PROJECT_COMPLETION_FAILED'

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__('项目完成事务执行失败')


class FeedbackProgressService:
    @staticmethod
    def _problem(status_code: int, code: str, message: str, **data: Any) -> HTTPException:
        return HTTPException(
            status_code=status_code,
            detail={'code': code, 'message': message, **data},
        )

    @staticmethod
    def _summary(rows: list[Any]) -> ProgressSummaryModel:
        counts = dict.fromkeys(('PENDING', 'DRAFT', 'SUBMITTED', 'CLOSED_INCOMPLETE'), 0)
        for row in rows:
            if row.status not in counts:
                raise RuntimeError('任务状态统计不一致')
            counts[row.status] += 1
        return ProgressSummaryModel.from_counts(**counts)

    @staticmethod
    def _row(item: Any) -> ProgressRowModel:
        return ProgressRowModel(
            assignmentId=item.assignment_id,
            evaluatorUserId=item.evaluator_user_id,
            evaluatorName=item.evaluator_user_name,
            evaluatorDeptName=item.evaluator_dept_name,
            targetUserId=item.target_user_id,
            targetName=item.target_user_name,
            targetDeptId=item.target_dept_id,
            targetDeptName=item.target_dept_name,
            relationId=item.relation_id,
            relationCode=item.relation_code,
            relationName=item.relation_name,
            status=item.status,
            savedTime=item.saved_time,
            submittedTime=item.submitted_time,
            closedTime=item.closed_time,
        )

    @classmethod
    async def _context(
        cls, db: Any, project_id: int, project_scope_sql: Any, target_scope_sql: Any
    ) -> tuple[Any, set[int], int, tuple[int, ...]]:
        project = await FeedbackProgressDao.get_project_scoped(db, project_id, project_scope_sql, for_share=True)
        if project is None or project.current_questionnaire_version_id is None:
            raise cls._problem(status.HTTP_404_NOT_FOUND, 'PROJECT_NOT_FOUND', '项目不存在')
        visible, all_count = await FeedbackProgressDao.get_visible_target_ids(
            db, project_id, project.current_questionnaire_version_id, target_scope_sql
        )
        if not visible and all_count > 0:
            raise cls._problem(status.HTTP_404_NOT_FOUND, 'PROJECT_NOT_FOUND', '项目不存在')
        assignment_ids = await FeedbackProgressDao.lock_visible_assignments_for_share(
            db, project_id, project.current_questionnaire_version_id, visible
        )
        return project, visible, all_count, assignment_ids

    @classmethod
    async def get_progress(
        cls, db: Any, project_id: int, query: ProgressQueryModel, project_scope_sql: Any, target_scope_sql: Any
    ) -> ProgressPageModel:
        project, visible, all_count, assignment_ids = await cls._context(
            db, project_id, project_scope_sql, target_scope_sql
        )
        version_id = project.current_questionnaire_version_id
        options = await FeedbackProgressDao.list_relation_options(db, project_id, version_id, assignment_ids)
        if query.relation_id is not None and not await FeedbackProgressDao.relation_belongs_to_version(
            db, project_id, version_id, query.relation_id
        ):
            raise cls._problem(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                'VALIDATION_ERROR',
                '评价关系不属于当前项目',
            )
        counts = await FeedbackProgressDao.summarize_assignments(db, project_id, version_id, assignment_ids)
        rows, total = await FeedbackProgressDao.list_assignments(db, project_id, version_id, assignment_ids, query)
        complete = len(visible) == all_count
        return ProgressPageModel(
            projectId=project.project_id,
            projectName=project.project_name,
            projectStatus=project.status,
            projectLockVersion=project.lock_version,
            dataScopeComplete=complete,
            scopeMessage=None if complete else '当前数据范围仅覆盖部分被评价人',
            summary=ProgressSummaryModel.from_counts(**counts),
            filterOptions=ProgressFilterOptionsModel(
                relations=[
                    ProgressRelationOptionModel(relationId=i[0], relationCode=i[1], relationName=i[2], sortOrder=i[3])
                    for i in options
                ]
            ),
            rows=[cls._row(item) for item in rows],
            total=total,
            pageNum=query.page_num,
            pageSize=query.page_size,
        )

    @classmethod
    async def get_precheck(
        cls, db: Any, project_id: int, project_scope_sql: Any, target_scope_sql: Any
    ) -> CompletionPrecheckModel:
        project = await FeedbackProgressDao.get_project_scoped(db, project_id, project_scope_sql, for_share=True)
        if project is None:
            raise cls._problem(status.HTTP_404_NOT_FOUND, 'PROJECT_NOT_FOUND', '项目不存在')
        if project.status == ProjectStatus.PREPARING.value:
            raise cls._problem(
                status.HTTP_409_CONFLICT,
                'PROJECT_NOT_ACTIVE',
                '项目尚未进入进行阶段',
            )
        if project.current_questionnaire_version_id is None:
            raise RuntimeError('已发布项目缺少冻结问卷版本')
        visible, all_count = await FeedbackProgressDao.get_visible_target_ids(
            db, project_id, project.current_questionnaire_version_id, target_scope_sql
        )
        if not visible and all_count > 0:
            raise cls._problem(status.HTTP_404_NOT_FOUND, 'PROJECT_NOT_FOUND', '项目不存在')
        assignment_ids = await FeedbackProgressDao.lock_visible_assignments_for_share(
            db, project_id, project.current_questionnaire_version_id, visible
        )
        rows = await FeedbackProgressDao.list_all_assignments(
            db, project_id, project.current_questionnaire_version_id, assignment_ids
        )
        summary = cls._summary(rows)
        groups: dict[tuple[int, str, int, str], list[int]] = {}
        for row in rows:
            key = (row.target_user_id, row.target_user_name, row.relation_id, row.relation_name)
            value = groups.setdefault(key, [0, 0])
            value[0] += 1
            value[1] += row.status == 'SUBMITTED'
        missing = sorted(
            [
                MissingRelationModel(
                    targetUserId=k[0],
                    targetName=k[1],
                    relationId=k[2],
                    relationName=k[3],
                    assignmentCount=v[0],
                    submittedCount=v[1],
                )
                for k, v in groups.items()
                if v[1] == 0
            ],
            key=lambda item: (item.target_user_id, item.relation_id),
        )
        impact = [
            f'完成后{summary.draft_count}项已暂存任务和{summary.pending_count}项未开始任务将关闭且不可继续作答。',
            f'报告只会使用{summary.submitted_count}项已提交答卷；缺失关系不会按0分处理。',
        ]
        complete = len(visible) == all_count
        return CompletionPrecheckModel(
            projectId=project.project_id,
            projectName=project.project_name,
            projectStatus=project.status,
            projectLockVersion=project.lock_version,
            dataScopeComplete=complete,
            canComplete=project.status == 'ACTIVE' and complete and summary.total_count > 0,
            completedBy=getattr(project, 'completed_by', None) if project.status == 'COMPLETED' else None,
            completedTime=getattr(project, 'completed_time', None) if project.status == 'COMPLETED' else None,
            completionReason=getattr(project, 'completion_reason', None) if project.status == 'COMPLETED' else None,
            alreadyCompleted=project.status == 'COMPLETED',
            summary=summary,
            missingRelations=missing,
            impactMessages=impact,
            precheckedAt=datetime.now(),
        )

    @classmethod
    async def complete_project(  # noqa: PLR0915 - 事务边界内显式保持状态检查顺序
        cls,
        db: Any,
        project_id: int,
        request: ProjectCompleteRequestModel,
        operator_id: int,
        operator_name: str,
        project_scope_sql: Any,
        target_scope_sql: Any,
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> ProjectCompleteResultModel:
        failure_stage = 'project_lock'
        try:
            project = await FeedbackProgressDao.get_project_scoped(db, project_id, project_scope_sql, for_update=True)
            failure_stage = 'project_state_check'
            if project is None:
                raise cls._problem(404, 'PROJECT_NOT_FOUND', '项目不存在')
            if project.status == ProjectStatus.PREPARING.value:
                raise cls._problem(409, 'PROJECT_NOT_ACTIVE', '项目尚未进入进行阶段')
            version_id = project.current_questionnaire_version_id
            failure_stage = 'target_scope_check'
            visible, all_count = await FeedbackProgressDao.get_visible_target_ids(
                db, project_id, version_id, target_scope_sql
            )
            if len(visible) != all_count:
                raise cls._problem(
                    403,
                    'PROJECT_COMPLETION_SCOPE_FORBIDDEN',
                    '当前数据范围不能完成整个项目',
                )
            failure_stage = 'assignment_lock'
            tasks = await FeedbackProgressDao.lock_assignments(db, project_id, version_id)
            failure_stage = 'summary_before_completion'
            current_summary = cls._summary(tasks)
            if project.status == ProjectStatus.COMPLETED.value:
                failure_stage = 'idempotent_response_build'
                result = ProjectCompleteResultModel(
                    projectId=project.project_id,
                    projectStatus=project.status,
                    projectLockVersion=project.lock_version,
                    completedBy=project.completed_by,
                    completedTime=project.completed_time,
                    completionReason=project.completion_reason,
                    alreadyCompleted=True,
                    summary=current_summary,
                )
                await db.rollback()
                return result
            if current_summary.total_count == 0:
                raise cls._problem(
                    409,
                    'PROJECT_HAS_NO_ASSIGNMENTS',
                    '项目没有评价任务，不能完成',
                )
            failure_stage = 'version_check'
            if project.lock_version != request.project_lock_version:
                raise cls._problem(409, 'PROJECT_VERSION_CONFLICT', '项目版本已变化，请重新预检')
            expected = request.expected_summary
            expected_tuple = (
                expected.total_count,
                expected.submitted_count,
                expected.draft_count,
                expected.pending_count,
                expected.closed_incomplete_count,
            )
            actual_tuple = (
                current_summary.total_count,
                current_summary.submitted_count,
                current_summary.draft_count,
                current_summary.pending_count,
                current_summary.closed_incomplete_count,
            )
            if actual_tuple != expected_tuple:
                failure_stage = 'stale_precheck_build'
                latest = (await cls.get_precheck(db, project_id, project_scope_sql, target_scope_sql)).model_dump(
                    by_alias=True, mode='json'
                )
                raise cls._problem(
                    409,
                    'COMPLETION_PRECHECK_STALE',
                    '任务统计已变化，请重新确认',
                    latestPrecheck=latest,
                )
            failure_stage = 'assignment_close'
            completed_at = datetime.now()
            closeable = [item for item in tasks if item.status in {'PENDING', 'DRAFT'}]
            for task in closeable:
                FeedbackStateTransitionService.ensure_assignment_transition(
                    task.status, AssignmentStatus.CLOSED_INCOMPLETE
                )
                task.status = 'CLOSED_INCOMPLETE'
                task.closed_time = completed_at
                task.update_time = completed_at
                task.lock_version += 1
            failure_stage = 'project_update'
            FeedbackStateTransitionService.ensure_project_transition(project.status, ProjectStatus.COMPLETED)
            project.status = ProjectStatus.COMPLETED.value
            project.completed_by = operator_id
            project.completed_time = completed_at
            project.completion_reason = request.completion_reason
            project.update_by = operator_name
            project.update_time = completed_at
            project.lock_version += 1
            failure_stage = 'state_verify'
            if any(item.status in {'PENDING', 'DRAFT'} for item in tasks):
                raise RuntimeError('项目完成后仍有未关闭任务')
            final_summary = cls._summary(tasks)
            failure_stage = 'audit_persist'
            await FeedbackProgressDao.add_completion_audit(
                db,
                FbProjectCompletionAudit(
                    project_id=project.project_id,
                    version_id=version_id,
                    result='SUCCESS',
                    operator_user_id=operator_id,
                    operator_name=operator_name,
                    request_id=request_id or None,
                    trace_id=trace_id or None,
                    before_total_count=current_summary.total_count,
                    before_submitted_count=current_summary.submitted_count,
                    before_draft_count=current_summary.draft_count,
                    before_pending_count=current_summary.pending_count,
                    before_closed_incomplete_count=current_summary.closed_incomplete_count,
                    closed_assignment_count=len(closeable),
                    completion_reason=request.completion_reason,
                    completed_time=completed_at,
                ),
            )
            failure_stage = 'flush'
            await db.flush()
            failure_stage = 'response_build'
            result = ProjectCompleteResultModel(
                projectId=project.project_id,
                projectStatus=project.status,
                projectLockVersion=project.lock_version,
                completedBy=project.completed_by,
                completedTime=project.completed_time,
                completionReason=project.completion_reason,
                alreadyCompleted=False,
                summary=final_summary,
            )
            failure_stage = 'commit'
            await db.commit()
            return result
        except HTTPException:
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            raise ProjectCompletionExecutionError(failure_stage) from exc
