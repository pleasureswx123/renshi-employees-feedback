from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from config.database import Base
from module_feedback.entity.do.mixins import FeedbackAuditMixin, LockVersionMixin
from module_feedback.enums import AssignmentStatus


class FbProjectTarget(FeedbackAuditMixin, Base):
    """项目被评价人及发布时展示快照。"""

    __tablename__ = 'fb_project_target'
    __table_args__ = (
        ForeignKeyConstraint(
            ['project_id', 'version_id'],
            ['fb_questionnaire_version.project_id', 'fb_questionnaire_version.version_id'],
            name='fk_fb_project_target_project_version',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('project_id', 'target_user_id', name='uq_fb_project_target_project_user'),
        UniqueConstraint(
            'project_id',
            'version_id',
            'target_user_id',
            'target_id',
            name='uq_fb_project_target_assignment_ref',
        ),
        Index('ix_fb_project_target_dept', 'project_id', 'target_dept_id'),
        {'comment': '项目被评价人快照表'},
    )

    target_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='项目被评价人记录ID')
    project_id = Column(
        BigInteger,
        ForeignKey('fb_project.project_id', name='fk_fb_project_target_project', ondelete='RESTRICT'),
        nullable=False,
        comment='评价项目ID',
    )
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    target_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_project_target_user', ondelete='RESTRICT'),
        nullable=False,
        comment='被评价人用户ID',
    )
    target_user_name = Column(String(100), nullable=False, comment='被评价人姓名快照')
    target_dept_id = Column(
        BigInteger,
        ForeignKey('sys_dept.dept_id', name='fk_fb_project_target_dept', ondelete='RESTRICT'),
        nullable=True,
        comment='被评价人部门ID快照',
    )
    target_dept_name = Column(String(100), nullable=True, comment='被评价人部门名称快照')
    only_self_evaluation = Column(
        Boolean,
        nullable=False,
        server_default=text('false'),
        comment='发布时是否仅配置自评',
    )

    project = relationship('FbProject', back_populates='targets', lazy='raise')
    evaluator_selections = relationship('FbEvaluatorSelection', lazy='raise', viewonly=True)
    assignments = relationship('FbAssignment', lazy='raise', viewonly=True)


class FbEvaluatorSelection(FeedbackAuditMixin, Base):
    """准备期评价人选择及发布后的冻结任务来源。"""

    __tablename__ = 'fb_evaluator_selection'
    __table_args__ = (
        ForeignKeyConstraint(
            ['project_id', 'version_id', 'relation_id'],
            ['fb_relation.project_id', 'fb_relation.version_id', 'fb_relation.relation_id'],
            name='fk_fb_evaluator_selection_relation',
            ondelete='CASCADE',
        ),
        ForeignKeyConstraint(
            ['project_id', 'version_id', 'target_user_id', 'target_id'],
            [
                'fb_project_target.project_id',
                'fb_project_target.version_id',
                'fb_project_target.target_user_id',
                'fb_project_target.target_id',
            ],
            name='fk_fb_evaluator_selection_target',
            ondelete='CASCADE',
        ),
        UniqueConstraint(
            'project_id',
            'evaluator_user_id',
            'target_user_id',
            'relation_id',
            name='uq_fb_evaluator_selection_business_key',
        ),
        Index(
            'ix_fb_evaluator_selection_project_version',
            'project_id',
            'version_id',
        ),
        Index(
            'ix_fb_evaluator_selection_evaluator_project',
            'evaluator_user_id',
            'project_id',
        ),
        {'comment': '评价人选择配置表'},
    )

    selection_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='评价人选择配置ID')
    project_id = Column(
        BigInteger,
        ForeignKey('fb_project.project_id', name='fk_fb_evaluator_selection_project', ondelete='RESTRICT'),
        nullable=False,
        comment='评价项目ID',
    )
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    target_id = Column(BigInteger, nullable=False, comment='项目被评价人记录ID')
    target_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_evaluator_selection_target_user', ondelete='RESTRICT'),
        nullable=False,
        comment='被评价人用户ID',
    )
    relation_id = Column(BigInteger, nullable=False, comment='评价关系ID')
    evaluator_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_evaluator_selection_evaluator_user', ondelete='RESTRICT'),
        nullable=False,
        comment='评价人用户ID',
    )

    project = relationship('FbProject', lazy='raise', viewonly=True)
    relation = relationship('FbRelation', lazy='raise', viewonly=True)
    target_snapshot = relationship('FbProjectTarget', lazy='raise', viewonly=True)


