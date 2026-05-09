import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import * as authApi from '@/lib/api/auth'
import { setAuthToken } from '@/lib/api/client'
import * as meApi from '@/lib/api/me'
import type { Person, User } from '@/lib/api/types'

type AuthState = {
  user: User | null
  person: Person | null
  isAuthenticated: boolean
  isLoading: boolean

  login: (
    email: string,
    password: string,
  ) => Promise<{ email_verified: boolean }>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  setUser: (user: User | null) => void
  setPerson: (person: Person | null) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      person: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true })
        try {
          const result = await authApi.login(email, password)
          set({
            user: result.user,
            isAuthenticated: true,
            isLoading: false,
          })
          try {
            const me = await meApi.getMe()
            set({ person: me.person })
          } catch {
            // ignore — login is still successful
          }
          return { email_verified: result.email_verified }
        } catch (e) {
          set({ isLoading: false })
          throw e
        }
      },

      logout: async () => {
        try {
          await authApi.logout()
        } finally {
          setAuthToken(null)
          set({ user: null, person: null, isAuthenticated: false })
        }
      },

      refresh: async () => {
        try {
          const me = await meApi.getMe()
          set({
            user: me.user,
            person: me.person,
            isAuthenticated: true,
          })
        } catch {
          set({ user: null, person: null, isAuthenticated: false })
          setAuthToken(null)
        }
      },

      setUser: (user) => set({ user }),
      setPerson: (person) => set({ person }),
    }),
    {
      name: 'radice-auth',
      partialize: (state) => ({
        user: state.user,
        person: state.person,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
)
