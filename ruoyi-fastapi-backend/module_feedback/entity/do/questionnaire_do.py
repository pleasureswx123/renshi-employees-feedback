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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from config.database import Base
from module_feedback.entity.do.mixins import FeedbackAuditMixin, LockVersionMixin
from module_feedback.enums import QuestionnaireVersionStatus


class FbQuestionnaireVersion(FeedbackAuditMixin, LockVersionMixin, Base):
    """可编辑或已冻结的问卷版本。"""

    __tablename__ = 'fb_questionnaire_version'
    __table_args__ = (
        UniqueConstraint('project_id', 'version_no', name='uq_fb_questionnaire_version_project_no'),
        UniqueConstraint('project_id', 'version_id', name='uq_fb_questionnaire_version_project_id'),
        CheckConstraint('version_no > 0', name='ck_fb_questionnaire_version_no'),
        CheckConstraint("status IN ('DRAFT', 'FROZEN')", name='ck_fb_questionnaire_version_status'),
        CheckConstraint('lock_version >= 0', name='ck_fb_questionnaire_version_lock'),
        CheckConstraint(
            "status <> 'FROZEN' OR (frozen_by IS NOT NULL AND frozen_time IS NOT NULL)",
            name='ck_fb_questionnaire_version_frozen',
        ),
        Index(
            'uq_fb_questionnaire_version_draft',
            'project_id',
            unique=True,
            postgresql_where=text("status = 'DRAFT'"),
        ),
        {'comment': '问卷版本表'},
    )

    version_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='问卷版本ID')
    project_id = Column(
        BigInteger,
        ForeignKey('fb_project.project_id', name='fk_fb_questionnaire_version_project', ondelete='RESTRICT'),
        nullable=False,
        comment='评价项目ID',
    )
    version_no = Column(Integer, nullable=False, comment='项目内版本号')
    status = Column(
        String(20),
        nullable=False,
        server_default=QuestionnaireVersionStatus.DRAFT.value,
        comment='问卷版本状态',
    )
    title = Column(String(200), nullable=False, comment='问卷标题')
    description = Column(Text, nullable=True, comment='问卷说明')
    description_doc = Column(JSONB, nullable=True, comment='问卷富文本说明文档')
    settings = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), comment='问卷全局设置')
    scoring_rule_snapshot = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment='计分规则快照',
    )
    frozen_by = Column(
        BigInteger,
        ForeignKey('sys_user.user_id', name='fk_fb_questionnaire_version_frozen_user', ondelete='RESTRICT'),
        nullable=True,
        comment='冻结人用户ID',
    )
    frozen_time = Column(DateTime, nullable=True, comment='冻结时间')

    project = relationship(
        'FbProject',
        back_populates='questionnaire_versions',
        foreign_keys=[project_id],
        lazy='raise',
    )
    pages = relationship(
        'FbQuestionnairePage',
        back_populates='questionnaire_version',
        lazy='raise',
        order_by='FbQuestionnairePage.sort_order',
    )
    indicators = relationship(
        'FbIndicator',
        back_populates='questionnaire_version',
        lazy='raise',
        order_by='FbIndicator.sort_order',
    )
    relations = relationship(
        'FbRelation',
        back_populates='questionnaire_version',
        lazy='raise',
        order_by='FbRelation.sort_order',
    )


