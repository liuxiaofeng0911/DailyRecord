import router from './index'
import { setupGuard } from './guard'

setupGuard(router)

window.addEventListener('dr-login-expired', () => {
  if (!window.location.hash.startsWith('#/Login')) {
    window.location.hash = '#/Login'
  }
})

export default router
