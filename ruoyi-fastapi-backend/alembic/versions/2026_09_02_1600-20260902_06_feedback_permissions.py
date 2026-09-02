"""登记评价平台授权项，不自动创建角色或给任何账号授权。"""

import sqlalchemy as sa
from alembic import op

revision = '20260902_06_feedback_permissions'
down_revision = '20260902_05_feedback_answering'
branch_labels = None
depends_on = None

MARKER = 'feedback-p6-permissions'
PERMISSIONS = (
    ('feedback:project:list', '查看评价项目'),
    ('feedback:project:add', '创建评价项目'),
    ('feedback:project:edit', '编辑评价项目'),
    ('feedback:project:remove', '删除评价草稿'),
    ('feedback:project:publish', '发布评价项目'),
    ('feedback:project:complete', '完成评价项目'),
    ('feedback:questionnaire:edit', '设计评价问卷'),
    ('feedback:participant:manage', '配置评价人员'),
    ('feedback:progress:view', '查看评价进度'),
    ('feedback:report:view', '查看评价报告'),
    ('feedback:answer:view', '查看已提交原始答案（敏感）'),
    ('feedback:task:view', '查看本人评价任务'),
    ('feedback:task:answer', '暂存本人评价答卷'),
    ('feedback:task:submit', '提交本人评价答卷'),
    ('feedback:history:view', '查看本人评价历史'),
)


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text('LOCK TABLE sys_menu IN SHARE ROW EXCLUSIVE MODE'))
    parent = connection.scalar(
        sa.text(
            "SELECT menu_id FROM sys_menu WHERE path='feedback-permissions' AND parent_id=0 ORDER BY menu_id LIMIT 1"
        )
    )
    if parent is None:
        parent = connection.scalar(
            sa.text(
                'INSERT INTO sys_menu(menu_name,parent_id,path,menu_type,visible,status,create_by,remark) '
                "VALUES('评价平台权限',0,'feedback-permissions','M','1','0',:marker,'仅供角色授权，业务页面位于feedback-frontend') RETURNING menu_id"
            ),
            {'marker': MARKER},
        )
    for order, (permission, label) in enumerate(PERMISSIONS, start=1):
        exists = connection.scalar(
            sa.text('SELECT menu_id FROM sys_menu WHERE perms=:permission LIMIT 1'), {'permission': permission}
        )
        if exists is None:
            connection.execute(
                sa.text(
                    'INSERT INTO sys_menu(menu_name,parent_id,order_num,path,menu_type,visible,status,perms,create_by,remark) '
                    "VALUES(:label,:parent,:order_num,'#','F','1','0',:permission,:marker,'评价平台接口授权项，不自动分配角色')"
                ),
                {'label': label, 'parent': parent, 'order_num': order, 'permission': permission, 'marker': MARKER},
            )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text('LOCK TABLE sys_menu, sys_role_menu IN SHARE ROW EXCLUSIVE MODE'))
    assigned = connection.scalar(
        sa.text(
            'SELECT count(*) FROM sys_role_menu r JOIN sys_menu m ON r.menu_id=m.menu_id WHERE m.create_by=:marker'
        ),
        {'marker': MARKER},
    )
    if assigned:
        raise RuntimeError('评价权限已授予角色，拒绝降级；请先在系统管理端明确撤销相关授权')
    connection.execute(sa.text("DELETE FROM sys_menu WHERE create_by=:marker AND menu_type='F'"), {'marker': MARKER})
    connection.execute(
        sa.text(
            "DELETE FROM sys_menu m WHERE m.create_by=:marker AND m.menu_type='M' "
            'AND NOT EXISTS(SELECT 1 FROM sys_menu child WHERE child.parent_id=m.menu_id)'
        ),
        {'marker': MARKER},
    )
