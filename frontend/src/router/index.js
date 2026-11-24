import { createRouter, createWebHashHistory } from 'vue-router'

import BasicLayout from '@/layout/BasicLayout.vue'

const routes = [
  { path: '/', redirect: '/Main/Today' },
  {
    path: '/Login',
    name: 'Login',
    component: () => import('@/views/Login/index.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/Register',
    name: 'Register',
    component: () => import('@/views/Register/index.vue'),
    meta: { public: true, title: '注册' },
  },
  {
    path: '/Main',
    component: BasicLayout,
    redirect: '/Main/Today',
    children: [
      {
        path: 'Today',
        name: 'Today',
        component: () => import('@/views/Main/Today/index.vue'),
        meta: { title: '今天' },
      },
      {
        path: 'Timeline',
        name: 'Timeline',
        component: () => import('@/views/Main/Timeline/index.vue'),
        meta: { title: '时间线' },
      },
      {
        path: 'Stats',
        name: 'Stats',
        component: () => import('@/views/Main/Stats/index.vue'),
        meta: { title: '统计' },
      },
    ],
  },
  {
    path: '/System',
    component: BasicLayout,
    redirect: '/System/Account',
    children: [
      {
        path: 'Account',
        name: 'Account',
        component: () => import('@/views/System/Account/index.vue'),
        meta: { title: '账户设置' },
      },
      {
        path: 'Settings',
        name: 'SystemSettings',
        component: () => import('@/views/System/Settings/index.vue'),
        meta: { title: '系统设置', owner: true },
      },
      {
        path: 'User',
        name: 'SystemUser',
        component: () => import('@/views/System/User/index.vue'),
        meta: { title: '用户管理', owner: true },
      },
      {
        path: 'Role',
        name: 'SystemRole',
        component: () => import('@/views/System/Role/index.vue'),
        meta: { title: '角色管理', owner: true },
      },
      {
        path: 'Organization',
        name: 'SystemOrganization',
        component: () => import('@/views/System/Organization/index.vue'),
        meta: { title: '组织管理', owner: true },
      },
      {
        path: 'Menu',
        name: 'SystemMenu',
        component: () => import('@/views/System/Menu/index.vue'),
        meta: { title: '菜单管理', owner: true },
      },
      {
        path: 'BaseCode',
        name: 'SystemBaseCode',
        component: () => import('@/views/System/BaseCode/index.vue'),
        meta: { title: '字典管理', owner: true },
      },
    ],
  },
  { path: '/404', name: 'NotFound', component: () => import('@/views/404.vue'), meta: { public: true } },
  { path: '/:pathMatch(.*)*', redirect: '/404' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
