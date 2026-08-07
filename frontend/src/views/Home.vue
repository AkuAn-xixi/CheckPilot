<template>
  <div>
    <section class="card home-hero">
      <div class="home-hero-grid">
        <div>
          <p class="eyebrow">{{ $t('home.eyebrow') }}</p>
          <h2 class="home-title">{{ $t('home.title') }}</h2>
          <p class="home-subtitle">
            {{ $t('home.subtitle') }}
          </p>

          <div class="home-actions">
            <router-link v-if="currentDevice" to="/excel" class="btn btn-primary">
              {{ $t('home.continueExcel') }}
            </router-link>
            <button v-else type="button" class="btn btn-primary" @click="scrollToDeviceHub">
              {{ $t('home.selectDeviceFirst') }}
            </button>
            <button type="button" class="btn btn-ghost" @click="showChangelog = true">
              {{ $t('home.changelog') }}
            </button>
          </div>
        </div>

        <div class="hero-stack">
          <article ref="deviceHubPanel" class="hero-card hero-card-soft device-hub-card">
            <div class="hero-card-header">
              <span class="hero-label">{{ $t('home.deviceHub') }}</span>

              <button
                type="button"
                class="btn btn-secondary hero-action-btn"
                :disabled="loading || Boolean(selectingDevice)"
                @click="refreshDevicePanel"
              >
                {{ loading ? $t('common.refreshing') : $t('deviceManagement.refresh') }}
              </button>
            </div>

            <div v-if="loading" class="device-empty-state">
              {{ $t('common.loading') }}
            </div>

            <div v-else-if="devices.length" class="device-list">
              <article
                v-for="(device, index) in devices"
                :key="device"
                class="device-list-item"
                :class="{ 'device-list-item-active': currentDevice === device }"
              >
                <div class="device-list-copy">
                  <div class="device-list-heading">
                    <span class="device-index">{{ String(index + 1).padStart(2, '0') }}</span>
                    <span v-if="currentDevice === device" class="device-badge">
                      {{ $t('home.currentDeviceTag') }}
                    </span>
                  </div>
                  <strong class="device-name">{{ device }}</strong>
                </div>

                <button
                  type="button"
                  class="btn"
                  :class="currentDevice === device ? 'btn-secondary' : 'btn-primary'"
                  :disabled="currentDevice === device || selectingDevice === device"
                  @click="selectDevice(index, device)"
                >
                  {{
                    selectingDevice === device
                      ? $t('common.loading')
                      : currentDevice === device
                        ? $t('home.currentDeviceTag')
                        : $t('home.selectThisDevice')
                  }}
                </button>
              </article>
            </div>

            <div v-else class="device-empty-state">
              {{ $t('home.noDevicesInline') }}
            </div>
          </article>

          <article class="hero-card login-card">
            <div class="login-card-heading">
              <span class="hero-label">{{ $t('home.remoteLogin') }}</span>
            </div>

            <strong class="login-card-title">{{ $t('home.remoteLoginTitle') }}</strong>

            <div v-if="platformAuthLoading" class="login-status-panel login-status-panel-muted">
              {{ $t('common.loading') }}
            </div>

            <div v-else-if="platformAuthAuthenticated" class="login-status-panel">
              <span class="login-status-label">{{ $t('app.platformLoggedIn') }}</span>
              <div class="login-status-username">{{ platformAuthUsername }}</div>
              <p class="login-status-copy">{{ $t('home.remoteLoginSuccessSaved', { username: platformAuthUsername }) }}</p>

              <button
                type="button"
                class="btn btn-secondary login-submit"
                :disabled="logoutLoading"
                @click="logoutPlatformAuth"
              >
                {{ logoutLoading ? $t('home.remoteLogoutSubmitting') : $t('home.remoteLogoutSubmit') }}
              </button>
            </div>

            <form v-else class="login-form" @submit.prevent="submitPlatformLogin">
              <label class="login-field">
                <span class="login-field-label">{{ $t('home.remoteLoginUsername') }}</span>
                <input
                  v-model.trim="loginUsername"
                  class="login-input"
                  type="text"
                  autocomplete="username"
                  :placeholder="$t('home.remoteLoginUsernamePlaceholder')"
                >
              </label>

              <label class="login-field">
                <span class="login-field-label">{{ $t('home.remoteLoginPassword') }}</span>
                <input
                  v-model="loginPassword"
                  class="login-input"
                  type="password"
                  autocomplete="current-password"
                  :placeholder="$t('home.remoteLoginPasswordPlaceholder')"
                >
              </label>

              <button
                type="submit"
                class="btn btn-primary login-submit"
                :disabled="loginLoading || !loginUsername.trim() || !loginPassword"
              >
                {{ loginLoading ? $t('home.remoteLoginSubmitting') : $t('home.remoteLoginSubmit') }}
              </button>
            </form>
          </article>
        </div>
      </div>

      <div class="home-stat-grid">
        <article class="stat-card">
          <span class="stat-label">{{ $t('home.workspaceStatus') }}</span>
          <strong>{{ currentDevice ? $t('home.readyTitle') : $t('home.needsSetupTitle') }}</strong>
          <p>{{ currentDevice ? $t('home.workspaceReadyDescription') : $t('home.workspaceNeedsSetupDescription') }}</p>
        </article>

        <article class="stat-card">
          <span class="stat-label">{{ $t('home.recommendedEntry') }}</span>
          <strong>{{ currentDevice ? $t('home.excelExecution') : $t('home.deviceHub') }}</strong>
          <p>{{ currentDevice ? $t('home.excelExecutionDescription') : $t('home.deviceHubDescription') }}</p>
        </article>

        <article class="stat-card">
          <span class="stat-label">{{ $t('home.resultReview') }}</span>
          <strong>{{ $t('home.resultReviewTitle') }}</strong>
          <p>{{ $t('home.resultReviewDescription') }}</p>
        </article>
      </div>
    </section>

    <div v-if="showChangelog" class="changelog-backdrop" @click.self="dismissChangelog">
      <div class="changelog-modal">
        <div class="changelog-header">
          <h4 class="changelog-title">{{ $t('home.changelogTitle') }}</h4>
          <button type="button" class="changelog-close" @click="dismissChangelog">&times;</button>
        </div>
        <div class="changelog-body">
          <div v-if="changelog.length === 0" class="changelog-empty">
            {{ $t('home.changelogEmpty') }}
          </div>
          <div v-for="entry in changelog" :key="entry.version" class="changelog-entry">
            <div class="changelog-entry-header">
              <span class="changelog-version">{{ $t('home.changelogVersion', { version: entry.version }) }}</span>
              <span class="changelog-date">{{ $t('home.changelogDate', { date: entry.date }) }}</span>
            </div>
            <ul class="changelog-list">
              <li v-for="(item, idx) in (entry.changes[locale] || entry.changes['zh-CN'] || [])" :key="idx">
                {{ item }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import changelogData from '../data/changelog.json'
import { showAlert as alert } from '../stores/dialogStore'

const DEVICE_STATUS_EVENT = 'checkpilot:device-updated'
const PLATFORM_AUTH_EVENT = 'checkpilot:platform-auth-updated'
const DEVICE_PANEL_QUERY_VALUE = 'device-hub'
const devices = ref([])
const currentDevice = ref('')
const deviceHubPanel = ref(null)
const loading = ref(false)
const selectingDevice = ref('')
const loginUsername = ref('')
const loginPassword = ref('')
const loginLoading = ref(false)
const logoutLoading = ref(false)
const platformAuthLoading = ref(false)
const platformAuthAuthenticated = ref(false)
const platformAuthUsername = ref('')
const route = useRoute()
const { t, locale } = useI18n({ useScope: 'global' })
const CHANGELOG_SEEN_KEY = 'checkpilot.changelogSeenVersion'
const showChangelog = ref(false)
const changelog = ref(Array.isArray(changelogData) ? changelogData : [])

const latestChangelogVersion = () => {
  if (!Array.isArray(changelogData) || changelogData.length === 0) return ''
  return changelogData[0].version || ''
}

const dismissChangelog = () => {
  showChangelog.value = false
  try {
    localStorage.setItem(CHANGELOG_SEEN_KEY, latestChangelogVersion())
  } catch {}
}

const checkAutoShowChangelog = () => {
  const latest = latestChangelogVersion()
  if (!latest) return
  try {
    const seen = localStorage.getItem(CHANGELOG_SEEN_KEY)
    if (seen !== latest) {
      showChangelog.value = true
    }
  } catch {
    showChangelog.value = true
  }
}

const extractLoginMessage = (payload, fallback) => {
  const candidates = [
    payload?.message,
    typeof payload?.detail === 'string' ? payload.detail : '',
    payload?.data?.message,
    typeof payload?.data?.detail === 'string' ? payload.data.detail : '',
    payload?.data?.error,
    payload?.error,
    payload?.msg,
    payload?.data?.msg
  ]

  return candidates.find((item) => typeof item === 'string' && item.trim()) || fallback
}

const notifyCurrentDeviceChange = (device = currentDevice.value || '') => {
  window.dispatchEvent(new CustomEvent(DEVICE_STATUS_EVENT, {
    detail: { device }
  }))
}

const notifyPlatformAuthStatusChange = () => {
  window.dispatchEvent(new CustomEvent(PLATFORM_AUTH_EVENT))
}

const applyPlatformAuthStatus = (payload) => {
  platformAuthAuthenticated.value = Boolean(payload?.authenticated)
  platformAuthUsername.value = payload?.authenticated ? payload.username || '' : ''
}

const scrollToDeviceHub = () => {
  deviceHubPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const scrollToRequestedPanel = async () => {
  if (route.query.panel !== DEVICE_PANEL_QUERY_VALUE) {
    return
  }

  await nextTick()
  scrollToDeviceHub()
}

const refreshDevicePanel = async () => {
  await Promise.all([loadDevices(), loadCurrentDevice()])
  notifyCurrentDeviceChange()
}

const FETCH_TIMEOUT_MS = 8000

const fetchWithTimeout = async (input, init = {}, timeoutMs = FETCH_TIMEOUT_MS) => {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

const loadPlatformAuthStatus = async () => {
  console.log('[PlatformAuth] 开始加载认证状态...')
  platformAuthLoading.value = true

  try {
    const response = await fetchWithTimeout('/api/platform-auth/status')
    console.log(`[PlatformAuth] 状态接口响应: status=${response.status}, ok=${response.ok}`)

    const payload = await response.json().catch((parseErr) => {
      console.error('[PlatformAuth] 状态响应JSON解析失败:', parseErr)
      return {}
    })
    console.log(`[PlatformAuth] 状态响应数据:`, payload)

    if (!response.ok) {
      console.warn(`[PlatformAuth] 状态接口返回非OK: ${response.status}`)
      applyPlatformAuthStatus({ authenticated: false })
      return
    }

    console.log(`[PlatformAuth] 认证状态: authenticated=${payload?.authenticated}, username=${payload?.username}`)
    applyPlatformAuthStatus(payload)
  } catch (error) {
    console.error('[PlatformAuth] 加载认证状态失败:', error?.message || error)
    console.error('[PlatformAuth] 错误类型:', error?.name)
    if (error?.name === 'AbortError') {
      console.error('[PlatformAuth] 请求超时')
    }
    applyPlatformAuthStatus({ authenticated: false })
  } finally {
    platformAuthLoading.value = false
  }
}

const handlePlatformAuthStatusChange = () => {
  void loadPlatformAuthStatus()
}

onMounted(async () => {
  window.addEventListener(PLATFORM_AUTH_EVENT, handlePlatformAuthStatusChange)
  await Promise.all([refreshDevicePanel(), loadPlatformAuthStatus()])
  await scrollToRequestedPanel()
  checkAutoShowChangelog()
})

onBeforeUnmount(() => {
  window.removeEventListener(PLATFORM_AUTH_EVENT, handlePlatformAuthStatusChange)
})

watch(
  () => route.query.panel,
  async (panel) => {
    if (panel !== DEVICE_PANEL_QUERY_VALUE) {
      return
    }

    await scrollToRequestedPanel()
  }
)

const loadDevices = async () => {
  loading.value = true
  try {
    const response = await fetchWithTimeout('/api/devices/list')
    const data = await response.json()
    devices.value = Array.isArray(data.devices) ? data.devices : []
  } catch (error) {
    devices.value = []
    console.error(t('deviceManagement.alerts.failed', { detail: error?.message || error }), error)
  } finally {
    loading.value = false
  }
}

const loadCurrentDevice = async () => {
  try {
    const response = await fetchWithTimeout('/api/devices/current')
    const data = await response.json()
    currentDevice.value = data.device || ''
  } catch (error) {
    currentDevice.value = ''
    console.error('Failed to get current device:', error)
  }
}

const selectDevice = async (index, device) => {
  selectingDevice.value = device

  try {
    const response = await fetchWithTimeout('/api/devices/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ device_index: index })
    })
    const data = await response.json()

    if (!response.ok || data.status !== 'success') {
      await alert(t('deviceManagement.alerts.failed', { detail: data.detail || t('deviceManagement.alerts.unknown') }))
      return
    }

    await refreshDevicePanel()
  } catch (error) {
    console.error('Failed to select device:', error)
    await alert(t('deviceManagement.alerts.retry'))
  } finally {
    selectingDevice.value = ''
  }
}

const submitPlatformLogin = async () => {
  if (!loginUsername.value.trim() || !loginPassword.value) {
    console.warn('[PlatformAuth Login] 表单校验失败: 用户名或密码为空')
    await alert(t('home.remoteLoginFormRequired'))
    return
  }

  const username = loginUsername.value.trim()
  console.log(`[PlatformAuth Login] ========== 登录流程开始 ==========`)
  console.log(`[PlatformAuth Login] 用户名: ${username}, 密码长度: ${loginPassword.value.length}`)

  loginLoading.value = true

  try {
    console.log('[PlatformAuth Login] 发送登录请求到 /api/platform-auth/login...')
    const startTime = Date.now()

    const response = await fetch('/api/platform-auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: username,
        password: loginPassword.value
      })
    })

    const elapsed = Date.now() - startTime
    console.log(`[PlatformAuth Login] 响应收到: status=${response.status}, ok=${response.ok}, 耗时=${elapsed}ms`)

    const payload = await response.json().catch((parseErr) => {
      console.error('[PlatformAuth Login] 响应JSON解析失败:', parseErr)
      return {}
    })
    console.log(`[PlatformAuth Login] 响应数据:`, {
      status: payload?.status,
      upstream_status: payload?.upstream_status,
      token_saved: payload?.token_saved,
      saved_username: payload?.saved_username,
      hasData: !!payload?.data
    })

    if (!response.ok || payload?.status !== 'success') {
      const errorMsg = extractLoginMessage(payload, t('home.remoteLoginFailed'))
      console.error(`[PlatformAuth Login] 登录失败: ${errorMsg}`)
      console.error(`[PlatformAuth Login] 完整响应:`, payload)
      await alert(errorMsg)
      return
    }

    loginPassword.value = ''
    if (payload?.token_saved) {
      console.log(`[PlatformAuth Login] 登录成功，token已保存，通知状态更新`)
      console.log(`[PlatformAuth Login] ========== 登录流程结束(成功) ==========`)
      notifyPlatformAuthStatusChange()
      return
    }

    console.warn('[PlatformAuth Login] 登录成功但token未保存!')
    console.warn('[PlatformAuth Login] 上游响应数据:', payload?.data)
    await alert(t('home.remoteLoginSuccessNoToken'))
  } catch (error) {
    console.error('[PlatformAuth Login] ========== 登录流程异常 ==========')
    console.error('[PlatformAuth Login] 异常类型:', error?.name)
    console.error('[PlatformAuth Login] 异常信息:', error?.message || error)
    if (error?.name === 'AbortError') {
      console.error('[PlatformAuth Login] 请求超时')
    }
    if (error?.cause) {
      console.error('[PlatformAuth Login] 原始异常:', error.cause)
    }
    await alert(t('home.remoteLoginRetry'))
  } finally {
    loginLoading.value = false
    console.log('[PlatformAuth Login] loading状态已重置')
  }
}

