import { normalizeDecimal } from './fixedDecimal'
import { createStableCode } from './stableCode'

export const SELF_RELATION_CODE = 'REL_SELF'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

export function normalizePublicationConfig(value) {
  const config = clone(value || {})
  config.targets = Array.isArray(config.targets) ? config.targets : []
  config.relations = Array.isArray(config.relations)
    ? config.relations.map((item, index) => ({
        ...item,
        weight: normalizeDecimal(item.weight ?? 0),
        sortOrder: index + 1
      }))
    : []
  config.evaluatorSelections = Array.isArray(config.evaluatorSelections)
    ? config.evaluatorSelections.map(item => ({
        ...item,
        evaluatorUserIds: [...new Set(item.evaluatorUserIds || [])]
      }))
    : []
  config.configuredParticipants = Array.isArray(config.configuredParticipants)
    ? config.configuredParticipants
    : []
  config.validationIssues = Array.isArray(config.validationIssues) ? config.validationIssues : []
  config.preview = config.preview || {
    targetCount: 0,
    assignmentCount: 0,
    evaluatorCount: 0,
    targetSummaries: []
  }
  return config
}

export function createCustomRelation(sortOrder) {
  return {
    relationId: null,
    relationCode: createStableCode('REL'),
    relationType: 'CUSTOM',
    relationName: `自定义关系${sortOrder}`,
    isEnabled: true,
    participatesInScore: false,
    weight: '0.0000',
    sortOrder,
    fixed: false
  }
}

export function serializePublicationConfig(config) {
  return {
    projectLockVersion: config.projectLockVersion,
    versionId: config.versionId,
    versionLockVersion: config.versionLockVersion,
    targets: config.targets.map(item => ({ targetUserId: item.userId })),
    relations: config.relations.map((item, index) => ({
      relationCode: item.relationCode,
      relationType: item.relationType,
      relationName: String(item.relationName || '').trim(),
      isEnabled: Boolean(item.isEnabled),
      participatesInScore: Boolean(item.participatesInScore),
      weight: normalizeDecimal(item.weight ?? 0),
      sortOrder: index + 1
    })),
    evaluatorSelections: config.evaluatorSelections
      .filter(
        item =>
          item.relationCode !== SELF_RELATION_CODE &&
          !item.systemManaged &&
          item.evaluatorUserIds?.length
      )
      .map(item => ({
        targetUserId: item.targetUserId,
        relationCode: item.relationCode,
        evaluatorUserIds: [...new Set(item.evaluatorUserIds)].sort((left, right) => left - right)
      }))
  }
}

export function validatePublicationConfig(config) {
  if (!config) return ['发布配置尚未加载']
  const errors = []
  const names = new Set()
  for (const relation of config.relations) {
    const name = String(relation.relationName || '').trim()
    if (!name) errors.push('请填写所有评价关系名称')
    if (names.has(name)) errors.push(`评价关系名称“${name}”重复`)
    names.add(name)
    try {
      relation.weight = normalizeDecimal(relation.weight ?? 0)
    } catch {
      errors.push(`评价关系“${name || relation.relationCode}”的权重格式不正确`)
    }
  }
  return [...new Set(errors)]
}
