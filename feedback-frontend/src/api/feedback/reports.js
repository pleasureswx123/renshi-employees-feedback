import request from '@/utils/request'

export const listReportProjects = params => request({ url: '/feedback/reports/projects', method: 'get', params })
export const getTeamReport = (id, params) => request({ url: `/feedback/projects/${id}/reports`, method: 'get', params })
export const generateReports = id => request({ url: `/feedback/projects/${id}/reports/calculate`, method: 'post' })
export const getPersonalReport = (id, targetId) => request({ url: `/feedback/projects/${id}/reports/${targetId}`, method: 'get' })
export const listSubmittedAnswers = (id, params) => request({ url: `/feedback/projects/${id}/answers`, method: 'get', params })
export const getSubmittedAnswer = (id, assignmentId) => request({ url: `/feedback/projects/${id}/answers/${assignmentId}`, method: 'get' })
