<template>
  <div class="not-found">
    <h1>404</h1>
    <p>这里没有记录，也许是走错了路。</p>
    <a-button type="primary" @click="$router.push('/Main/Today')">回到今天</a-button>
  </div>
</template>

<style scoped>
.not-found {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: var(--app-bg-body);
  color: var(--app-text-1);
}

.not-found h1 {
  font-size: 64px;
  margin: 0;
  color: var(--app-primary);
}
</style>
