import { createApp } from 'vue'
import Antd from 'antdv-next'
import 'antdv-next/dist/reset.css'
import 'antdv-next/dist/antd.css'

import App from './App.vue'
import router from './router/setup'
import store from './store'
import './styles/global.less'
import './styles/modules.css'
import { applyTheme } from './theme'

applyTheme(localStorage.getItem('dr:theme') || 'dark')

createApp(App).use(store).use(router).use(Antd).mount('#app')
