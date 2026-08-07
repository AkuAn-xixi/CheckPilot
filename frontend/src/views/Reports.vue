<template>
  <div class="reports-page">

    <div v-if="pageError" class="card reports-alert reports-alert-error">
      {{ pageError }}
    </div>

    <section v-if="loadingReports" class="card reports-state-card">
      {{ $t('common.loading') }}
    </section>

    <section v-else-if="reportRows.length" class="card reports-table-card">
      <div class="reports-panel-header">
        <div>
          <p class="eyebrow">{{ $t('reports.list.eyebrow') }}</p>
          <h3>{{ $t('reports.list.title') }}</h3>
        </div>
        <div class="reports-panel-tools">
          <button
            type="button"
            class="btn btn-danger btn-sm"
            :disabled="selectedReportIds.length === 0 || deletingReports"
            @click="deleteSelectedReports"
          >
            {{ $t('reports.list.deleteSelected') }}<template v-if="selectedReportIds.length"> ({{ selectedReportIds.length }})</template>
          </button>
        </div>
      </div>

      <div class="reports-table-head">
        <span class="reports-check-cell">
          <input
            type="checkbox"
            :checked="allSelected"
            :title="$t('reports.list.selectAll')"
            @change="toggleSelectAll"
          >
        </span>
        <span>{{ $t('reports.list.columns.title') }}</span>
        <span>{{ $t('reports.list.columns.overview') }}</span>
        <span>{{ $t('reports.list.columns.metrics') }}</span>
        <span>{{ $t('reports.list.columns.actions') }}</span>
      </div>

      <div class="reports-table-body">
        <article v-for="item in reportRows" :key="item.report_id" class="reports-table-row">
          <div class="reports-check-cell">
            <input
              type="checkbox"
              :checked="isSelected(item.report_id)"
              :aria-label="item.title"
              @change="toggleSelect(item.report_id)"
            >
          </div>
          <div class="reports-title-cell">
            <strong>{{ item.title }}</strong>
            <p>{{ formatDate(item.updated_at) }} · {{ getReportKindLabel(item.kind) }}</p>
          </div>

          <div class="reports-overview-cell">
            <span :class="['reports-overview-pill', `reports-overview-pill-${item.overviewTone}`]">
              {{ item.overviewText }}
            </span>
          </div>

          <div class="reports-metrics-cell">
            <div class="reports-metric-item">
              <span>{{ $t('reports.detail.summary.total') }}</span>
              <strong>{{ item.summary.total }}</strong>
            </div>
            <div class="reports-metric-item">
              <span>{{ $t('reports.detail.summary.passed') }}</span>
              <strong>{{ item.summary.passed }}</strong>
            </div>
            <div class="reports-metric-item">
              <span>{{ $t('reports.detail.summary.failed') }}</span>
              <strong>{{ item.summary.failed }}</strong>
            </div>
            <div class="reports-metric-item">
              <span>{{ $t('reports.list.passRate') }}</span>
              <strong>{{ item.passRate }}</strong>
            </div>
          </div>

          <div class="reports-actions-cell">
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!item.report_url"
              @click="openReport(item.report_url)"
            >
              {{ $t('reports.detail.openHtml') }}
            </button>
            <button
              type="button"
              class="btn btn-danger"
              :disabled="deletingReportId === item.report_id"
              @click="deleteReport(item)"
            >
              {{ $t('common.delete') }}
            </button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showAlert as alert, showConfirm as confirm } from '../stores/dialogStore'

const reports = ref([])
const loadingReports = ref(false)
const refreshing = ref(false)
const deletingReportId = ref('')
const deletingReports = ref(false)
const selectedReportIds = ref([])
const pageError = ref('')
const { t } = useI18n({ useScope: 'global' })

const SUPPORTED_REPORT_KINDS = ['excel-batch', 'asr-batch']

const visibleReports = computed(() => {
  return reports.value.filter((item) => SUPPORTED_REPORT_KINDS.includes(item.kind))
})

