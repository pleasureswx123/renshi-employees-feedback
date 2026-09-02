import pytest

from module_feedback.enums import AssignmentStatus, ProjectStatus
from module_feedback.service.state_transition_service import (
    FeedbackStateTransitionError,
    FeedbackStateTransitionService,
)


@pytest.mark.parametrize(
    ('current', 'target'),
    [
        (ProjectStatus.PREPARING, ProjectStatus.ACTIVE),
        (ProjectStatus.ACTIVE, ProjectStatus.COMPLETED),
        (ProjectStatus.PREPARING, ProjectStatus.PREPARING),
        (ProjectStatus.COMPLETED, ProjectStatus.COMPLETED),
    ],
)
def test_project_legal_transitions(current: ProjectStatus, target: ProjectStatus) -> None:
    assert FeedbackStateTransitionService.ensure_project_transition(current, target) is target


@pytest.mark.parametrize(
    ('current', 'target'),
    [
        (ProjectStatus.PREPARING, ProjectStatus.COMPLETED),
        (ProjectStatus.ACTIVE, ProjectStatus.PREPARING),
        (ProjectStatus.COMPLETED, ProjectStatus.ACTIVE),
        (ProjectStatus.COMPLETED, ProjectStatus.PREPARING),
    ],
)
def test_project_reverse_or_skipped_transitions_are_rejected(current: ProjectStatus, target: ProjectStatus) -> None:
    with pytest.raises(FeedbackStateTransitionError, match='评价项目不允许'):
        FeedbackStateTransitionService.ensure_project_transition(current, target)


@pytest.mark.parametrize(
    ('current', 'target'),
    [
        (AssignmentStatus.PENDING, AssignmentStatus.DRAFT),
        (AssignmentStatus.PENDING, AssignmentStatus.SUBMITTED),
        (AssignmentStatus.PENDING, AssignmentStatus.CLOSED_INCOMPLETE),
        (AssignmentStatus.DRAFT, AssignmentStatus.DRAFT),
        (AssignmentStatus.DRAFT, AssignmentStatus.SUBMITTED),
        (AssignmentStatus.DRAFT, AssignmentStatus.CLOSED_INCOMPLETE),
        (AssignmentStatus.SUBMITTED, AssignmentStatus.SUBMITTED),
        (AssignmentStatus.CLOSED_INCOMPLETE, AssignmentStatus.CLOSED_INCOMPLETE),
    ],
)
def test_assignment_legal_transitions(current: AssignmentStatus, target: AssignmentStatus) -> None:
    assert FeedbackStateTransitionService.ensure_assignment_transition(current, target) is target


@pytest.mark.parametrize(
    ('current', 'target'),
    [
        (AssignmentStatus.DRAFT, AssignmentStatus.PENDING),
        (AssignmentStatus.SUBMITTED, AssignmentStatus.DRAFT),
        (AssignmentStatus.SUBMITTED, AssignmentStatus.CLOSED_INCOMPLETE),
        (AssignmentStatus.CLOSED_INCOMPLETE, AssignmentStatus.PENDING),
        (AssignmentStatus.CLOSED_INCOMPLETE, AssignmentStatus.SUBMITTED),
    ],
)
def test_assignment_terminal_and_reverse_transitions_are_rejected(
    current: AssignmentStatus, target: AssignmentStatus
) -> None:
    with pytest.raises(FeedbackStateTransitionError, match='评价任务不允许'):
        FeedbackStateTransitionService.ensure_assignment_transition(current, target)


def test_transition_accepts_persistence_strings_and_returns_enum() -> None:
    assert FeedbackStateTransitionService.ensure_assignment_transition('PENDING', 'DRAFT') is AssignmentStatus.DRAFT
