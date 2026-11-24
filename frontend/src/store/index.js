import { createStore } from 'vuex'

import app from './app'
import auth from './auth'
import dict from './dict'

export default createStore({
  modules: { app, auth, dict },
})