class FbQuestionnairePage(FeedbackAuditMixin, Base):
    """问卷页面。"""

    __tablename__ = 'fb_questionnaire_page'
    __table_args__ = (
        UniqueConstraint('version_id', 'sort_order', name='uq_fb_questionnaire_page_version_sort'),
        UniqueConstraint('version_id', 'page_code', name='uq_fb_questionnaire_page_version_code'),
        UniqueConstraint('version_id', 'page_id', name='uq_fb_questionnaire_page_version_id'),
        CheckConstraint('sort_order > 0', name='ck_fb_questionnaire_page_sort'),
        {'comment': '问卷页面表'},
    )

    page_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='问卷页面ID')
    version_id = Column(
        BigInteger,
        ForeignKey('fb_questionnaire_version.version_id', name='fk_fb_questionnaire_page_version', ondelete='CASCADE'),
        nullable=False,
        comment='问卷版本ID',
    )
    page_code = Column(String(64), nullable=False, comment='版本内稳定页面标识')
    page_title = Column(String(200), nullable=False, comment='页面标题')
    # 历史兼容字段：业务不再读写，保留已冻结版本的原始数据。
    page_description = Column(Text, nullable=True, comment='页面说明')
    sort_order = Column(Integer, nullable=False, comment='页面顺序')

    questionnaire_version = relationship('FbQuestionnaireVersion', back_populates='pages', lazy='raise')
    questions = relationship(
        'FbQuestion',
        back_populates='page',
        lazy='raise',
        order_by='FbQuestion.sort_order',
    )


class FbQuestion(FeedbackAuditMixin, Base):
    """问卷题目。"""

    __tablename__ = 'fb_question'
    __table_args__ = (
        ForeignKeyConstraint(
            ['version_id', 'page_id'],
            ['fb_questionnaire_page.version_id', 'fb_questionnaire_page.page_id'],
            name='fk_fb_question_page_version',
            ondelete='CASCADE',
        ),
        UniqueConstraint('version_id', 'question_code', name='uq_fb_question_version_code'),
        UniqueConstraint('page_id', 'sort_order', name='uq_fb_question_page_sort'),
        UniqueConstraint('version_id', 'question_id', name='uq_fb_question_version_id'),
        CheckConstraint(
            "question_type IN ('SINGLE_CHOICE', 'STAR_RATING', 'NUMERIC_INPUT', 'SLIDER', 'TEXT')",
            name='ck_fb_question_type',
        ),
        CheckConstraint('sort_order > 0', name='ck_fb_question_sort'),
        CheckConstraint('decimal_places BETWEEN 0 AND 4', name='ck_fb_question_decimal_places'),
        CheckConstraint("question_type <> 'TEXT' OR is_scored = false", name='ck_fb_question_text_not_scored'),
        CheckConstraint(
            "(question_type IN ('STAR_RATING', 'NUMERIC_INPUT', 'SLIDER') "
            'AND min_score IS NOT NULL AND max_score IS NOT NULL AND max_score > min_score) '
            "OR (question_type NOT IN ('STAR_RATING', 'NUMERIC_INPUT', 'SLIDER') "
            'AND min_score IS NULL AND max_score IS NULL)',
            name='ck_fb_question_score_range',
        ),
        Index('ix_fb_question_version_type', 'version_id', 'question_type'),
        {'comment': '问卷题目表'},
    )

    question_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='题目ID')
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    page_id = Column(BigInteger, nullable=False, comment='问卷页面ID')
    question_code = Column(String(64), nullable=False, comment='版本内稳定题目标识')
    question_type = Column(String(30), nullable=False, comment='题型')
    title = Column(Text, nullable=False, comment='题目标题')
    description = Column(Text, nullable=True, comment='题目说明')
    is_required = Column(Boolean, nullable=False, server_default=text('false'), comment='是否必答')
    is_scored = Column(Boolean, nullable=False, server_default=text('true'), comment='是否参与计分')
    min_score = Column(Numeric(12, 4), nullable=True, comment='最低分')
    max_score = Column(Numeric(12, 4), nullable=True, comment='最高分')
    decimal_places = Column(SmallInteger, nullable=False, server_default='0', comment='允许小数位数')
    config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), comment='题型特有配置')
    sort_order = Column(Integer, nullable=False, comment='页内题目顺序')

    page = relationship('FbQuestionnairePage', back_populates='questions', lazy='raise')
    options = relationship(
        'FbQuestionOption',
        back_populates='question',
        lazy='raise',
        order_by='FbQuestionOption.sort_order',
    )


