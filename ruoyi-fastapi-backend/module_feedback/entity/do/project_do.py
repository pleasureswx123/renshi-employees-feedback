from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
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
