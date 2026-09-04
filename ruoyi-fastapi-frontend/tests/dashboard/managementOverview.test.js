import assert from 'node:assert/strict'
import test from 'node:test'
import { loadManagementOverview, resolveFeedbackEntry } from '../../src/utils/managementOverview.js'

test('无权限时不调用接口，也不伪造统计值', async () => {
  let called = false
  const load = () => { called = true; throw new Error('不应调用') }
  const result = await loadManagementOverview(() => false, { users: load, departments: load, roles: load })
  assert.equal(called, false)
  assert.deepEqual(Object.values(result), Array(3).fill({ status: 'forbidden', value: null }))
})

test('读取真实总数且只请求一条用户和角色记录，零条也是有效数据', async () => {
  const queries = []
  const result = await loadManagementOverview(() => true, {
    users: async query => { queries.push(query); return { total: 52, rows: [{}] } },
    departments: async () => ({ data: [{ deptId: 1 }, { deptId: 2 }] }),
    roles: async query => { queries.push(query); return { total: 0, rows: [] } }
  })
  assert.deepEqual(queries, [{ pageNum: 1, pageSize: 1 }, { pageNum: 1, pageSize: 1 }])
  assert.deepEqual(result, {
    users: { status: 'success', value: 52 },
    departments: { status: 'success', value: 2 },
    roles: { status: 'success', value: 0 }
  })
})

test('局部权限与单个接口失败不会影响其他统计', async () => {
  const result = await loadManagementOverview(permission => permission !== 'system:role:list', {
    users: async () => { throw new Error('服务暂不可用') },
    departments: async () => ({ data: [{ deptId: 1 }] }),
    roles: async () => { throw new Error('未授权接口不应调用') }
  })
  assert.deepEqual(result.users, { status: 'error', value: null })
  assert.deepEqual(result.departments, { status: 'success', value: 1 })
  assert.deepEqual(result.roles, { status: 'forbidden', value: null })
})

test('缺失或非法响应不会显示成零', async () => {
  const result = await loadManagementOverview(() => true, {
    users: async () => ({ rows: [] }), departments: async () => ({ data: null }), roles: async () => ({ total: -1 })
  })
  assert.deepEqual(Object.values(result), Array(3).fill({ status: 'error', value: null }))
})

test('评价入口保留部署路径，拒绝空地址、脚本及附带凭据的地址', () => {
  assert.equal(resolveFeedbackEntry(' http://localhost:5174 '), 'http://localhost:5174/')
  assert.equal(resolveFeedbackEntry('https://example.com/feedback/'), 'https://example.com/feedback/')
  for (const value of ['', undefined, '/feedback/', 'javascript:alert(1)', 'https://user:password@example.com/', 'https://example.com/?token=secret', 'https://example.com/#token']) {
    assert.equal(resolveFeedbackEntry(value), '')
  }
})