class FbQuestionOption(FeedbackAuditMixin, Base):
    """单选题选项。"""

    __tablename__ = 'fb_question_option'
    __table_args__ = (
        UniqueConstraint('question_id', 'option_code', name='uq_fb_question_option_question_code'),
        UniqueConstraint('question_id', 'sort_order', name='uq_fb_question_option_question_sort'),
        UniqueConstraint('question_id', 'option_id', name='uq_fb_question_option_question_id'),
        CheckConstraint('sort_order > 0', name='ck_fb_question_option_sort'),
        {'comment': '题目选项表'},
    )

    option_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='题目选项ID')
    question_id = Column(
        BigInteger,
        ForeignKey('fb_question.question_id', name='fk_fb_question_option_question', ondelete='CASCADE'),
        nullable=False,
        comment='题目ID',
    )
    option_code = Column(String(64), nullable=False, comment='题目内稳定选项标识')
    option_label = Column(String(500), nullable=False, comment='选项文本')
    score = Column(Numeric(12, 4), nullable=False, server_default='0', comment='选项原始分')
    requires_reason = Column(Boolean, nullable=False, server_default=text('false'), comment='是否要求附加原因')
    sort_order = Column(Integer, nullable=False, comment='选项顺序')

    question = relationship('FbQuestion', back_populates='options', lazy='raise')


class FbIndicator(FeedbackAuditMixin, Base):
    """问卷计分指标。"""

    __tablename__ = 'fb_indicator'
    __table_args__ = (
        UniqueConstraint('version_id', 'indicator_code', name='uq_fb_indicator_version_code'),
        UniqueConstraint('version_id', 'indicator_name', name='uq_fb_indicator_version_name'),
        UniqueConstraint('version_id', 'sort_order', name='uq_fb_indicator_version_sort'),
        UniqueConstraint('version_id', 'indicator_id', name='uq_fb_indicator_version_id'),
        CheckConstraint('weight >= 0 AND weight <= 100', name='ck_fb_indicator_weight'),
        CheckConstraint('sort_order > 0', name='ck_fb_indicator_sort'),
        {'comment': '评价指标表'},
    )

    indicator_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='指标ID')
    version_id = Column(
        BigInteger,
        ForeignKey('fb_questionnaire_version.version_id', name='fk_fb_indicator_version', ondelete='CASCADE'),
        nullable=False,
        comment='问卷版本ID',
    )
    indicator_code = Column(String(64), nullable=False, comment='版本内稳定指标标识')
    indicator_name = Column(String(100), nullable=False, comment='指标名称')
    description = Column(Text, nullable=True, comment='指标说明')
    weight = Column(Numeric(12, 4), nullable=False, comment='指标权重百分比')
    sort_order = Column(Integer, nullable=False, comment='指标顺序')

    questionnaire_version = relationship('FbQuestionnaireVersion', back_populates='indicators', lazy='raise')
    question_bindings = relationship('FbIndicatorQuestion', back_populates='indicator', lazy='raise')


class FbIndicatorQuestion(Base):
    """指标与计分题目的一对多绑定。"""

    __tablename__ = 'fb_indicator_question'
    __table_args__ = (
        ForeignKeyConstraint(
            ['version_id', 'indicator_id'],
            ['fb_indicator.version_id', 'fb_indicator.indicator_id'],
            name='fk_fb_indicator_question_indicator',
            ondelete='CASCADE',
        ),
        ForeignKeyConstraint(
            ['version_id', 'question_id'],
            ['fb_question.version_id', 'fb_question.question_id'],
            name='fk_fb_indicator_question_question',
            ondelete='CASCADE',
        ),
        UniqueConstraint('question_id', name='uq_fb_indicator_question_question'),
        {'comment': '指标题目绑定表'},
    )

    binding_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='指标题目绑定ID')
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    indicator_id = Column(BigInteger, nullable=False, comment='指标ID')
    question_id = Column(BigInteger, nullable=False, comment='题目ID')

    indicator = relationship('FbIndicator', back_populates='question_bindings', lazy='raise')
