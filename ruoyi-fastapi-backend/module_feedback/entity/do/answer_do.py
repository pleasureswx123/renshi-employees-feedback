from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from config.database import Base
from module_feedback.entity.do.mixins import LockVersionMixin
from module_feedback.enums import AnswerSheetStatus


class FbAnswerSheet(LockVersionMixin, Base):
    """评价任务答卷。"""

    __tablename__ = 'fb_answer_sheet'
    __table_args__ = (
        ForeignKeyConstraint(
            ['assignment_id', 'project_id', 'version_id'],
            ['fb_assignment.assignment_id', 'fb_assignment.project_id', 'fb_assignment.version_id'],
            name='fk_fb_answer_sheet_assignment',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('assignment_id', name='uq_fb_answer_sheet_assignment'),
        UniqueConstraint('sheet_id', 'version_id', name='uq_fb_answer_sheet_version_ref'),
        CheckConstraint("status IN ('DRAFT', 'SUBMITTED')", name='ck_fb_answer_sheet_status'),
        CheckConstraint('answered_count >= 0', name='ck_fb_answer_sheet_answered_count'),
        CheckConstraint('lock_version >= 0', name='ck_fb_answer_sheet_lock_version'),
        CheckConstraint(
            "status <> 'SUBMITTED' OR submitted_time IS NOT NULL",
            name='ck_fb_answer_sheet_submitted_time',
        ),
        Index('ix_fb_answer_sheet_project_submitted', 'project_id', 'submitted_time'),
        {'comment': '评价答卷表'},
    )

    sheet_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='答卷ID')
    assignment_id = Column(BigInteger, nullable=False, comment='评价任务ID')
    project_id = Column(BigInteger, nullable=False, comment='评价项目ID')
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    status = Column(
        String(20),
        nullable=False,
        server_default=AnswerSheetStatus.DRAFT.value,
        comment='答卷状态',
    )
    last_page_id = Column(
        BigInteger,
        ForeignKey('fb_questionnaire_page.page_id', name='fk_fb_answer_sheet_last_page', ondelete='RESTRICT'),
        nullable=True,
        comment='最近填写页面ID',
    )
    answered_count = Column(Integer, nullable=False, server_default='0', comment='已作答题目数量')
    raw_total_score = Column(Numeric(12, 4), nullable=True, comment='答卷原始总分')
    submission_snapshot = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment='提交时校验与计分输入快照',
    )
    saved_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='最近保存时间')
    submitted_time = Column(DateTime, nullable=True, comment='正式提交时间')
    create_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='更新时间')

    assignment = relationship('FbAssignment', back_populates='answer_sheet', lazy='raise')
    answers = relationship('FbAnswer', back_populates='answer_sheet', lazy='raise')


class FbAnswer(Base):
    """答卷中的单题答案。"""

    __tablename__ = 'fb_answer'
    __table_args__ = (
        ForeignKeyConstraint(
            ['sheet_id', 'version_id'],
            ['fb_answer_sheet.sheet_id', 'fb_answer_sheet.version_id'],
            name='fk_fb_answer_sheet_version',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['version_id', 'question_id'],
            ['fb_question.version_id', 'fb_question.question_id'],
            name='fk_fb_answer_question_version',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['question_id', 'option_id'],
            ['fb_question_option.question_id', 'fb_question_option.option_id'],
            name='fk_fb_answer_question_option',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('sheet_id', 'question_id', name='uq_fb_answer_sheet_question'),
        CheckConstraint("answer_type IN ('OPTION', 'NUMERIC', 'TEXT')", name='ck_fb_answer_type'),
        CheckConstraint(
            "(answer_type = 'OPTION' AND option_id IS NOT NULL AND numeric_value IS NULL AND text_value IS NULL) OR "
            "(answer_type = 'NUMERIC' AND option_id IS NULL AND numeric_value IS NOT NULL AND text_value IS NULL) OR "
            "(answer_type = 'TEXT' AND option_id IS NULL AND numeric_value IS NULL AND text_value IS NOT NULL)",
            name='ck_fb_answer_value_channel',
        ),
        Index('ix_fb_answer_sheet', 'sheet_id'),
        {'comment': '评价单题答案表'},
    )

    answer_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='单题答案ID')
    sheet_id = Column(BigInteger, nullable=False, comment='答卷ID')
    version_id = Column(BigInteger, nullable=False, comment='问卷版本ID')
    question_id = Column(BigInteger, nullable=False, comment='题目ID')
    answer_type = Column(String(20), nullable=False, comment='答案值类型')
    option_id = Column(BigInteger, nullable=True, comment='所选选项ID')
    numeric_value = Column(Numeric(12, 4), nullable=True, comment='数值答案')
    text_value = Column(Text, nullable=True, comment='文本答案')
    reason = Column(Text, nullable=True, comment='选项附加原因')
    raw_score = Column(Numeric(12, 4), nullable=True, comment='题目原始得分')
    value_snapshot = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment='答案展示值快照',
    )
    create_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='创建时间')
    update_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), comment='更新时间')

    answer_sheet = relationship('FbAnswerSheet', back_populates='answers', lazy='raise')
