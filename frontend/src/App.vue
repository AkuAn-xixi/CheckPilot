<template>
  <div class="app-shell">
    <div class="app-orb app-orb-left"></div>
    <div class="app-orb app-orb-right"></div>
    <div class="app-grid"></div>

    <header class="app-topbar">
      <div class="app-topbar-inner">
        <div class="brand-cluster">
          <div class="brand-mark" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div>
            <p class="eyebrow">Precision Automation Workspace</p>
            <h1 class="brand-title">ADB 控制中心</h1>
          </div>
        </div>

        <div class="topbar-summary">
          <div class="topbar-pill">
            <span class="pill-label">当前模块</span>
            <strong>{{ currentSection.label }}</strong>
            <span class="pill-value">{{ currentSection.description }}</span>
          </div>
          <div class="topbar-pill" :class="{ idle: !currentDevice }">
            <span class="pill-label">设备连接</span>
            <strong>{{ currentDevice ? '已连接' : '等待选择' }}</strong>
            <span class="pill-value">{{ currentDevice || '未选择设备' }}</span>
          </div>
        </div>
      </div>
    </header>

    <main class="app-main">
      <aside class="app-sidebar">
        <section class="card sidebar-panel">
          <div class="sidebar-header">
            <p class="eyebrow">Navigation</p>
            <h2 class="sidebar-title">工作台</h2>
          </div>
          <nav class="nav-stack">
            <router-link
              v-for="(item, index) in navItems"
              :key="item.to"
              :to="item.to"
              class="nav-link"
              active-class="active"
            >
              <span class="nav-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="nav-copy">
                <span class="nav-link-title">{{ item.label }}</span>
                <span class="nav-link-desc">{{ item.description }}</span>
              </span>
            </router-link>
          </nav>
        </section>
      </aside>

      <section class="app-content">
        <router-view />
      </section>
    </main>

    <footer class="app-footer">
      <span>ADB Control Tool v1.1.0</span>
      <span>{{ currentDevice ? `当前设备：${currentDevice}` : statusMessage }}</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

const currentDevice = ref('')
const statusMessage = ref('系统就绪')
const route = useRoute()

const navItems = [
  { to: '/', label: '首页', description: '查看设备总览与常用入口' },
  { to: '/devices', label: '设备管理', description: '连接、刷新并锁定目标设备' },
  { to: '/commands', label: '命令执行', description: '直接发送 ADB 指令与序列' },
  { to: '/excel', label: 'Excel 执行', description: '从用例表驱动步骤与截图校验' },
  { to: '/keymonitor', label: '按键监听', description: '采集遥控器事件并清洗映射' }
]

const currentSection = computed(() => {
  return navItems.find((item) => item.to === route.path) || navItems[0]
})

const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    currentDevice.value = data.device || ''
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
}

onMounted(async () => {
  await loadCurrentDevice()
})
</script>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
  padding: 24px;
  overflow: hidden;
}

.app-orb {
  position: absolute;
  border-radius: 9999px;
  pointer-events: none;
  filter: blur(48px);
  opacity: 0.8;
}

.app-orb-left {
  width: 420px;
  height: 420px;
  top: -120px;
  left: -100px;
  background: rgba(10, 132, 255, 0.24);
}

.app-orb-right {
  width: 360px;
  height: 360px;
  top: 120px;
  right: -80px;
  background: rgba(125, 211, 252, 0.22);
}

.app-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.28;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.12) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.5), transparent 85%);
}

.app-topbar,
.app-main,
.app-footer {
  position: relative;
  z-index: 1;
  max-width: 1480px;
  margin-left: auto;
  margin-right: auto;
}

.app-topbar {
  margin-bottom: 24px;
}

.app-topbar-inner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 20px 24px;
  border-radius: 30px;
  border: 1px solid rgba(255, 255, 255, 0.66);
  background: rgba(255, 255, 255, 0.58);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(24px);
}

.brand-cluster {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand-mark {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  width: 56px;
  height: 56px;
  padding: 8px;
  border-radius: 18px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95), rgba(226, 232, 240, 0.65));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92), 0 18px 40px rgba(15, 23, 42, 0.12);
}

.brand-mark span {
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(10, 132, 255, 0.98), rgba(0, 113, 227, 0.7));
}

.brand-mark span:last-child {
  grid-column: span 2;
}

.brand-title {
  margin-top: 4px;
  font-size: clamp(1.8rem, 2.4vw, 2.45rem);
  line-height: 1.02;
  letter-spacing: -0.05em;
}

.topbar-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: min(100%, 560px);
}

.topbar-pill {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 14px 16px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.72);
}

.topbar-pill.idle {
  border-color: rgba(245, 158, 11, 0.25);
  background: rgba(255, 251, 235, 0.72);
}

.pill-label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #6b7280;
}

.pill-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #6b7280;
}

.app-main {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.app-sidebar {
  position: sticky;
  top: 24px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.sidebar-panel {
  padding: 22px;
}

.sidebar-title {
  margin-top: 8px;
  font-size: 1.45rem;
  letter-spacing: -0.04em;
}

.nav-stack {
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nav-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.05);
  color: #6b7280;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.nav-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.nav-link.active .nav-index {
  background: rgba(0, 113, 227, 0.12);
  color: #0071e3;
}

.nav-link-desc {
  color: #6b7280;
  line-height: 1.5;
}

.app-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.app-footer {
  margin-top: 24px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 0 6px;
  color: #6b7280;
  font-size: 0.88rem;
}

@media (max-width: 1100px) {
  .app-main {
    grid-template-columns: 1fr;
  }

  .app-sidebar {
    position: static;
  }
}

@media (max-width: 820px) {
  .app-shell {
    padding: 16px;
  }

  .app-topbar-inner,
  .sidebar-header {
    flex-direction: column;
  }

  .topbar-summary {
    width: 100%;
    min-width: 0;
    grid-template-columns: 1fr;
  }

  .app-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
