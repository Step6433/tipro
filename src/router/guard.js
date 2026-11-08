import { homeForRole } from '../utils/roles'

export async function checkNavigation(to, store) {
  try {
    // Check the persisted account on each private navigation, including changes in another tab.
    if (to.meta.auth) await store.refreshSession()
    else await store.init()
  } catch { if (to.meta.auth) return '/login' }
  if (to.meta.auth && !store.session) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.auth && store.awaitingApproval && to.path !== '/approval') return '/approval'
  if (to.path === '/approval' && store.session && !store.awaitingApproval) return homeForRole(store.session.role)
  if (to.meta.roles && !to.meta.roles.includes(store.session?.role)) return homeForRole(store.session?.role)
}
