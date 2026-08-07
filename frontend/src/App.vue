<template>
  <div class="app-shell" :class="{ 'excel-feature-shell': isExcelFeatureFullscreen }">
    <div class="app-orb app-orb-left"></div>
    <div class="app-orb app-orb-right"></div>
    <div class="app-grid"></div>

    <div v-if="showLocaleSwitcher" class="locale-switcher" role="group" :aria-label="$t('app.language')">
      <button
        v-for="option in localeOptions"
        :key="option.value"
        type="button"
        class="locale-button"
        :class="{ active: locale === option.value }"
        @click="changeLocale(option.value)"
      >
        <span>{{ option.short }}</span>
        <small>{{ option.label }}</small>
      </button>
    </div>

    <header v-if="!isExcelFeatureFullscreen" class="app-topbar">
        <div class="app-topbar-inner">
          <div class="brand-cluster">
            <div class="brand-mark" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div>
              <p class="eyebrow">{{ $t('app.brandEyebrow') }}</p>
              <h1 class="brand-title">{{ $t('app.brandTitle') }}</h1>
            </div>
          </div>

          <div class="topbar-summary">
            <div class="topbar-pill">
              <span class="pill-label">{{ $t('app.currentSection') }}</span>
              <strong>{{ currentSection.label }}</strong>
              <span class="pill-value">{{ currentSection.description }}</span>
            </div>
            <div class="topbar-pill" :class="{ idle: !currentDevice }">
              <span class="pill-label">{{ $t('app.deviceConnection') }}</span>
              <strong>{{ currentDevice ? $t('app.connected') : $t('app.waitingSelection') }}</strong>
              <span class="pill-value">{{ currentDevice || $t('app.noDeviceSelected') }}</span>
            </div>
            <div class="topbar-pill" :class="{ idle: !platformAuthAuthenticated }">
              <span class="pill-label">{{ $t('app.platformAuth') }}</span>
              <strong>{{ platformAuthAuthenticated ? $t('app.platformLoggedIn') : $t('app.platformLoggedOut') }}</strong>
              <span class="pill-value">
                {{
                  platformAuthAuthenticated
                    ? $t('app.platformLoggedInAs', { username: platformAuthUsername })
                    : $t('app.platformLoginPending')
                }}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main class="app-main" :class="{ 'app-main-solo': isExcelFeatureFullscreen }">
        <aside v-if="!isExcelFeatureFullscreen" class="app-sidebar">
          <section class="card sidebar-panel">
            <div class="sidebar-header">
              <p class="eyebrow">{{ $t('app.navEyebrow') }}</p>
              <h2 class="sidebar-title">{{ $t('app.navTitle') }}</h2>
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

        <section class="app-content" :class="{ 'app-content-solo': isExcelFeatureFullscreen }">
          <router-view v-slot="{ Component }">
            <keep-alive :include="['ExcelFeatureLayout', 'ExcelExecution', 'ExcelAsrAutomation']">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </section>
      </main>

      <footer v-if="!isExcelFeatureFullscreen" class="app-footer">
        <span>AutoDeck 自动测控台 v1.1.1</span>
        <span>{{ currentDevice ? t('app.currentDevice', { device: currentDevice }) : statusMessage }}</span>
      </footer>

    <ExecutionProgressCard />
    <DialogHost />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { setLocale } from './i18n'
import ExecutionProgressCard from './components/ExecutionProgressCard.vue'
import DialogHost from './components/DialogHost.vue'
import { executionState } from './stores/executionStore'

const DEVICE_STATUS_EVENT = 'checkpilot:device-updated'
const PLATFORM_AUTH_EVENT = 'checkpilot:platform-auth-updated'
const currentDevice = ref('')
const platformAuthAuthenticated = ref(false)
const platformAuthUsername = ref('')
const route = useRoute()
const { t, locale } = useI18n({ useScope: 'global' })

const localeOptions = [
  { value: 'zh-CN', short: '中', label: '中文' },
  { value: 'en-US', short: 'EN', label: 'English' }
]

// 语言切换器只在首页显示，避免在功能页（设备/Excel/按键监听等）干扰用户操作；
// 执行任务进行中时右上角被进度卡片占用，也隐藏切换器避免重叠
const showLocaleSwitcher = computed(() => (
  route.path === '/'
  && !(executionState.activeType !== null && executionState.status !== 'idle')
))

const statusMessage = computed(() => t('app.systemReady'))

const sectionItems = computed(() => [
  { to: '/', label: t('app.nav.home.label'), description: t('app.nav.home.description') },
  { to: '/devices', label: t('app.nav.devices.label'), description: t('app.nav.devices.description') },
  { to: '/excel', label: t('app.nav.excel.label'), description: t('app.nav.excel.description') },
  { to: '/keymonitor', label: t('app.nav.keymonitor.label'), description: t('app.nav.keymonitor.description') },
  { to: '/reports', label: t('app.nav.reports.label'), description: t('app.nav.reports.description') },
  { to: '/customization', label: t('app.nav.customization.label'), description: t('app.nav.customization.description') }
])

const navItems = computed(() => sectionItems.value.filter((item) => item.to !== '/devices'))

const currentSection = computed(() => {
  if (route.path === '/') {
    return sectionItems.value[0]
  }

  return sectionItems.value.find((item) => route.path === item.to || route.path.startsWith(`${item.to}/`)) || sectionItems.value[0]
})

