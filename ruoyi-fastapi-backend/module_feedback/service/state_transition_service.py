from module_feedback.enums import AssignmentStatus, ProjectStatus


class FeedbackStateTransitionError(ValueError):
    """状态转换不符合评价领域规则。"""

    def __init__(self, aggregate: str, current: str, target: str) -> None:
        self.aggregate = aggregate
        self.current = current
        self.target = target
        super().__init__(f'{aggregate}不允许从{current}转换为{target}')


class FeedbackStateTransitionService:
    """集中维护项目和任务的单向状态机。"""

    _PROJECT_TRANSITIONS = {
        ProjectStatus.PREPARING: frozenset({ProjectStatus.ACTIVE}),
        ProjectStatus.ACTIVE: frozenset({ProjectStatus.COMPLETED}),
        ProjectStatus.COMPLETED: frozenset(),
    }
    _ASSIGNMENT_TRANSITIONS = {
        AssignmentStatus.PENDING: frozenset(
            {
                AssignmentStatus.DRAFT,
                AssignmentStatus.SUBMITTED,
                AssignmentStatus.CLOSED_INCOMPLETE,
            }
        ),
        AssignmentStatus.DRAFT: frozenset(
            {
                AssignmentStatus.SUBMITTED,
                AssignmentStatus.CLOSED_INCOMPLETE,
            }
        ),
        AssignmentStatus.SUBMITTED: frozenset(),
        AssignmentStatus.CLOSED_INCOMPLETE: frozenset(),
    }

    @classmethod
    def ensure_project_transition(cls, current: ProjectStatus | str, target: ProjectStatus | str) -> ProjectStatus:
        """校验项目状态转换并返回规范化目标状态。"""
        normalized_current = ProjectStatus(current)
        normalized_target = ProjectStatus(target)
        if normalized_current == normalized_target:
            return normalized_target
        if normalized_target not in cls._PROJECT_TRANSITIONS[normalized_current]:
            raise FeedbackStateTransitionError('评价项目', normalized_current.value, normalized_target.value)
        return normalized_target

    @classmethod
    def ensure_assignment_transition(
        cls, current: AssignmentStatus | str, target: AssignmentStatus | str
    ) -> AssignmentStatus:
        """校验评价任务状态转换并返回规范化目标状态。"""
        normalized_current = AssignmentStatus(current)
        normalized_target = AssignmentStatus(target)
        if normalized_current == normalized_target:
            return normalized_target
        if normalized_target not in cls._ASSIGNMENT_TRANSITIONS[normalized_current]:
            raise FeedbackStateTransitionError('评价任务', normalized_current.value, normalized_target.value)
        return normalized_target
