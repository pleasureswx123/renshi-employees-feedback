import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { public: true, title: '登录' }
  },
  {
    path: '/',
    name: 'workspace-home',
    component: () => import('@/views/shared/PlaceholderView.vue'),
    props: { title: '正在进入工作台', description: '正在根据当前账号权限选择可用入口。' },
    meta: { title: '工作台' }
  },
  {
    path: '/hr',
    component: () => import('@/layouts/HrLayout.vue'),
    meta: { workspace: 'hr' },
    children: [
      {
        path: 'reports', name: 'hr-reports',
        component: () => import('@/views/hr/ReportProjectsView.vue'),
        meta: { title: '评价报告', workspace: 'hr', permissions: ['feedback:report:view'] }
      },
      {
        path: 'projects/:projectId/reports', name: 'hr-project-reports',
        component: () => import('@/views/hr/ProjectReportsView.vue'),
        meta: { title: '项目报告', workspace: 'hr', permissions: ['feedback:report:view'], activeMenu: '/hr/reports' }
      },
      {
        path: 'answers', name: 'hr-answers-entry',
        component: () => import('@/views/hr/SubmittedAnswersView.vue'),
        meta: { title: '原始答案', workspace: 'hr', permissions: ['feedback:answer:view'] }
      },
      {
        path: 'projects/:projectId/answers', name: 'hr-project-answers',
        component: () => import('@/views/hr/SubmittedAnswersView.vue'),
        meta: { title: '原始答案', workspace: 'hr', permissions: ['feedback:answer:view'], activeMenu: '/hr/answers' }
      },
      {
        path: 'progress',
        name: 'hr-progress-entry',
        component: () => import('@/views/hr/ProjectProgressEntryView.vue'),
        meta: {
          title: '回收进度入口',
          workspace: 'hr',
          permissions: ['feedback:progress:view']
        }
      },
      {
        path: 'projects',
        name: 'hr-projects',
        component: () => import('@/views/hr/ProjectListView.vue'),
        meta: { title: '评价项目', workspace: 'hr', permissions: ['feedback:project:list'] }
      },
      {
        path: 'projects/:projectId/editor',
        name: 'hr-questionnaire-editor',
        component: () => import('@/views/hr/QuestionnaireEditorView.vue'),
        meta: {
          title: '问卷编辑器',
          workspace: 'hr',
          permissions: ['feedback:questionnaire:edit']
        }
      },
      {
        path: 'projects/:projectId/publication',
        name: 'hr-publication-config',
        component: () => import('@/views/hr/PublicationConfigView.vue'),
        meta: {
          title: '人员关系与发布',
          workspace: 'hr',
          permissions: ['feedback:participant:manage', 'feedback:project:publish']
        }
      },
      {
        path: 'projects/:projectId/progress',
        name: 'hr-project-progress',
        component: () => import('@/views/hr/ProjectProgressView.vue'),
        meta: {
          title: '回收进度',
          workspace: 'hr',
          permissions: ['feedback:progress:view'],
          activeMenu: '/hr/projects'
        }
      }
    ]
  },
  {
    path: '/employee',
    component: () => import('@/layouts/EmployeeLayout.vue'),
    meta: { workspace: 'employee' },
    children: [
      {
        path: 'todos',
        name: 'employee-todos',
        component: () => import('@/views/employee/EmployeeProjectsView.vue'),
        meta: { title: '我的待办', workspace: 'employee', permissions: ['feedback:task:view'] }
      },
      {
        path: 'reviews',
        name: 'employee-reviews',
        component: () => import('@/views/employee/EmployeeHistoryView.vue'),
        meta: { title: '我评价的', workspace: 'employee', permissions: ['feedback:history:view'] }
      },
      {
        path: 'todos/:projectId',
        name: 'employee-project',
        component: () => import('@/views/employee/EmployeeProjectView.vue'),
        meta: { title: '评价任务', workspace: 'employee', permissions: ['feedback:task:view'] }
      },
      {
        path: 'tasks/:assignmentId',
        name: 'employee-answer',
        component: () => import('@/views/employee/AnswerSheetView.vue'),
        meta: { title: '填写评价', workspace: 'employee', permissions: ['feedback:task:view'] }
      },
      {
        path: 'reviews/:assignmentId',
        name: 'employee-answer-history',
        component: () => import('@/views/employee/AnswerSheetView.vue'),
        props: { history: true },
        meta: { title: '已提交答案', workspace: 'employee', permissions: ['feedback:history:view'] }
      }
    ]
  },
  {
    path: '/403',
    name: 'forbidden',
    component: () => import('@/views/errors/ForbiddenView.vue'),
    meta: { title: '无权访问' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/errors/NotFoundView.vue'),
    meta: { public: true, title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach(async to => {
  document.title = `${to.meta.title || '工作台'} - ${import.meta.env.VITE_APP_TITLE}`
  const authStore = useAuthStore()
  const permissionStore = usePermissionStore()

  if (to.meta.public) {
    if (to.name === 'login' && authStore.token) {
      const restored = authStore.initialized || (await authStore.restoreSession())
      if (restored) return permissionStore.defaultPath()
    }
    return true
  }

  if (!authStore.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!authStore.initialized && !(await authStore.restoreSession())) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'workspace-home') return permissionStore.defaultPath()
  if (to.meta.workspace && !permissionStore.canAccessWorkspace(to.meta.workspace)) {
    return { name: 'forbidden' }
  }
  if (to.meta.permissions?.length && !permissionStore.hasAnyPermission(to.meta.permissions)) {
    return { name: 'forbidden' }
  }
  return true
})

export default router
