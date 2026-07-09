<template>
  <div class="excel-workspace">
    <section v-if="isDirectory" class="card excel-directory overflow-hidden">
      <div class="excel-directory-copy">
        <p class="eyebrow">{{ $t('excelDirectory.eyebrow') }}</p>
        <h2 class="excel-directory-title">{{ $t('excelDirectory.title') }}</h2>
        <p class="excel-directory-subtitle">
          {{ $t('excelDirectory.subtitle') }}
        </p>
      </div>

      <div class="excel-directory-grid">
        <button
          v-for="feature in features"
          :key="feature.to"
          type="button"
          class="feature-card directory-card"
          @click="openFeature(feature.to)"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{{ feature.tag }}</p>
              <h3 class="mt-2 text-lg font-semibold text-slate-900">{{ feature.label }}</h3>
              <p class="mt-2 text-sm leading-6 text-slate-600">{{ feature.description }}</p>
            </div>
            <span class="feature-index">{{ feature.index }}</span>
          </div>
          <div class="mt-5 flex items-center justify-between text-sm">
            <span class="text-slate-500">{{ feature.status }}</span>
            <span class="font-medium text-sky-700">{{ $t('excelDirectory.enterFeature') }}</span>
          </div>
        </button>
      </div>
    </section>

    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const { t } = useI18n({ useScope: 'global' })

const features = computed(() => [
  {
    index: '01',
    tag: 'Visual Check',
    label: t('excelDirectory.visualCheck.label'),
    description: t('excelDirectory.visualCheck.description'),
    status: t('excelDirectory.visualCheck.status'),
    to: '/excel/cases'
  },
  {
    index: '02',
    tag: 'Speech Validation',
    label: t('excelDirectory.speechValidation.label'),
    description: t('excelDirectory.speechValidation.description'),
    status: t('excelDirectory.speechValidation.status'),
    to: '/excel/asr'
  }
])

const isDirectory = computed(() => route.path === '/excel')

const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    if (!response.ok) {
      return ''
    }

    const data = await response.json().catch(() => ({}))
    return typeof data.device === 'string' ? data.device : ''
  } catch (error) {
    console.error('获取当前设备失败:', error)
    return ''
  }
}

const openFeature = async (to) => {
  const currentDevice = await loadCurrentDevice()
  if (!currentDevice) {
    alert(t('excelDirectory.alerts.selectDeviceFirst'))
    return
  }

  await router.push(to)
}
</script>

<style scoped>
.excel-workspace {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.excel-directory {
  padding: 24px;
}

.excel-directory-copy {
  max-width: 46rem;
}

.excel-directory-title {
  margin-top: 8px;
  font-size: clamp(1.8rem, 2.6vw, 2.5rem);
  line-height: 1;
  letter-spacing: -0.05em;
}

.excel-directory-subtitle {
  margin-top: 12px;
  font-size: 0.98rem;
  line-height: 1.65;
  color: #64748b;
}

.excel-directory-grid {
  margin-top: 20px;
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.feature-card {
  display: block;
  width: 100%;
  padding: 24px;
  border-radius: 28px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92), 0 18px 38px rgba(15, 23, 42, 0.08);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  appearance: none;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.directory-card {
  min-height: 220px;
}

.feature-card:hover {
  transform: translateY(-1px);
  border-color: rgba(14, 165, 233, 0.35);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92), 0 22px 42px rgba(14, 165, 233, 0.12);
}

.feature-card.active {
  border-color: rgba(14, 165, 233, 0.5);
  background: linear-gradient(180deg, rgba(240, 249, 255, 0.96), rgba(255, 255, 255, 0.9));
}

.feature-card:focus-visible {
  outline: 2px solid rgba(14, 165, 233, 0.35);
  outline-offset: 3px;
}

.feature-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  height: 52px;
  border-radius: 18px;
  background: rgba(226, 232, 240, 0.7);
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: #475569;
}

@media (max-width: 1200px) {
  .excel-directory-grid {
    grid-template-columns: 1fr;
  }
}
</style>