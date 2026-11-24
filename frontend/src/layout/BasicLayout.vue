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
        <span class="brand-mark"><AppIcon name="lucide:calendar-heart" :size="17" /></span>
        <span v-if="!collapsed" class="brand-name">每日记录</span>
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
            <button type="button" class="user-button" :aria-label="`${username} 的菜单`">
              <span class="avatar" role="img" :aria-label="`${username}头像`">
                <img v-if="avatarUrl" :src="avatarUrl" alt="" />
                <template v-else>{{ initial }}</template>
              </span>
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
        <AppIcon :name="resolveNavIcon(item.key)" :size="18" />
        {{ item.label }}
      </button>
    </nav>
  </a-layout>
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'

import AppIcon from '@/components/AppIcon.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'
import { resolveNavIcon } from '@/store/icon'

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
const avatarUrl = computed(() => store.state.auth.userInfo?.avatar || '')
const pageTitle = computed(() => route.meta?.title || '今天')

const selectedKeys = computed(() => {
  if (route.path.startsWith('/System')) {
    return [`/System/${route.name === 'Account' ? 'Account' : route.path.split('/').pop()}`]
  }
  return [route.path]
})

const isOwner = computed(() => store.getters['auth/isOwner'])

function menuIcon(path) {
  return h(AppIcon, { name: resolveNavIcon(path), size: 18 })
}

const menuItems = computed(() => {
  const items = [
    { key: '/Main/Today', label: '今天', icon: menuIcon('/Main/Today') },
    { key: '/Main/Timeline', label: '时间线', icon: menuIcon('/Main/Timeline') },
    { key: '/Main/Stats', label: '统计', icon: menuIcon('/Main/Stats') },
  ]
  if (!isOwner.value) {
    // 普通成员只保留账户设置，不展示系统管理分组
    items.push({ key: '/System/Account', label: '账户设置', icon: menuIcon('/System/Account') })
    return items
  }
  items.push({
    key: 'system',
    label: '系统管理',
    icon: h(AppIcon, { name: 'lucide:settings', size: 18 }),
    children: [
      { key: '/System/Account', label: '账户设置', icon: menuIcon('/System/Account') },
      { key: '/System/Settings', label: '系统设置', icon: menuIcon('/System/Settings') },
      { key: '/System/User', label: '用户管理', icon: menuIcon('/System/User') },
      { key: '/System/Role', label: '角色管理', icon: menuIcon('/System/Role') },
      {
        key: '/System/Organization',
        label: '组织管理',
        icon: menuIcon('/System/Organization'),
      },
      { key: '/System/BaseCode', label: '字典管理', icon: menuIcon('/System/BaseCode') },
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #2090ff, #7e57ff);
}

.brand-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--app-text-1);
  white-space: nowrap;
}

.app-header {
  height: 56px;
  line-height: 1;
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
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 8px;
  border: none;
  border-radius: var(--radius-pill);
  background: transparent;
  cursor: pointer;
  color: var(--app-text-1);
  line-height: 1;
  transition: background 0.2s;

  &:hover {
    background: var(--app-bg-elevated);
  }
}

.avatar {
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  line-height: 1;
  background: linear-gradient(135deg, var(--app-primary), #7e57ff);
  color: #fff;
  font-size: 13px;
  font-weight: 600;

  img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }
}

.user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.app-content {
  background: var(--app-bg-body);
  min-height: calc(100vh - 56px);
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
</style>
