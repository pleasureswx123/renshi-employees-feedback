from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, declared_attr


class FeedbackAuditMixin:
    """评价配置类数据使用的RuoYi风格审计字段。"""

    @declared_attr
    def create_by(cls) -> Mapped[str]:  # noqa: N805
        return Column(String(64), nullable=False, server_default='', comment='创建者')

    @declared_attr
    def create_time(cls) -> Mapped[datetime]:  # noqa: N805
        return Column(DateTime, nullable=False, server_default=func.now(), comment='创建时间')

    @declared_attr
    def update_by(cls) -> Mapped[str]:  # noqa: N805
        return Column(String(64), nullable=False, server_default='', comment='更新者')

    @declared_attr
    def update_time(cls) -> Mapped[datetime]:  # noqa: N805
        return Column(
            DateTime,
            nullable=False,
            server_default=func.now(),
            onupdate=datetime.now,
            comment='更新时间',
        )

    @declared_attr
    def remark(cls) -> Mapped[str | None]:  # noqa: N805
        return Column(String(500), nullable=True, comment='备注')


class LockVersionMixin:
    """乐观锁版本字段。"""

    @declared_attr
    def lock_version(cls) -> Mapped[int]:  # noqa: N805
        return Column(Integer, nullable=False, server_default='0', comment='乐观锁版本')
