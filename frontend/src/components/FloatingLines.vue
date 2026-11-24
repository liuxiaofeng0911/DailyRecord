<template>
  <div class="floating-lines" aria-hidden="true">
    <span v-for="index in 14" :key="index" :style="lineStyle(index)" />
  </div>
</template>

<script setup>
function lineStyle(index) {
  const duration = 14 + (index % 5) * 4
  const delay = -(index * 1.7)
  const top = (index * 7) % 100
  const opacity = 0.06 + (index % 4) * 0.03
  return {
    top: `${top}%`,
    animationDuration: `${duration}s`,
    animationDelay: `${delay}s`,
    opacity,
  }
}
</script>

<style scoped lang="less">
.floating-lines {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;

  span {
    position: absolute;
    left: -20%;
    width: 140%;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(32, 144, 255, 0.9),
      rgba(126, 87, 255, 0.6),
      transparent
    );
    animation-name: float-line;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
  }
}

@keyframes float-line {
  0% {
    transform: translateX(-12%) rotate(-8deg);
  }
  50% {
    transform: translateX(8%) rotate(-4deg);
  }
  100% {
    transform: translateX(-12%) rotate(-8deg);
  }
}
</style>