const buildOverviewMeta = (summary) => {
  if (summary.failed > 0) {
    return {
      tone: 'fail',
      text: t('reports.list.overviewHasFailures', { count: summary.failed })
    }
  }
  if (summary.blocked > 0) {
    return {
      tone: 'warning',
      text: t('reports.list.overviewHasBlocked', { count: summary.blocked })
    }
  }
  if (summary.total > 0 && summary.passed === summary.total) {
    return {
      tone: 'pass',
      text: t('reports.list.overviewAllPassed')
    }
  }
  return {
    tone: 'muted',
    text: t('reports.list.overviewPending')
  }
}

const reportRows = computed(() => {
  return visibleReports.value.map((item) => {
    const summary = {
      total: Number(item.summary?.total || 0),
      passed: Number(item.summary?.passed || 0),
      failed: Number(item.summary?.failed || 0),
      blocked: Number(item.summary?.blocked || 0)
    }
    const passRate = summary.total > 0
      ? `${((summary.passed / summary.total) * 100).toFixed(2)}%`
      : '0.00%'
    const overview = buildOverviewMeta(summary)

    return {
      ...item,
      summary,
      passRate,
      overviewText: overview.text,
      overviewTone: overview.tone
    }
  })
})

const allSelected = computed(() => {
  return reportRows.value.length > 0 && selectedReportIds.value.length === reportRows.value.length
})

const readErrorMessage = async (response, fallbackMessage) => {
  try {
    const data = await response.json()
    return data.detail || data.message || fallbackMessage
  } catch {
    return fallbackMessage
  }
}

const formatDate = (value) => {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

const getReportKindLabel = (kind) => {
  if (kind === 'excel-batch') {
    return t('reports.groups.image.kindLabel')
  }
  if (kind === 'asr-batch') {
    return t('reports.groups.asr.kindLabel')
  }
  return kind || '-'
}

const loadReports = async () => {
  loadingReports.value = true
  try {
    const response = await fetch('/api/reports')
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('reports.alerts.loadReportsFailed')))
    }

    const data = await response.json()
    reports.value = Array.isArray(data.reports) ? data.reports : []
  } finally {
    loadingReports.value = false
  }
}

const refreshAll = async () => {
  refreshing.value = true
  pageError.value = ''
  try {
    await loadReports()
  } catch (error) {
    pageError.value = error instanceof Error ? error.message : t('reports.alerts.loadReportsFailed')
  } finally {
    refreshing.value = false
  }
}

const openReport = (url) => {
  if (!url) {
    return
  }

  window.open(url, '_blank', 'noopener')
}

