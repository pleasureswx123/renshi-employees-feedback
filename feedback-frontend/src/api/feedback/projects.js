import request from '@/utils/request'

export function listProjects(params) {
  return request({ url: '/feedback/projects', method: 'get', params })
}

export function createProject(data) {
  return request({ url: '/feedback/projects', method: 'post', data })
}

export function getProject(projectId) {
  return request({ url: `/feedback/projects/${projectId}`, method: 'get' })
}

export function updateProject(projectId, data) {
  return request({ url: `/feedback/projects/${projectId}`, method: 'put', data })
}

export function removeProject(projectId, lockVersion) {
  return request({
    url: `/feedback/projects/${projectId}`,
    method: 'delete',
    params: { lockVersion }
  })
}

export function getQuestionnaireDraft(projectId) {
  return request({ url: `/feedback/projects/${projectId}/questionnaire-draft`, method: 'get' })
}

export function saveQuestionnaireDraft(projectId, data) {
  return request({
    url: `/feedback/projects/${projectId}/questionnaire-draft`,
    method: 'put',
    data,
    headers: { repeatInterval: 1500 }
  })
}

export function listParticipantOptions(projectId, params) {
  return request({
    url: `/feedback/projects/${projectId}/participant-options`,
    method: 'get',
    params
  })
}

export function getPublicationConfig(projectId) {
  return request({ url: `/feedback/projects/${projectId}/publication-config`, method: 'get' })
}

export function savePublicationConfig(projectId, data) {
  return request({
    url: `/feedback/projects/${projectId}/publication-config`,
    method: 'put',
    data,
    headers: { repeatInterval: 1500 }
  })
}

export function publishProject(projectId, data) {
  return request({
    url: `/feedback/projects/${projectId}/publish`,
    method: 'post',
    data,
    headers: { repeatInterval: 3000 }
  })
}

export function getProjectProgress(projectId, params) {
  return request({
    url: `/feedback/projects/${projectId}/progress`,
    method: 'get',
    params,
    suppressErrorMessage: true
  })
}

export function getCompletionPrecheck(projectId) {
  return request({
    url: `/feedback/projects/${projectId}/completion-precheck`,
    method: 'get',
    suppressErrorMessage: true
  })
}

export function completeProject(projectId, data) {
  return request({
    url: `/feedback/projects/${projectId}/complete`,
    method: 'post',
    data,
    headers: { repeatInterval: 3000 },
    suppressErrorMessage: true
  })
}

export const listSystemTemplates = () => request({ url: '/feedback/projects/system-templates', method: 'get' })