const isExcelFeatureFullscreen = computed(() => {
  return route.path.startsWith('/excel/cases')
    || route.path.startsWith('/excel/asr')
    || route.path.startsWith('/keymonitor')
})

const changeLocale = (value) => {
  setLocale(value)
}

const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    if (!response.ok) {
      currentDevice.value = ''
      return
    }

    const data = await response.json()
    currentDevice.value = data.device || ''
  } catch (error) {
    currentDevice.value = ''
    console.error('获取当前设备失败:', error)
  }
}

const loadPlatformAuthStatus = async () => {
  try {
    const response = await fetch('/api/platform-auth/status')
    if (!response.ok) {
      platformAuthAuthenticated.value = false
      platformAuthUsername.value = ''
      return
    }

    const data = await response.json()
    platformAuthAuthenticated.value = Boolean(data?.authenticated)
    platformAuthUsername.value = data?.authenticated ? data.username || '' : ''
  } catch (error) {
    platformAuthAuthenticated.value = false
    platformAuthUsername.value = ''
    console.error('获取平台登录状态失败:', error)
  }
}

const handleDeviceStatusChange = (event) => {
  if (typeof event?.detail?.device === 'string') {
    currentDevice.value = event.detail.device
    return
  }

  void loadCurrentDevice()
}

const handlePlatformAuthStatusChange = () => {
  void loadPlatformAuthStatus()
}

onMounted(async () => {
  window.addEventListener(DEVICE_STATUS_EVENT, handleDeviceStatusChange)
  window.addEventListener(PLATFORM_AUTH_EVENT, handlePlatformAuthStatusChange)
  await Promise.all([loadCurrentDevice(), loadPlatformAuthStatus()])
})

onBeforeUnmount(() => {
  window.removeEventListener(DEVICE_STATUS_EVENT, handleDeviceStatusChange)
  window.removeEventListener(PLATFORM_AUTH_EVENT, handlePlatformAuthStatusChange)
})

watch(
  () => route.fullPath,
  () => {
    void Promise.all([loadCurrentDevice(), loadPlatformAuthStatus()])
  }
)
</script>

<style scoped>
.app-shell {
  position: relative;
  box-sizing: border-box;
  min-height: 100dvh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: 18px 24px 14px;
  overflow: hidden;
}

.app-shell.excel-feature-shell {
  padding: 0;
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

.locale-switcher {
  position: fixed;
  top: 18px;
  right: 24px;
  z-index: 5;
  display: inline-flex;
  gap: 8px;
  padding: 8px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.62);
  box-shadow: 0 16px 44px rgba(15, 23, 42, 0.1);
  backdrop-filter: blur(18px);
}

.locale-button {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  padding: 8px 12px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: #475569;
  cursor: pointer;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.locale-button span {
  font-size: 0.92rem;
  font-weight: 700;
}

.locale-button small {
  font-size: 0.68rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.locale-button:hover {
  transform: translateY(-1px);
  background: rgba(241, 245, 249, 0.9);
}

.locale-button.active {
  background: linear-gradient(180deg, rgba(14, 165, 233, 0.18), rgba(59, 130, 246, 0.16));
  color: #0f172a;
}

.app-topbar,
.app-main,
.app-footer {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1480px;
  margin-left: auto;
  margin-right: auto;
}

.app-topbar {
  margin-bottom: 18px;
}

.app-topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  border-radius: 30px;
  border: 1px solid rgba(255, 255, 255, 0.66);
  background: rgba(255, 255, 255, 0.58);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(24px);
}

.brand-cluster {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  width: 48px;
  height: 48px;
  padding: 7px;
  border-radius: 16px;
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
  margin-top: 2px;
  font-size: clamp(1.55rem, 2vw, 2.1rem);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.topbar-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  min-width: min(100%, 780px);
}

.topbar-pill {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 10px 14px;
  border-radius: 20px;
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
  font-size: 0.88rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: break-word;
  color: #6b7280;
}

.app-main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
  overflow: visible;
}

.app-sidebar {
  position: sticky;
  top: 0;
  max-height: calc(100dvh - 160px);
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.sidebar-panel {
  padding: 22px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  flex: 1;
}

.sidebar-title {
  margin-top: 8px;
  font-size: 1.45rem;
  letter-spacing: -0.04em;
}

.nav-stack {
  margin-top: 18px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding-bottom: 4px;
}

.nav-stack::-webkit-scrollbar {
  width: 0;
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
  max-height: calc(100dvh - 160px);
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
  padding-right: 4px;
}

.app-content::-webkit-scrollbar {
  width: 5px;
}

.app-content::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 9999px;
}

.app-content::-webkit-scrollbar-track {
  background: transparent;
}

.app-footer {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 0 6px;
  color: #6b7280;
  font-size: 0.82rem;
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

  .locale-switcher {
    top: 12px;
    left: 12px;
    right: 12px;
    justify-content: center;
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

/* 全屏功能页（/excel/cases、/excel/asr、/keymonitor）：顶栏/侧栏/页脚隐藏，
   主内容区铺满整个应用外壳。放在样式末尾以覆盖 .app-main / .app-content 的默认值。 */
.app-main-solo {
  grid-template-columns: minmax(0, 1fr);
  align-items: stretch;
  max-width: none;
}

.app-content-solo {
  max-height: none;
}
</style>
