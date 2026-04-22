<template>
  <div class="space-y-6">
    <section class="card home-hero">
      <div class="home-hero-grid">
        <div>
          <p class="eyebrow">Automation Workspace</p>
          <h2 class="home-title">把设备控制、脚本执行和结果校验，收束到一个更干净的工作台。</h2>
          <p class="home-subtitle">
            从 ADB 连接、即时指令到 Excel 回放、截图比对和按键监听，整个流程都在一个连续界面里完成，减少反复切换和状态丢失。
          </p>

          <div class="home-actions">
            <router-link :to="currentDevice ? '/excel' : '/devices'" class="btn btn-primary">
              {{ currentDevice ? '继续执行 Excel 用例' : '先选择设备' }}
            </router-link>
            <router-link to="/commands" class="btn btn-secondary">
              打开命令执行
            </router-link>
          </div>
        </div>

        <div class="hero-stack">
          <article class="hero-card">
            <span class="hero-label">当前连接</span>
            <strong>{{ currentDevice || '未选择设备' }}</strong>
            <p>
              {{ currentDevice ? '设备已就绪，可以直接进入 Excel 执行或命令执行。' : '先在设备管理里绑定一个 ADB 设备，再开始后续流程。' }}
            </p>
          </article>

          <article class="hero-card hero-card-soft">
            <span class="hero-label">已检测设备</span>
            <strong>{{ devices.length }}</strong>
            <p>
              {{ devices.length ? '已发现可用设备，可在任意时刻切换控制目标。' : '当前没有发现在线设备，请检查 USB 调试、线缆和驱动。' }}
            </p>
          </article>
        </div>
      </div>

      <div class="home-stat-grid">
        <article class="stat-card">
          <span class="stat-label">工作区状态</span>
          <strong>{{ currentDevice ? 'Ready' : 'Needs Setup' }}</strong>
          <p>{{ currentDevice ? '当前设备已经连通，可以直接开始执行。' : '还差最后一步：先把设备连接到工作台。' }}</p>
        </article>

        <article class="stat-card">
          <span class="stat-label">推荐入口</span>
          <strong>{{ currentDevice ? 'Excel 执行' : '设备管理' }}</strong>
          <p>{{ currentDevice ? '最适合批量回放、截图采集和结果回看。' : '先建立稳定连接，再进入脚本执行和校验流程。' }}</p>
        </article>

        <article class="stat-card">
          <span class="stat-label">结果回看</span>
          <strong>截图 + 校验图</strong>
          <p>执行结束后可直接查看截图与参考图，不必再切去别的页面确认。</p>
        </article>
      </div>
    </section>

    <div class="grid grid-cols-1 xl:grid-cols-[1.15fr_.85fr] gap-6">
      <section class="card">
        <p class="eyebrow">Capabilities</p>
        <h3 class="section-title">把分散动作整理成一条顺滑的回归路径</h3>

        <div class="feature-grid">
          <article v-for="feature in features" :key="feature.title" class="feature-card">
            <span class="feature-kicker">{{ feature.kicker }}</span>
            <h4>{{ feature.title }}</h4>
            <p>{{ feature.description }}</p>
          </article>
        </div>
      </section>

      <section class="card">
        <p class="eyebrow">Live Devices</p>
        <h3 class="section-title">当前设备概览</h3>

        <div v-if="devices.length" class="device-list">
          <article
            v-for="(device, index) in devices"
            :key="device"
            class="device-item"
            :class="{ active: currentDevice === device }"
          >
            <div>
              <p class="device-index">设备 {{ String(index + 1).padStart(2, '0') }}</p>
              <strong>{{ device }}</strong>
            </div>
            <span class="device-badge">{{ currentDevice === device ? '当前控制' : '可切换' }}</span>
          </article>
        </div>

        <div v-else class="empty-state">
          <p>还没有检测到 ADB 设备。</p>
          <p class="text-sm text-gray-500">确认 USB 调试、驱动和线缆状态后，再刷新设备列表。</p>
        </div>

        <div class="home-actions mt-6">
          <router-link to="/devices" class="btn btn-secondary">管理设备</router-link>
          <router-link to="/keymonitor" class="btn btn-secondary">打开按键监听</router-link>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const devices = ref([])
const currentDevice = ref('')

const features = [
  {
    kicker: '01',
    title: '设备连接更直接',
    description: '统一查看当前可用设备，避免在执行前来回确认连接状态。'
  },
  {
    kicker: '02',
    title: '脚本回放更完整',
    description: '从 Excel 直接驱动指令、截图和图像校验，把执行与验证收在同一流程。'
  },
  {
    kicker: '03',
    title: '结果回看更顺手',
    description: '执行完成后保留截图和参考图的对照关系，问题定位更快。'
  },
  {
    kicker: '04',
    title: '按键监听更清晰',
    description: '把采集、纠错和恢复动作放在一处，方便整理遥控器映射。'
  }
]

onMounted(async () => {
  await loadDevices()
  await loadCurrentDevice()
})

const loadDevices = async () => {
  try {
    const response = await fetch('/api/devices/list')
    const data = await response.json()
    devices.value = Array.isArray(data.devices) ? data.devices : []
  } catch (error) {
    devices.value = []
    console.error('获取设备列表失败:', error)
  }
}

const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    currentDevice.value = data.device || ''
  } catch (error) {
    console.error('获取当前设备失败:', error)
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
  gap: 24px;
  align-items: start;
}

.home-title {
  margin-top: 10px;
  max-width: 12ch;
  font-size: clamp(2.3rem, 5vw, 4.6rem);
  line-height: 0.98;
  letter-spacing: -0.06em;
}

.home-subtitle {
  margin-top: 18px;
  max-width: 62ch;
  color: #4b5563;
  font-size: 1.04rem;
  line-height: 1.8;
}

.home-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.hero-stack {
  display: grid;
  gap: 14px;
}

.hero-card {
  padding: 22px;
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
  margin-top: 10px;
  font-size: 1.7rem;
  letter-spacing: -0.04em;
}

.hero-card p {
  margin-top: 10px;
  color: #6b7280;
  line-height: 1.7;
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
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  padding: 18px 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.68);
}

.stat-card strong {
  display: block;
  margin-top: 10px;
  font-size: 1.2rem;
  letter-spacing: -0.03em;
}

.stat-card p,
.feature-card p {
  margin-top: 8px;
  color: #6b7280;
  line-height: 1.7;
}

.section-title {
  margin-top: 10px;
  margin-bottom: 18px;
  font-size: 1.55rem;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.feature-card {
  padding: 18px 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid rgba(255, 255, 255, 0.68);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.feature-card h4 {
  margin-top: 12px;
  font-size: 1.1rem;
}

.device-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 16px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.7);
}

.device-item strong {
  display: block;
  margin-top: 8px;
}

.device-item.active {
  background: linear-gradient(135deg, rgba(10, 132, 255, 0.12), rgba(255, 255, 255, 0.8));
  border-color: rgba(0, 113, 227, 0.16);
}

.device-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 88px;
  padding: 0.55rem 0.8rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #4b5563;
  font-size: 0.82rem;
  font-weight: 600;
}

.empty-state {
  padding: 18px 0 6px;
  color: #4b5563;
  line-height: 1.7;
}

@media (max-width: 1100px) {
  .home-hero-grid,
  .home-stat-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .feature-grid {
    grid-template-columns: 1fr;
  }

  .device-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
