"""增加发布前评价人选择配置并初始化固定关系。

Revision ID: 20260902_04_feedback_publication
Revises: 20260902_03_feedback_designer
Create Date: 2026-09-02 14:00:00
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260902_04_feedback_publication'
down_revision: str | Sequence[str] | None = '20260902_03_feedback_designer'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_RELATIONS = (
    ('REL_SUPERVISOR', 'SUPERVISOR', '上级', False, False, '0.0000', 1),
    ('REL_PEER', 'PEER', '同级', False, False, '0.0000', 2),
    ('REL_SUBORDINATE', 'SUBORDINATE', '下级', False, False, '0.0000', 3),
    ('REL_SELF', 'SELF', '自己', True, False, '0.0000', 4),
    ('REL_OTHER', 'OTHER', '其他', False, False, '0.0000', 5),
)


def _audit_columns() -> list[sa.Column]:
    """返回配置类表统一使用的审计字段。"""
    return [
        sa.Column('create_by', sa.String(length=64), server_default=sa.text("''"), nullable=False, comment='创建者'),
        sa.Column(
            'create_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column('update_by', sa.String(length=64), server_default=sa.text("''"), nullable=False, comment='更新者'),
        sa.Column(
            'update_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='更新时间',
        ),
        sa.Column('remark', sa.String(length=500), nullable=True, comment='备注'),
    ]


def _relation_conflict_message(project_id: int, version_id: int, reason: str) -> RuntimeError:
    return RuntimeError(f'P5固定关系回填冲突：project_id={project_id}, version_id={version_id}, {reason}')


def _validate_existing_fixed_relation(
    project_id: int,
    version_id: int,
    relation_code: str,
    relation_type: str,
    row: dict[str, Any],
) -> None:
    if str(row['relation_type']) != relation_type:
        raise _relation_conflict_message(
            project_id,
            version_id,
            f'{relation_code}的类型为{row["relation_type"]}，期望{relation_type}',
        )
    if relation_code != 'REL_SELF':
        return
    self_weight = Decimal(str(row['weight']))
    if not bool(row['is_enabled']) or bool(row['participates_in_score']) or self_weight != Decimal('0.0000'):
        raise _relation_conflict_message(project_id, version_id, 'REL_SELF不满足启用、不参与计分且权重为0')


def _backfill_default_relations() -> None:
    """为既有可编辑草稿补齐固定关系，遇到歧义数据时拒绝猜测。"""
    bind = op.get_bind()
    draft_versions = bind.execute(
        sa.text(
            """
            SELECT v.project_id, v.version_id
            FROM fb_questionnaire_version v
            JOIN fb_project p ON p.project_id = v.project_id
            WHERE v.status = 'DRAFT'
              AND p.status = 'PREPARING'
              AND p.del_flag = '0'
            ORDER BY v.project_id, v.version_id
            """
        )
    ).all()

    for project_id_value, version_id_value in draft_versions:
        project_id = int(project_id_value)
        version_id = int(version_id_value)
        rows = list(
            bind.execute(
                sa.text(
                    """
                    SELECT relation_code, relation_type, relation_name,
                           is_enabled, participates_in_score, weight, sort_order
                    FROM fb_relation
                    WHERE project_id = :project_id AND version_id = :version_id
                    ORDER BY relation_id
                    """
                ),
                {'project_id': project_id, 'version_id': version_id},
            )
            .mappings()
            .all()
        )
        by_code = {str(row['relation_code']): dict(row) for row in rows}

        for relation_code, relation_type, relation_name, enabled, scores, weight, sort_order in DEFAULT_RELATIONS:
            existing = by_code.get(relation_code)
            if existing is not None:
                _validate_existing_fixed_relation(
                    project_id,
                    version_id,
                    relation_code,
                    relation_type,
                    existing,
                )
                continue

            name_owner = next((row for row in rows if str(row['relation_name']) == relation_name), None)
            if name_owner is not None:
                raise _relation_conflict_message(
                    project_id,
                    version_id,
                    f'名称“{relation_name}”已被{name_owner["relation_code"]!s}占用',
                )
            sort_owner = next((row for row in rows if int(row['sort_order']) == sort_order), None)
            if sort_owner is not None:
                raise _relation_conflict_message(
                    project_id,
                    version_id,
                    f'顺序{sort_order}已被{sort_owner["relation_code"]!s}占用',
                )

            bind.execute(
                sa.text(
                    """
                    INSERT INTO fb_relation(
                        project_id, version_id, relation_code, relation_type,
                        relation_name, is_enabled, participates_in_score,
                        weight, sort_order, create_by, update_by
                    )
                    VALUES (
                        :project_id, :version_id, :relation_code, :relation_type,
                        :relation_name, :is_enabled, :participates_in_score,
                        CAST(:weight AS NUMERIC(12, 4)), :sort_order,
                        'p5-migration', 'p5-migration'
                    )
                    """
                ),
                {
                    'project_id': project_id,
                    'version_id': version_id,
                    'relation_code': relation_code,
                    'relation_type': relation_type,
                    'relation_name': relation_name,
                    'is_enabled': enabled,
                    'participates_in_score': scores,
                    'weight': weight,
                    'sort_order': sort_order,
                },
            )
            rows.append(
                {
                    'relation_code': relation_code,
                    'relation_type': relation_type,
                    'relation_name': relation_name,
                    'is_enabled': enabled,
                    'participates_in_score': scores,
                    'weight': Decimal(weight),
                    'sort_order': sort_order,
                }
            )


def upgrade() -> None:
    """创建评价人选择配置表并为既有草稿补齐固定关系。"""
    op.create_table(
        'fb_evaluator_selection',
        sa.Column('selection_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='评价人选择配置ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('target_id', sa.BigInteger(), nullable=False, comment='项目被评价人记录ID'),
        sa.Column('target_user_id', sa.BigInteger(), nullable=False, comment='被评价人用户ID'),
        sa.Column('relation_id', sa.BigInteger(), nullable=False, comment='评价关系ID'),
        sa.Column('evaluator_user_id', sa.BigInteger(), nullable=False, comment='评价人用户ID'),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['project_id'],
            ['fb_project.project_id'],
            name='fk_fb_evaluator_selection_project',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['target_user_id'],
            ['sys_user.user_id'],
            name='fk_fb_evaluator_selection_target_user',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['evaluator_user_id'],
            ['sys_user.user_id'],
            name='fk_fb_evaluator_selection_evaluator_user',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id', 'relation_id'],
            ['fb_relation.project_id', 'fb_relation.version_id', 'fb_relation.relation_id'],
            name='fk_fb_evaluator_selection_relation',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint('selection_id', name='pk_fb_evaluator_selection'),
        sa.UniqueConstraint(
            'project_id',
            'evaluator_user_id',
            'target_user_id',
            'relation_id',
            name='uq_fb_evaluator_selection_business_key',
        ),
        comment='评价人选择配置表',
    )
    op.create_index(
        'ix_fb_evaluator_selection_project_version',
        'fb_evaluator_selection',
        ['project_id', 'version_id'],
    )
    op.create_index(
        'ix_fb_evaluator_selection_evaluator_project',
        'fb_evaluator_selection',
        ['evaluator_user_id', 'project_id'],
    )
    _backfill_default_relations()


def downgrade() -> None:
    """移除选择配置表，保留已经写入P2关系表的固定关系。"""
    op.drop_table('fb_evaluator_selection')