const logoutPlatformAuth = async () => {
  console.log('[PlatformAuth Logout] ========== 退出登录开始 ==========')
  logoutLoading.value = true

  try {
    console.log('[PlatformAuth Logout] 发送退出请求到 /api/platform-auth/logout...')
    const response = await fetch('/api/platform-auth/logout', {
      method: 'POST'
    })
    console.log(`[PlatformAuth Logout] 响应: status=${response.status}, ok=${response.ok}`)

    const payload = await response.json().catch((parseErr) => {
      console.error('[PlatformAuth Logout] 响应JSON解析失败:', parseErr)
      return {}
    })

    if (!response.ok || payload?.status !== 'success') {
      const errorMsg = extractLoginMessage(payload, t('home.remoteLogoutFailed'))
      console.error(`[PlatformAuth Logout] 退出失败: ${errorMsg}`)
      await alert(errorMsg)
      return
    }

    console.log('[PlatformAuth Logout] 退出成功，清除本地状态')
    loginPassword.value = ''
    applyPlatformAuthStatus({ authenticated: false })
    notifyPlatformAuthStatusChange()
    console.log('[PlatformAuth Logout] ========== 退出登录结束(成功) ==========')
  } catch (error) {
    console.error('[PlatformAuth Logout] ========== 退出登录异常 ==========')
    console.error('[PlatformAuth Logout] 异常:', error?.message || error)
    await alert(t('home.remoteLogoutRetry'))
  } finally {
    logoutLoading.value = false
  }
}
</script>

