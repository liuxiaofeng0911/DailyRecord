import { createApp } from 'vue'
import Antd from 'antdv-next'
import 'antdv-next/dist/reset.css'
import 'antdv-next/dist/antd.css'
import { addCollection } from '@iconify/vue'
import lucide from '@iconify-json/lucide/icons.json'

import App from './App.vue'
import router from './router/setup'
import store from './store'
import './styles/global.less'
import './styles/modules.css'
import { applyTheme } from './theme'

// 离线注册 Lucide 图标集，不请求 Iconify 公网 API
addCollection(lucide)

applyTheme(localStorage.getItem('dr:theme') || 'dark')

createApp(App).use(store).use(router).use(Antd).mount('#app')
