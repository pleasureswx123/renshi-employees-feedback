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