<style scoped>
.home-hero {
  overflow: hidden;
}

.home-hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(300px, 0.75fr);
  gap: 20px;
  align-items: start;
}

.home-title {
  margin-top: 8px;
  max-width: 13ch;
  font-size: clamp(2.1rem, 4.4vw, 4rem);
  line-height: 0.98;
  letter-spacing: -0.06em;
}

.home-subtitle {
  margin-top: 14px;
  max-width: 62ch;
  color: #4b5563;
  font-size: 0.98rem;
  line-height: 1.68;
}

.home-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}

.hero-stack {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.hero-card {
  padding: 20px;
  border-radius: 28px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.62));
  border: 1px solid rgba(255, 255, 255, 0.75);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95), 0 18px 40px rgba(15, 23, 42, 0.08);
}

.hero-card-soft {
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.9), rgba(255, 255, 255, 0.7));
}

.hero-card strong {
  display: block;
  margin-top: 8px;
  font-size: 1.55rem;
  letter-spacing: -0.04em;
}

.hero-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.hero-action-btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.hero-card p {
  margin-top: 8px;
  color: #6b7280;
  line-height: 1.62;
}

.device-hub-card {
  display: grid;
  gap: 14px;
}

.login-card {
  display: grid;
  gap: 12px;
  background: linear-gradient(180deg, rgba(255, 248, 238, 0.92), rgba(255, 255, 255, 0.78));
}

