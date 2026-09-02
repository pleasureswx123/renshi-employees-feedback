import request from '@/utils/request'

const prefix = '/feedback/employee'

export const listMyProjects = params => request({ url: `${prefix}/projects`, method: 'get', params })
export const getMyProject = projectId => request({ url: `${prefix}/projects/${projectId}`, method: 'get' })
export const getMyTask = assignmentId => request({ url: `${prefix}/tasks/${assignmentId}`, method: 'get' })
export const listMyHistory = params => request({ url: `${prefix}/history`, method: 'get', params })
export const getMyHistory = assignmentId => request({ url: `${prefix}/history/${assignmentId}`, method: 'get' })
export const saveMyDraft = (assignmentId, data) => request({
  url: `${prefix}/tasks/${assignmentId}/draft`, method: 'put', data,
  headers: { repeatSubmit: false }
})
export const submitMyAnswer = (assignmentId, data) => request({
  url: `${prefix}/tasks/${assignmentId}/submit`, method: 'post', data,
  headers: { repeatSubmit: false }
})
