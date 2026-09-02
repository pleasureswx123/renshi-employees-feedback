"""接管RuoYi PostgreSQL基线版本。

Revision ID: 20260902_01_feedback_baseline
Revises:
Create Date: 2026-09-02 11:00:00

完整RuoYi基础结构仍由 ``sql/ruoyi-fastapi-pg.sql`` 初始化。本revision
只建立Alembic版本历史起点，避免后续评价业务迁移重复创建现有系统表。
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '20260902_01_feedback_baseline'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """登记RuoYi PostgreSQL基线，不重复创建基线SQL中的对象。"""


def downgrade() -> None:
    """移除版本登记时保留RuoYi基线结构。"""
