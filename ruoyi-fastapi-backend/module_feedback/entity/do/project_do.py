from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from config.database import Base
from module_feedback.entity.do.mixins import FeedbackAuditMixin, LockVersionMixin
from module_feedback.enums import ProjectStatus


class FbProject(FeedbackAuditMixin, LockVersionMixin, Base):
    """评价项目。"""

    __tablename__ = 'fb_project'
    __table_args__ = (
        CheckConstraint(
            "status IN ('PREPARING', 'ACTIVE', 'COMPLETED')",
            name='ck_fb_project_status',
        ),
        CheckConstraint("del_flag IN ('0', '2')", name='ck_fb_project_del_flag'),
        CheckConstraint('lock_version >= 0', name='ck_fb_project_lock_version'),
        CheckConstraint(
            "status = 'PREPARING' OR "
            '(current_questionnaire_version_id IS NOT NULL '
            'AND published_by IS NOT NULL AND published_time IS NOT NULL)',
            name='ck_fb_project_published_fields',
        ),
        CheckConstraint(
            "status <> 'COMPLETED' OR (completed_by IS NOT NULL AND completed_time IS NOT NULL)",
            name='ck_fb_project_completed_fields',
        ),
        Index('ix_fb_project_status_create_time', 'status', 'create_time'),
        Index('ix_fb_project_owner_user_dept', 'owner_user_id', 'owner_dept_id'),
        {'comment': '评价项目表'},
    )

    project_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='评价项目ID')
    project_name = Column(String(200), nullable=False, comment='评价项目名称')
    description = Column(Text, nullable=True, comment='评价项目说明')
    status = Column(
        String(20),
        nullable=False,
        server_default=ProjectStatus.PREPARING.value,
        comment='项目状态',
    )
    owner_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_project_owner_user', ondelete='RESTRICT'),
        nullable=False,
        comment='项目负责人用户ID',
    )
    owner_dept_id = Column(
        BigInteger,
        ForeignKey('sys_dept.dept_id', name='fk_fb_project_owner_dept', ondelete='RESTRICT'),
        nullable=True,
        comment='项目归属部门ID',
    )
    current_questionnaire_version_id = Column(
        BigInteger,
        ForeignKey(
            'fb_questionnaire_version.version_id',
            name='fk_fb_project_current_version',
            ondelete='RESTRICT',
            use_alter=True,
        ),
        nullable=True,
        comment='当前问卷版本ID',
    )
    published_by = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_project_published_user', ondelete='RESTRICT'),
        nullable=True,
        comment='发布人用户ID',
    )
    published_time = Column(DateTime, nullable=True, comment='发布时间')
    completed_by = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_project_completed_user', ondelete='RESTRICT'),
        nullable=True,
        comment='完成人用户ID',
    )
    completed_time = Column(DateTime, nullable=True, comment='完成时间')
    completion_reason = Column(String(500), nullable=True, comment='手动完成原因')
    del_flag = Column(String(1), nullable=False, server_default='0', comment='删除标志（0存在 2删除）')

    questionnaire_versions = relationship(
        'FbQuestionnaireVersion',
        back_populates='project',
        foreign_keys='FbQuestionnaireVersion.project_id',
        lazy='raise',
        order_by='FbQuestionnaireVersion.version_no',
    )
    targets = relationship('FbProjectTarget', back_populates='project', lazy='raise')
    assignments = relationship('FbAssignment', lazy='raise', viewonly=True)


class FbProjectCompletionAudit(Base):
    """项目不可逆完成的同事务业务审计。"""

    __tablename__ = 'fb_project_completion_audit'
    __table_args__ = (
        ForeignKeyConstraint(
            ['project_id', 'version_id'],
            ['fb_questionnaire_version.project_id', 'fb_questionnaire_version.version_id'],
            name='fk_fb_project_completion_audit_project_version',
            ondelete='RESTRICT',
        ),
        CheckConstraint("result = 'SUCCESS'", name='ck_fb_project_completion_audit_result'),
        CheckConstraint(
            'before_total_count >= 0 '
            'AND before_submitted_count >= 0 '
            'AND before_draft_count >= 0 '
            'AND before_pending_count >= 0 '
            'AND before_closed_incomplete_count >= 0 '
            'AND closed_assignment_count >= 0',
            name='ck_fb_project_completion_audit_counts_nonnegative',
        ),
        CheckConstraint(
            'before_total_count = before_submitted_count + before_draft_count '
            '+ before_pending_count + before_closed_incomplete_count',
            name='ck_fb_project_completion_audit_summary_identity',
        ),
        CheckConstraint(
            'closed_assignment_count = before_draft_count + before_pending_count',
            name='ck_fb_project_completion_audit_closed_count',
        ),
        Index(
            'uq_fb_project_completion_audit_success',
            'project_id',
            unique=True,
            postgresql_where=text("result = 'SUCCESS'"),
        ),
        {'comment': '项目完成业务审计表'},
    )

    audit_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='项目完成审计ID')
    project_id = Column(
        BigInteger,
        ForeignKey('fb_project.project_id', name='fk_fb_project_completion_audit_project', ondelete='RESTRICT'),
        nullable=False,
        comment='评价项目ID',
    )
    version_id = Column(BigInteger, nullable=False, comment='完成时冻结问卷版本ID')
    result = Column(String(20), nullable=False, server_default='SUCCESS', comment='完成结果')
    operator_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_project_completion_audit_operator_user', ondelete='RESTRICT'),
        nullable=False,
        comment='完成人用户ID',
    )
    operator_name = Column(String(64), nullable=False, comment='完成人账号快照')
    request_id = Column(String(64), nullable=True, comment='请求ID')
    trace_id = Column(String(64), nullable=True, comment='链路ID')
    before_total_count = Column(Integer, nullable=False, comment='完成前任务总数')
    before_submitted_count = Column(Integer, nullable=False, comment='完成前已提交任务数')
    before_draft_count = Column(Integer, nullable=False, comment='完成前已暂存任务数')
    before_pending_count = Column(Integer, nullable=False, comment='完成前未开始任务数')
    before_closed_incomplete_count = Column(Integer, nullable=False, comment='完成前已关闭未完成任务数')
    closed_assignment_count = Column(Integer, nullable=False, comment='本次关闭未完成任务数')
    completion_reason = Column(String(500), nullable=False, comment='手动完成原因')
    completed_time = Column(DateTime, nullable=False, comment='项目完成时间')
    create_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='审计记录创建时间')
