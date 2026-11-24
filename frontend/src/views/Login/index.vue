<template>
  <div class="auth-shell">
    <FloatingLines />
    <div class="auth-actions">
      <ThemeSelect />
    </div>
    <div class="auth-card">
      <div class="auth-card-inner">
        <div class="logo">日</div>
        <h1 class="auth-title">每日照片记录</h1>
        <p class="auth-subtitle">每天一张照片，一句记忆点。登录后继续今天的记录。</p>

        <a-form layout="vertical" @submit.prevent="submit">
          <a-form-item label="账号或邮箱">
            <a-input
              v-model:value="form.identifier"
              size="large"
              placeholder="登录账号或邮箱"
              autocomplete="username"
              allow-clear
            />
          </a-form-item>
          <a-form-item label="密码">
            <a-input-password
              v-model:value="form.password"
              size="large"
              placeholder="请输入密码"
              autocomplete="current-password"
              @press-enter="submit"
            />
          </a-form-item>
          <div class="row-between remember-row">
            <a-checkbox v-model:checked="form.rememberMe">记住账号</a-checkbox>
            <router-link to="/Register">注册新账号</router-link>
          </div>
          <a-button type="primary" size="large" block :loading="loading" @click="submit">
            登录
          </a-button>
        </a-form>

        <p class="footnote">数据完全存储在自家服务器，仅你与家人可见。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { message } from 'antdv-next'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

import FloatingLines from '@/components/FloatingLines.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'

const router = useRouter()
const store = useStore()
const loading = ref(false)

const savedIdentifier = localStorage.getItem('dr:lastUser') || ''
const form = reactive({ identifier: savedIdentifier, password: '', rememberMe: true })

async function submit() {
  if (loading.value) return
  if (!form.identifier.trim() || !form.password) {
    message.warning('请填写账号和密码')
    return
  }
  loading.value = true
  try {
    await store.dispatch('auth/login', {
      identifier: form.identifier.trim(),
      password: form.password,
      rememberMe: form.rememberMe,
    })
    if (form.rememberMe) localStorage.setItem('dr:lastUser', form.identifier.trim())
    else localStorage.removeItem('dr:lastUser')
    await store.dispatch('dict/load')
    message.success('欢迎回来')
    router.push('/Main/Today')
  } catch (error) {
    message.error(error?.message || '登录失败，请检查账号和密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="less">
.logo {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(135deg, #2090ff, #7e57ff);
  margin-bottom: 14px;
}

.remember-row {
  margin-bottom: 18px;
}

.footnote {
  margin: 18px 0 0;
  font-size: 12px;
  color: var(--app-text-3);
  text-align: center;
}
</style>
