import { DECIMAL_FACTOR, toScaledInteger } from './fixedDecimal'
import { SELF_RELATION_CODE } from './publicationConfig'

import { PROJECT_PREPARATION_STEPS } from '@/constants/projectPreparation'

export const PUBLICATION_STEPS = PROJECT_PREPARATION_STEPS.slice(2)

export function analyzePublicationWorkflow(config, mode = 'others') {
  const targets = config?.targets || []
  const relations = config?.relations || []
  const enabled = relations.filter(item => item.isEnabled && item.relationCode !== SELF_RELATION_CODE)
  const scored = enabled.filter(item => item.participatesInScore)
  const selections = (config?.evaluatorSelections || []).filter(item =>
    enabled.some(relation => relation.relationCode === item.relationCode) && item.evaluatorUserIds.length
  )
  const targetIssues = targets.length ? [] : ['请至少选择一名被评价人']
  const relationIssues = ['others', 'self'].includes(mode) ? [] : ['请选择评价方式']
  const names = relations.map(item => String(item.relationName || '').trim())
  if (names.some(name => !name)) relationIssues.push('请填写所有评价关系名称')
  if (new Set(names).size !== names.length) relationIssues.push('评价关系名称不能重复')
  let total = 0
  try {
    total = scored.reduce((sum, item) => sum + toScaledInteger(item.weight), 0)
    if (scored.some(item => toScaledInteger(item.weight) <= 0)) relationIssues.push('参与计分的关系权重必须大于 0%')
  } catch { relationIssues.push('请填写有效的关系权重') }
  if (mode === 'others') {
    if (!enabled.length) relationIssues.push('请启用至少一种评价关系，或选择“仅自评”')
    if (total !== 100 * DECIMAL_FACTOR) relationIssues.push(`计分关系权重应合计 100%，当前为 ${total / DECIMAL_FACTOR}%`)
  }
  const assignmentIssues = []
  const targetSummaries = targets.map(target => {
    const assigned = selections.filter(item => item.targetUserId === target.userId)
    const missingRelations = enabled.filter(relation => !assigned.some(item => item.relationCode === relation.relationCode))
    const superiorCodes = new Set(enabled.filter(item => item.relationType === 'SUPERVISOR').map(item => item.relationCode))
    const superiorIds = new Set(assigned.filter(item => superiorCodes.has(item.relationCode)).flatMap(item => item.evaluatorUserIds))
    const peers = enabled.filter(item => item.relationType === 'PEER')
    let conflict = false
    for (const peer of peers) {
      const duplicates = assigned.filter(item => item.relationCode === peer.relationCode).flatMap(item => item.evaluatorUserIds).filter(id => superiorIds.has(id))
      if (duplicates.length) {
        conflict = true
        const names = duplicates.map(id => { const person = config.configuredParticipants?.find(item => item.userId === id); return person?.nickName || person?.userName || `用户${id}` })
        assignmentIssues.push({ message: `“${target.nickName || target.userName}”的上级与同级重复：${names.join('、')}，请保留一种关系`, targetUserId: target.userId, relationCode: peer.relationCode })
      }
    }
    const missingScoring = missingRelations.length > 0 || conflict
    for (const relation of missingRelations) {
      assignmentIssues.push({
        message: `“${target.nickName || target.userName}”尚未配置“${relation.relationName}”评价人`,
        targetUserId: target.userId,
        relationCode: relation.relationCode
      })
    }
    return {
      ...target,
      hasOthers: assigned.length > 0,
      missingScoring,
      description: assigned.map(item => `${enabled.find(relation => relation.relationCode === item.relationCode)?.relationName} ${item.evaluatorUserIds.length} 人`).join('、') || (enabled.length ? '尚未分配评价人' : '仅自评')
    }
  })
  return { targetIssues, relationIssues, assignmentIssues, targetSummaries, totalWeight: total / DECIMAL_FACTOR }
}

export function publicationIssueDestination(issue) {
  if (['EVALUATOR_RELATION_CONFLICT', 'TARGET_RELATION_ASSIGNMENT_REQUIRED', 'RELATION_POSITIVE_ASSIGNMENT_REQUIRED', 'TARGET_SCORING_ASSIGNMENT_REQUIRED', 'EVALUATOR_USER_UNAVAILABLE'].includes(issue.code)) return 2
  if (issue.path?.startsWith('targets')) return 0
  if (issue.path?.startsWith('relations')) return 1
  if (issue.path?.startsWith('evaluatorSelections')) return 2
  return 'editor'
}