class FbAssignment(LockVersionMixin, Base):
    """逐被评价人生成的评价任务。"""

    __tablename__ = 'fb_assignment'
    __table_args__ = (
        ForeignKeyConstraint(
            ['project_id', 'version_id', 'relation_id'],
            ['fb_relation.project_id', 'fb_relation.version_id', 'fb_relation.relation_id'],
            name='fk_fb_assignment_relation',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['project_id', 'version_id', 'target_user_id', 'target_id'],
            [
                'fb_project_target.project_id',
                'fb_project_target.version_id',
                'fb_project_target.target_user_id',
                'fb_project_target.target_id',
            ],
            name='fk_fb_assignment_target',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'project_id',
            'evaluator_user_id',
            'target_user_id',
            'relation_id',
            name='uq_fb_assignment_business_key',
        ),
        UniqueConstraint(
            'assignment_id',
            'project_id',
            'version_id',
            name='uq_fb_assignment_sheet_ref',
        ),
        CheckConstraint(
            "status IN ('PENDING', 'DRAFT', 'SUBMITTED', 'CLOSED_INCOMPLETE')",
            name='ck_fb_assignment_status',
        ),
        CheckConstraint('lock_version >= 0', name='ck_fb_assignment_lock_version'),
        CheckConstraint(
            "status <> 'DRAFT' OR saved_time IS NOT NULL",
            name='ck_fb_assignment_draft_time',
        ),
        CheckConstraint(
            "status <> 'SUBMITTED' OR submitted_time IS NOT NULL",
            name='ck_fb_assignment_submitted_time',
        ),
        CheckConstraint(
            "status <> 'CLOSED_INCOMPLETE' OR closed_time IS NOT NULL",
            name='ck_fb_assignment_closed_time',
        ),
        Index('ix_fb_assignment_evaluator_status', 'evaluator_user_id', 'status'),
        Index('ix_fb_assignment_target_status', 'target_user_id', 'status'),
        Index('ix_fb_assignment_project_status', 'project_id', 'status'),
        {'comment': '评价任务表'},
    )

    assignment_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='评价任务ID')
    project_id = Column(
        BigInteger,
        ForeignKey('fb_project.project_id', name='fk_fb_assignment_project', ondelete='RESTRICT'),
        nullable=False,
        comment='评价项目ID',
    )
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    evaluator_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_assignment_evaluator_user', ondelete='RESTRICT'),
        nullable=False,
        comment='评价人用户ID',
    )
    evaluator_user_name = Column(String(100), nullable=False, comment='评价人姓名快照')
    evaluator_dept_id = Column(
        BigInteger,
        ForeignKey('sys_dept.dept_id', name='fk_fb_assignment_evaluator_dept', ondelete='RESTRICT'),
        nullable=True,
        comment='评价人部门ID快照',
    )
    evaluator_dept_name = Column(String(100), nullable=True, comment='评价人部门名称快照')
    target_id = Column(BigInteger, nullable=False, comment='项目被评价人记录ID')
    target_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_assignment_target_user', ondelete='RESTRICT'),
        nullable=False,
        comment='被评价人用户ID',
    )
    relation_id = Column(BigInteger, nullable=False, comment='评价关系ID')
    status = Column(
        String(20),
        nullable=False,
        server_default=AssignmentStatus.PENDING.value,
        comment='评价任务状态',
    )
    saved_time = Column(DateTime, nullable=True, comment='最近暂存时间')
    submitted_time = Column(DateTime, nullable=True, comment='正式提交时间')
    closed_time = Column(DateTime, nullable=True, comment='关闭未完成时间')
    create_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='更新时间')

    project = relationship('FbProject', lazy='raise', viewonly=True)
    relation = relationship('FbRelation', lazy='raise', viewonly=True)
    target_snapshot = relationship('FbProjectTarget', lazy='raise', viewonly=True)
    answer_sheet = relationship('FbAnswerSheet', back_populates='assignment', lazy='raise', uselist=False)
