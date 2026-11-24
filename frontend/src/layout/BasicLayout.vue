<template>
  <a-layout class="app-layout">
    <a-layout-sider
      v-if="!mobile"
      v-model:collapsed="collapsed"
      :width="220"
      :collapsed-width="64"
      collapsible
      :trigger="null"
      class="app-sider"
    >
      <div class="brand">
        <div class="brand-mark">日</div>
        <span v-if="!collapsed" class="brand-name">每日照片记录</span>
      </div>
      <a-menu
        :selected-keys="selectedKeys"
        mode="inline"
        :items="menuItems"
        :inline-collapsed="collapsed"
        @click="onMenuClick"
      />
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="app-header">
        <div class="header-left">
          <button
            v-if="!mobile"
            type="button"
            class="icon-button"
            aria-label="折叠菜单"
            @click="toggleCollapse"
          >
            ☰
          </button>
          <strong class="header-title">{{ pageTitle }}</strong>
        </div>
        <div class="header-right">
          <ThemeSelect />
          <a-dropdown :menu="userMenu" trigger="click">
            <button type="button" class="user-button">
              <span class="avatar">{{ initial }}</span>
              <span v-if="!mobile" class="user-name">{{ username }}</span>
            </button>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="app-content">
        <router-view v-slot="{ Component }">
          <keep-alive :max="5">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </a-layout-content>
    </a-layout>

    <nav v-if="mobile" class="mobile-tabs">
      <button
        v-for="item in mobileTabs"
        :key="item.key"
        type="button"
        :class="{ active: selectedKeys.includes(item.key) }"
        @click="router.push(item.path)"
      >
        <span class="tab-dot" />
        {{ item.label }}
      </button>
    </nav>
  </a-layout>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'

import ThemeSelect from '@/components/ThemeSelect.vue'

const store = useStore()
const router = useRouter()
const route = useRoute()

const collapsed = computed({
  get: () => store.state.app.collapsed,
  set: (value) => store.commit('app/setCollapsed', value),
})
const mobile = computed(() => store.state.app.mobile)
const username = computed(() => store.state.auth.userInfo?.username || '我')
const initial = computed(() => (username.value || '我').slice(0, 1))
const pageTitle = computed(() => route.meta?.title || '今天')

const selectedKeys = computed(() => {
  if (route.path.startsWith('/System')) {
    return [`/System/${route.name === 'Account' ? 'Account' : route.path.split('/').pop()}`]
  }
  return [route.path]
})

const isOwner = computed(() => store.getters['auth/isOwner'])

const menuItems = computed(() => {
  const items = [
    { key: '/Main/Today', label: '今天' },
    { key: '/Main/Timeline', label: '时间线' },
    { key: '/Main/Stats', label: '统计' },
  ]
  if (!isOwner.value) {
    // 普通成员只保留账户设置，不展示系统管理分组
    items.push({ key: '/System/Account', label: '账户设置' })
    return items
  }
  items.push({
    key: 'system',
    label: '系统管理',
    children: [
      { key: '/System/Account', label: '账户设置' },
      { key: '/System/Settings', label: '系统设置' },
      { key: '/System/User', label: '用户管理' },
      { key: '/System/Role', label: '角色管理' },
      { key: '/System/Organization', label: '组织管理' },
      { key: '/System/BaseCode', label: '字典管理' },
    ],
  })
  return items
})

const mobileTabs = [
  { key: '/Main/Today', label: '今天', path: '/Main/Today' },
  { key: '/Main/Timeline', label: '时间线', path: '/Main/Timeline' },
  { key: '/Main/Stats', label: '统计', path: '/Main/Stats' },
  { key: '/System/Account', label: '我的', path: '/System/Account' },
]

const userMenu = computed(() => ({
  items: [
    { key: 'account', label: '账户设置' },
    { type: 'divider' },
    { key: 'logout', label: '退出登录' },
  ],
  onClick: onUserMenu,
}))

function toggleCollapse() {
  store.commit('app/setCollapsed', !store.state.app.collapsed)
}

function onMenuClick({ key }) {
  if (String(key).startsWith('/')) router.push(key)
}

async function onUserMenu({ key }) {
  if (key === 'account') {
    router.push('/System/Account')
    return
  }
  if (key === 'logout') {
    await store.dispatch('auth/logout')
    router.push('/Login')
  }
}

function syncViewport() {
  store.commit('app/setMobile', window.innerWidth < 768)
}

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
  store.dispatch('dict/load')
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport)
})
</script>

<style scoped lang="less">
.app-layout {
  min-height: 100vh;
  background: var(--app-bg-body);
}

.app-sider {
  border-right: 1px solid var(--app-border);
  background: var(--app-bg-container);
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid var(--app-border);
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  color: #fff;
  font-weight: 700;
  background: linear-gradient(135deg, #2090ff, #7e57ff);
}

.brand-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--app-text-1);
  white-space: nowrap;
}

.app-header {
  height: 50px;
  line-height: 50px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--app-bg-container);
  border-bottom: 1px solid var(--app-border);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 15px;
  color: var(--app-text-1);
}

.icon-button {
  border: none;
  background: transparent;
  color: var(--app-text-2);
  font-size: 16px;
  cursor: pointer;
}

.user-button {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--app-text-1);
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--app-primary-weak);
  color: var(--app-primary);
  font-size: 13px;
  font-weight: 600;
}

.user-name {
  font-size: 13px;
}

.app-content {
  background: var(--app-bg-body);
  min-height: calc(100vh - 50px);
}

.mobile-tabs {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: 58px;
  display: flex;
  background: var(--app-bg-container);
  border-top: 1px solid var(--app-border);
  z-index: 20;

  button {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    border: none;
    background: transparent;
    color: var(--app-text-3);
    font-size: 11px;

    &.active {
      color: var(--app-primary);
    }
  }
}

.tab-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
</style>
