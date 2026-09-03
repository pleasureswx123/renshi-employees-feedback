import { defineStore } from 'pinia'

import { getCurrentUser, login, logout } from '@/api/auth'
import { getToken, removeToken, setToken } from '@/utils/auth'
import { useAnswerSheetStore } from './answerSheet'
import { useProjectProgressStore } from './projectProgress'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken() || '',
    user: null,
    roles: [],
    permissions: [],
    initialized: false,
    loading: false
  }),
  getters: {
    userName: state => state.user?.userName || '',
    displayName: state => state.user?.nickName || state.user?.userName || '当前用户'
  },
  actions: {
    applyCurrentUser(payload) {
      this.user = payload.user || null
      this.roles = Array.isArray(payload.roles) ? payload.roles : []
      this.permissions = Array.isArray(payload.permissions) ? payload.permissions : []
      this.initialized = true
    },
    async fetchCurrentUser() {
      const response = await getCurrentUser()
      this.applyCurrentUser(response)
      return response
    },
    async signIn(credentials) {
      if (this.loading) return
      this.loading = true
      try {
        const response = await login(credentials)
        if (!response.token) throw new Error('登录响应缺少Token')
        setToken(response.token)
        this.token = response.token
        await this.fetchCurrentUser()
      } catch (error) {
        this.clearSession()
        throw error
      } finally {
        this.loading = false
      }
    },
    async restoreSession() {
      this.token = getToken() || ''
      if (!this.token) {
        this.clearSession()
        return false
      }
      try {
        await this.fetchCurrentUser()
        return true
      } catch {
        this.clearSession()
        return false
      }
    },
    async signOut() {
      try {
        if (this.token) await logout()
      } catch (error) {
        console.warn('后端退出请求失败，已清理本地登录状态', error)
      } finally {
        this.clearSession()
      }
    },
    clearSession() {
      useAnswerSheetStore().reset()
      useProjectProgressStore().reset()
      removeToken()
      this.token = ''
      this.user = null
      this.roles = []
      this.permissions = []
      this.initialized = false
    }
  }
})
