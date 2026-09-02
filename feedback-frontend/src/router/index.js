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
        component: () => import('@/views/shared/PlaceholderView.vue'),
        props: {
          title: '我的待办',
          description: 'P1 已完成工程与权限基线；真实评价任务将在后续阶段由后端生成。'
        },
        meta: { title: '我的待办', workspace: 'employee', permissions: ['feedback:task:view'] }
      },
      {
        path: 'reviews',
        name: 'employee-reviews',
        component: () => import('@/views/shared/PlaceholderView.vue'),
        props: {
          title: '我评价的',
          description: '这里将在后续阶段展示当前账号已经提交的评价记录。'
        },
        meta: { title: '我评价的', workspace: 'employee', permissions: ['feedback:history:view'] }
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