const deleteReport = async (item) => {
  if (!item?.report_id) {
    return
  }

  const title = item.title || item.report_id
  if (!(await confirm(t('reports.alerts.deleteConfirm', { title })))) {
    return
  }

  deletingReportId.value = item.report_id
  pageError.value = ''

  try {
    const response = await fetch(`/api/reports/${encodeURIComponent(item.report_id)}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('reports.alerts.deleteReportFailed')))
    }

    reports.value = reports.value.filter((report) => report.report_id !== item.report_id)
    selectedReportIds.value = selectedReportIds.value.filter((id) => id !== item.report_id)
  } catch (error) {
    pageError.value = error instanceof Error ? error.message : t('reports.alerts.deleteReportFailed')
  } finally {
    deletingReportId.value = ''
  }
}

const isSelected = (reportId) => {
  return selectedReportIds.value.includes(reportId)
}

const toggleSelect = (reportId) => {
  selectedReportIds.value = selectedReportIds.value.includes(reportId)
    ? selectedReportIds.value.filter((id) => id !== reportId)
    : [...selectedReportIds.value, reportId]
}

const toggleSelectAll = () => {
  selectedReportIds.value = allSelected.value
    ? []
    : reportRows.value.map((item) => item.report_id)
}

const deleteSelectedReports = async () => {
  const count = selectedReportIds.value.length
  if (count === 0) {
    return
  }

  if (!(await confirm(t('reports.alerts.deleteBatchConfirm', { count })))) {
    return
  }

  deletingReports.value = true
  pageError.value = ''
  try {
    const response = await fetch('/api/reports/delete-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_ids: selectedReportIds.value })
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('reports.alerts.deleteBatchFailed')))
    }

    const data = await response.json()
    const deletedCount = Array.isArray(data.deleted) ? data.deleted.length : 0
    selectedReportIds.value = []
    await loadReports()

    if (deletedCount > 0) {
      await alert(t('reports.alerts.deleteBatchSuccess', { count: deletedCount }))
    }
  } catch (error) {
    pageError.value = error instanceof Error ? error.message : t('reports.alerts.deleteBatchFailed')
  } finally {
    deletingReports.value = false
  }
}

onMounted(async () => {
  await refreshAll()
})
</script>

<style scoped>
.reports-page {
  display: grid;
  gap: 20px;
}

.reports-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.reports-title {
  margin-top: 8px;
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.reports-subtitle {
  margin-top: 14px;
  max-width: 64ch;
  color: #4b5563;
  line-height: 1.68;
}

.reports-alert,
.reports-state-card {
  padding: 16px;
}

.reports-alert-error {
  border: 1px solid rgba(248, 113, 113, 0.28);
  background: rgba(254, 242, 242, 0.84);
  color: #b91c1c;
}

.reports-table-card {
  display: grid;
  gap: 18px;
}

.reports-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.reports-panel-header h3 {
  margin-top: 8px;
  font-size: 1.15rem;
  line-height: 1.2;
}

.reports-list-description {
  max-width: 28rem;
  margin: 0;
  color: #64748b;
  line-height: 1.6;
  text-align: right;
}

.reports-table-head,
.reports-table-row {
  display: grid;
  grid-template-columns: 44px minmax(260px, 1.35fr) minmax(180px, 0.9fr) minmax(300px, 1.2fr) auto;
  gap: 16px;
  align-items: center;
}

.reports-panel-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.reports-check-cell {
  display: flex;
  align-items: center;
  justify-content: center;
}

.reports-check-cell input[type='checkbox'] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #2563eb;
}

.reports-table-head {
  padding: 0 6px;
}

.reports-table-head span,
.reports-title-cell p,
.reports-metric-item span {
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  color: #6b7280;
}

.reports-table-head span,
.reports-metric-item span {
  text-transform: uppercase;
}

.reports-table-body {
  display: grid;
  gap: 12px;
}

.reports-table-row {
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.82);
}

.reports-title-cell {
  display: grid;
  gap: 8px;
}

.reports-title-cell strong {
  font-size: 1.02rem;
  color: #111827;
}

.reports-title-cell p,
.reports-list-description {
  margin: 0;
}

.reports-overview-cell {
  display: flex;
  align-items: center;
}

.reports-overview-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 0.88rem;
  font-weight: 600;
}

.reports-overview-pill-pass {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.reports-overview-pill-fail {
  background: rgba(248, 113, 113, 0.12);
  color: #b91c1c;
}

.reports-overview-pill-warning {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}

.reports-overview-pill-muted {
  background: rgba(148, 163, 184, 0.12);
  color: #475569;
}

.reports-metrics-cell {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.reports-metric-item {
  display: grid;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.9);
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.reports-metric-item strong {
  font-size: 1.08rem;
  color: #111827;
}

.reports-actions-cell {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 1180px) {
  .reports-table-head,
  .reports-table-row {
    grid-template-columns: 1fr;
  }

  .reports-table-head {
    display: none;
  }

  .reports-actions-cell {
    justify-content: flex-start;
  }
}

@media (max-width: 860px) {
  .reports-hero,
  .reports-panel-header {
    flex-direction: column;
  }

  .reports-list-description {
    max-width: none;
    text-align: left;
  }
}

@media (max-width: 640px) {
  .reports-metrics-cell {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
