from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from config.database import Base


class FbScoreResult(Base):
    """可追溯的指标、关系、个人和完成覆盖率结果。"""

    __tablename__ = 'fb_score_result'
    __table_args__ = (
        ForeignKeyConstraint(
            ['project_id', 'version_id', 'target_user_id', 'target_id'],
            [
                'fb_project_target.project_id',
                'fb_project_target.version_id',
                'fb_project_target.target_user_id',
                'fb_project_target.target_id',
            ],
            name='fk_fb_score_result_target',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['version_id', 'indicator_id'],
            ['fb_indicator.version_id', 'fb_indicator.indicator_id'],
            name='fk_fb_score_result_indicator',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['project_id', 'version_id', 'relation_id'],
            ['fb_relation.project_id', 'fb_relation.version_id', 'fb_relation.relation_id'],
            name='fk_fb_score_result_relation',
            ondelete='RESTRICT',
        ),
        CheckConstraint(
            "result_type IN ('INDICATOR_RELATION', 'INDICATOR_COMPOSITE', 'PERSON_TOTAL', 'COVERAGE')",
            name='ck_fb_score_result_type',
        ),
        CheckConstraint('score IS NULL OR (score >= 0 AND score <= 100)', name='ck_fb_score_result_score'),
        CheckConstraint(
            'original_weight IS NULL OR (original_weight >= 0 AND original_weight <= 100)',
            name='ck_fb_score_result_original_weight',
        ),
        CheckConstraint(
            'effective_weight IS NULL OR (effective_weight >= 0 AND effective_weight <= 100)',
            name='ck_fb_score_result_effective_weight',
        ),
        CheckConstraint(
            'expected_count >= 0 AND submitted_count >= 0 AND submitted_count <= expected_count',
            name='ck_fb_score_result_counts',
        ),
        CheckConstraint(
            "(result_type = 'INDICATOR_RELATION' AND indicator_id IS NOT NULL AND relation_id IS NOT NULL) OR "
            "(result_type = 'INDICATOR_COMPOSITE' AND indicator_id IS NOT NULL AND relation_id IS NULL) OR "
            "(result_type IN ('PERSON_TOTAL', 'COVERAGE') AND indicator_id IS NULL AND relation_id IS NULL)",
            name='ck_fb_score_result_dimensions',
        ),
        Index('ix_fb_score_result_project_target', 'project_id', 'target_user_id'),
        Index(
            'uq_fb_score_indicator_relation',
            'project_id',
            'target_user_id',
            'version_id',
            'result_type',
            'indicator_id',
            'relation_id',
            unique=True,
            postgresql_where=text("result_type = 'INDICATOR_RELATION'"),
        ),
        Index(
            'uq_fb_score_indicator_composite',
            'project_id',
            'target_user_id',
            'version_id',
            'result_type',
            'indicator_id',
            unique=True,
            postgresql_where=text("result_type = 'INDICATOR_COMPOSITE'"),
        ),
        Index(
            'uq_fb_score_person_result',
            'project_id',
            'target_user_id',
            'version_id',
            'result_type',
            unique=True,
            postgresql_where=text("result_type IN ('PERSON_TOTAL', 'COVERAGE')"),
        ),
        {'comment': '评价计分结果表'},
    )

    result_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='计分结果ID')
    project_id = Column(
        BigInteger,
        ForeignKey('fb_project.project_id', name='fk_fb_score_result_project', ondelete='RESTRICT'),
        nullable=False,
        comment='评价项目ID',
    )
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    target_id = Column(BigInteger, nullable=False, comment='项目被评价人记录ID')
    target_user_id = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_score_result_target_user', ondelete='RESTRICT'),
        nullable=False,
        comment='被评价人用户ID',
    )
    result_type = Column(String(30), nullable=False, comment='计分结果类型')
    indicator_id = Column(BigInteger, nullable=True, comment='指标ID')
    relation_id = Column(BigInteger, nullable=True, comment='评价关系ID')
    score = Column(Numeric(12, 4), nullable=True, comment='百分制得分；数据不足时为空')
    original_weight = Column(Numeric(12, 4), nullable=True, comment='发布快照中的原配置权重')
    effective_weight = Column(Numeric(12, 4), nullable=True, comment='实际参与计算权重')
    expected_count = Column(Integer, nullable=False, server_default='0', comment='应完成任务数')
    submitted_count = Column(Integer, nullable=False, server_default='0', comment='已提交任务数')
    has_missing_data = Column(Boolean, nullable=False, server_default=text('false'), comment='是否存在缺失数据')
    calculation_version = Column(String(32), nullable=False, comment='计分规则版本')
    calculation_basis = Column(JSONB, nullable=False, comment='可复算的计分输入与过程依据')
    calculated_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='计算时间')
    create_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