.login-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.login-card-title {
  margin-top: 0;
  font-size: 1.26rem;
  line-height: 1.15;
}

.login-card-description {
  margin-top: 0;
  color: #6b7280;
}

.login-form {
  display: grid;
  gap: 12px;
}

.login-status-panel {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.login-status-panel-muted {
  color: #6b7280;
}

.login-status-label {
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: #6b7280;
}

.login-status-username {
  font-size: 1.2rem;
  font-weight: 700;
  color: #111827;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.login-status-copy {
  margin: 0;
  color: #4b5563;
}

.login-field {
  display: grid;
  gap: 6px;
}

.login-field-label {
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: #6b7280;
}

.login-input {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  color: #111827;
  font: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.login-input:focus {
  outline: none;
  border-color: rgba(59, 130, 246, 0.42);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
}

.login-submit {
  width: 100%;
}

.device-list {
  display: grid;
  gap: 12px;
  max-height: 260px;
  overflow: auto;
  padding-right: 4px;
}

.device-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.device-list-item-active {
  border-color: rgba(59, 130, 246, 0.28);
  background: rgba(239, 246, 255, 0.88);
}

.device-list-copy {
  min-width: 0;
}

.device-list-heading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.device-name {
  display: block;
  margin-top: 8px;
  font-size: 0.86rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.device-list-item .btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.device-empty-state {
  margin-top: 16px;
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px dashed rgba(148, 163, 184, 0.28);
  color: #6b7280;
  line-height: 1.6;
}

.hero-label,
.stat-label,
.feature-kicker,
.device-index {
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #6b7280;
}

.home-stat-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 16px 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.68);
}

.stat-card strong {
  display: block;
  margin-top: 8px;
  font-size: 1.12rem;
  letter-spacing: -0.03em;
}

.stat-card p,
.feature-card p {
  margin-top: 6px;
  color: #6b7280;
  line-height: 1.58;
}

@media (max-width: 1100px) {
  .home-hero-grid,
  .home-stat-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .home-title {
    max-width: 100%;
  }

  .hero-card-header,
  .device-list-item {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-action-btn,
  .device-list-item .btn {
    width: 100%;
  }
}

.btn-ghost {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.3);
  color: #6b7280;
  padding: 10px 20px;
  border-radius: 14px;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.btn-ghost:hover {
  background: rgba(241, 245, 249, 0.8);
  border-color: rgba(148, 163, 184, 0.5);
  color: #334155;
}

.changelog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.changelog-modal {
  background: #fff;
  border-radius: 20px;
  width: 100%;
  max-width: 520px;
  max-height: 72vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.18);
  overflow: hidden;
}

.changelog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 0;
}

.changelog-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0;
}

.changelog-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  line-height: 1;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.15s ease, color 0.15s ease;
}

.changelog-close:hover {
  background: rgba(241, 245, 249, 0.8);
  color: #475569;
}

.changelog-body {
  padding: 16px 24px 24px;
  overflow-y: auto;
  flex: 1;
}

.changelog-empty {
  color: #94a3b8;
  font-size: 0.88rem;
  text-align: center;
  padding: 24px 0;
}

.changelog-entry {
  padding: 14px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
}

.changelog-entry:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.changelog-entry:first-child {
  padding-top: 0;
}

.changelog-entry-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.changelog-version {
  font-size: 0.82rem;
  font-weight: 700;
  color: #1e40af;
  background: rgba(239, 246, 255, 0.9);
  padding: 3px 10px;
  border-radius: 999px;
}

.changelog-date {
  font-size: 0.78rem;
  color: #94a3b8;
}

.changelog-list {
  margin: 0;
  padding: 0 0 0 18px;
  list-style: disc;
}

.changelog-list li {
  font-size: 0.86rem;
  color: #475569;
  line-height: 1.65;
  margin-bottom: 2px;
}
</style>
