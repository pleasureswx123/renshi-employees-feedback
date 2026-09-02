import { describe, expect, it } from 'vitest'

import {
  createCustomRelation,
  normalizePublicationConfig,
  serializePublicationConfig,
  validatePublicationConfig
} from '@/utils/publicationConfig'

function configFixture() {
  return normalizePublicationConfig({
    projectId: 7,
    projectLockVersion: 2,
    versionId: 8,
    versionLockVersion: 3,
    targets: [{ userId: 10, nickName: '张三' }],
    relations: [
      {
        relationCode: 'REL_PEER',
        relationType: 'PEER',
        relationName: '同级',
        isEnabled: true,
        participatesInScore: true,
        weight: '100',
        fixed: true
      },
      {
        relationCode: 'REL_SELF',
        relationType: 'SELF',
        relationName: '自己',
        isEnabled: true,
        participatesInScore: false,
        weight: '0',
        fixed: true
      }
    ],
    evaluatorSelections: [
      { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [12, 11, 11] },
      {
        targetUserId: 10,
        relationCode: 'REL_SELF',
        evaluatorUserIds: [10],
        systemManaged: true
      }
    ]
  })
}

describe('P5发布配置工具', () => {
  it('规范化四位小数并只序列化非自评选择', () => {
    const payload = serializePublicationConfig(configFixture())

    expect(payload.relations.map(item => item.weight)).toEqual(['100.0000', '0.0000'])
    expect(payload.evaluatorSelections).toEqual([
      { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11, 12] }
    ])
  })

  it('自定义关系生成稳定REL标识，关系名称重复会在保存前报错', () => {
    const relation = createCustomRelation(6)
    expect(relation.relationCode).toMatch(/^REL_/)
    const config = configFixture()
    config.relations[1].relationName = '同级'
    expect(validatePublicationConfig(config)).toContain('评价关系名称“同级”重复')
  })
})
