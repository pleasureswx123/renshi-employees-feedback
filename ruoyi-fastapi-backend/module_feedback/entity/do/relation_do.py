from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from config.database import Base
from module_feedback.entity.do.mixins import FeedbackAuditMixin


class FbRelation(FeedbackAuditMixin, Base):
    """项目问卷版本内冻结的评价关系。"""

    __tablename__ = 'fb_relation'
    __table_args__ = (
        ForeignKeyConstraint(
            ['project_id', 'version_id'],
            ['fb_questionnaire_version.project_id', 'fb_questionnaire_version.version_id'],
            name='fk_fb_relation_project_version',
            ondelete='CASCADE',
        ),
        UniqueConstraint('version_id', 'relation_code', name='uq_fb_relation_version_code'),
        UniqueConstraint('version_id', 'relation_name', name='uq_fb_relation_version_name'),
        UniqueConstraint('version_id', 'sort_order', name='uq_fb_relation_version_sort'),
        UniqueConstraint('project_id', 'version_id', 'relation_id', name='uq_fb_relation_project_version_id'),
        CheckConstraint(
            "relation_type IN ('SUPERVISOR', 'PEER', 'SUBORDINATE', 'SELF', 'OTHER', 'CUSTOM')",
            name='ck_fb_relation_type',
        ),
        CheckConstraint('weight >= 0 AND weight <= 100', name='ck_fb_relation_weight'),
        CheckConstraint('sort_order > 0', name='ck_fb_relation_sort'),
        CheckConstraint(
            "relation_type <> 'SELF' OR weight = 0",
            name='ck_fb_relation_self_weight',
        ),
        {'comment': '项目评价关系表'},
    )

    relation_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='评价关系ID')
    project_id = Column(BigInteger, nullable=False, comment='评价项目ID')
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    relation_code = Column(String(64), nullable=False, comment='版本内稳定关系标识')
    relation_type = Column(String(20), nullable=False, comment='评价关系类型')
    relation_name = Column(String(100), nullable=False, comment='评价关系名称')
    is_enabled = Column(Boolean, nullable=False, server_default=text('true'), comment='是否启用')
    participates_in_score = Column(Boolean, nullable=False, server_default=text('true'), comment='是否参与综合计分')
    weight = Column(Numeric(12, 4), nullable=False, server_default='0', comment='关系配置权重百分比')
    sort_order = Column(Integer, nullable=False, comment='关系顺序')

    questionnaire_version = relationship('FbQuestionnaireVersion', back_populates='relations', lazy='raise')
    evaluator_selections = relationship('FbEvaluatorSelection', lazy='raise', viewonly=True)
    assignments = relationship('FbAssignment', lazy='raise', viewonly=True)
