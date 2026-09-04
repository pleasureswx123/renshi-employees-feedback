import { describe, expect, it } from 'vitest'
import { activeWorkspaceMenu, workspaceMenuItems } from '@/utils/workspaceNavigation'
import { formatDateTime, formatTableDate } from '@/utils/displayFormat'

describe('工作台菜单权限与定位', () => {
  it('HR 基础权限不会显示原始答案入口', () => {
    const permissions = ['feedback:project:list', 'feedback:progress:view', 'feedback:report:view']
    const items = workspaceMenuItems('hr', value => permissions.includes(value))
    expect(items.map(item => item.path)).toEqual(['/hr/projects', '/hr/reports'])
    expect(activeWorkspaceMenu({ path: '/hr/projects/8/editor', meta: { activeMenu: '/hr/projects' } }, items)?.label).toBe('评价项目')
  })

  it('只有进度权限时，明细仍定位到有权访问的进度入口', () => {
    const items = workspaceMenuItems('hr', value => value === 'feedback:progress:view')
    expect(items).toHaveLength(1)
    expect(activeWorkspaceMenu({ path: '/hr/projects/8/progress', meta: { activeMenu: '/hr/projects' } }, items)?.path).toBe('/hr/progress')
  })

  it('员工历史与待办独立授权，未知路径不错误选中菜单', () => {
    const items = workspaceMenuItems('employee', value => value === 'feedback:history:view')
    expect(items.map(item => item.path)).toEqual(['/employee/reviews'])
    expect(activeWorkspaceMenu({ path: '/employee/reviews/8', meta: { activeMenu: '/employee/reviews' } }, items)?.label).toBe('我评价的')
    expect(activeWorkspaceMenu({ path: '/employee/tasks/8', meta: {} }, items)).toBeNull()
  })
})

describe('页面时间显示', () => {
  it('移除数据库小数秒，保持服务端日期与时间', () => {
    expect(formatTableDate({}, {}, '2026-09-02T13:38:08.328437')).toBe('2026-09-02 13:38:08')
    expect(formatDateTime('2026-09-02 13:38:08')).toBe('2026-09-02 13:38:08')
  })
  it('保留显式时区，不把空值或未知格式显示为虚构时间', () => {
    expect(formatDateTime('2026-09-02T13:38:08Z')).toBe('2026-09-02 13:38:08 Z')
    expect(formatDateTime('2026-09-02T13:38:08+08:00')).toBe('2026-09-02 13:38:08 +08:00')
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('待确认')).toBe('待确认')
  })
})
