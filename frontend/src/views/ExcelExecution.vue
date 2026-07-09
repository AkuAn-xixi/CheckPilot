<template>
            <div class="card w-full max-w-7xl mx-auto excel-execution-page">
              <div class="mb-4 flex flex-wrap items-center gap-3">
                <router-link to="/excel" class="btn btn-secondary btn-sm">
                  {{ $t('common.chooseFeature') }}
                </router-link>
                <h2 class="mb-0">{{ $t('excelExecution.title') }}</h2>
              </div>

              <div class="excel-execution-scroll">
                <div v-if="!selectedDevice" class="bg-yellow-50 p-4 rounded-lg mb-6">
                  <p class="text-warning mb-2">{{ $t('common.deviceRequired') }}</p>
                  <router-link :to="{ path: '/', query: { panel: 'device-hub' } }" class="btn btn-primary">
                    {{ $t('common.goDeviceManagement') }}
                  </router-link>
                </div>

                <div>
                <input
                  ref="verifyImageFolderInput"
                  type="file"
                  class="hidden"
                  webkitdirectory
                  directory
                  multiple
                  @change="handleVerifyImageFolderChange"
                >

                <div class="excel-top-grid mb-4">
                <div v-if="showCompactFileSelectorPanel" class="excel-top-compact-card excel-section-card mb-0 rounded-[24px] border border-white/70 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
                  <div class="excel-top-compact-header">
                    <div class="min-w-0">
                      <p class="eyebrow">{{ $t('excelExecution.chooseExcel') }}</p>
                      <h3 class="excel-top-compact-title">{{ selectedFile }}</h3>
                      <p class="excel-top-compact-meta">{{ $t('excelExecution.fileReadyHint') }}</p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                      <button @click="analyzeFile" class="btn btn-primary btn-sm" :disabled="loadingAnalysis || !selectedFile">
                        {{ loadingAnalysis ? $t('common.analyzing') : $t('common.analyzeFile') }}
                      </button>
                      <button
                        v-if="validationResult"
                        @click="openValidationResultModal"
                        class="btn btn-secondary btn-sm"
                        :disabled="loadingAnalysis"
                      >
                        {{ $t('excelExecution.viewAnalysisResult') }}
                      </button>
                      <button @click="expandFileSelectorPanel" class="btn btn-secondary btn-sm">
                        {{ $t('excelExecution.changeSelectedFile') }}
                      </button>
                    </div>
                  </div>
                </div>
                <div v-else class="excel-file-panel excel-section-card mb-0 rounded-[28px] border border-white/70 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
                  <h3 class="font-medium mb-3">{{ $t('excelExecution.chooseExcel') }}</h3>
                  <button @click="loadExcelFiles" class="btn btn-secondary mb-4">
                    {{ $t('common.refreshFileList') }}
                  </button>

                  <div v-if="loadingFiles">
                    <p>{{ $t('common.loading') }}</p>
                  </div>

                  <div v-if="excelFiles.length > 0">
                    <p class="mb-3">{{ $t('common.currentDirectoryExcelFiles') }}</p>
                    <div class="excel-file-list space-y-2 mb-4">
                      <div
                        v-for="(file, index) in excelFiles"
                        :key="file"
                        class="excel-file-item border rounded-lg p-4 cursor-pointer hover:bg-gray-50"
                        :class="selectedFile === file ? 'border-primary bg-blue-50' : ''"
                        @click="selectFile(file)"
                      >
                        <div class="flex items-center justify-between gap-4">
                          <div class="flex-1 min-w-0">
                            <p class="font-medium">{{ $t('common.fileNumber', { index: index + 1 }) }}</p>
                            <p class="text-gray-600 truncate">{{ file }}</p>
                          </div>
                          <div class="flex items-center gap-2">
                            <button
                              @click.stop="deleteFile(file)"
                              class="btn btn-danger"
                              :disabled="executing"
                            >
                              {{ $t('common.delete') }}
                            </button>
                            <div class="text-primary" v-if="selectedFile === file">
                              ✅
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="mb-4 flex items-center gap-2">
                    <input
                      type="file"
                      id="fileUpload"
                      ref="fileInput"
                      class="hidden"
                      accept=".xlsx,.xls"
                      @change="uploadFile"
                    >
                    <button type="button" class="btn btn-primary" @click="handleUploadExcelClick">
                      {{ $t('common.uploadExcel') }}
                    </button>
                    <button @click="analyzeFile" class="btn btn-primary" :disabled="loadingAnalysis || !selectedFile">
                      {{ loadingAnalysis ? $t('common.analyzing') : $t('common.analyzeFile') }}
                    </button>
                    <button
                      v-if="validationResult"
                      @click="openValidationResultModal"
                      class="btn btn-secondary"
                      :disabled="loadingAnalysis"
                    >
                      {{ $t('excelExecution.viewAnalysisResult') }}
                    </button>
                  </div>

                  <div v-if="excelFiles.length === 0">
                    <p class="text-danger mb-4">{{ $t('common.noExcelFiles') }}</p>
                    <div class="bg-yellow-50 p-4 rounded-lg mb-4">
                      <h4 class="font-medium mb-2">{{ $t('common.hint') }}</h4>
                      <p class="text-sm mb-2">
                        {{ $t('excelExecution.uploadTip1') }}
                      </p>
                      <p class="text-sm">
                        {{ $t('excelExecution.uploadTip2') }}
                      </p>
                    </div>
                  </div>
                </div>

                <section v-if="showCompactModelSelectorPanel" class="excel-top-compact-card excel-section-card mb-0 rounded-[24px] border border-white/70 bg-white/65 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
                  <div class="excel-top-compact-header">
                    <div class="min-w-0">
                      <p class="eyebrow">{{ $t('excelExecution.imageModelSetup') }}</p>
                      <h3 class="excel-top-compact-title">{{ activeImageModelName || $t('excelExecution.noActiveImageModel') }}</h3>
                      <p class="excel-top-compact-meta">{{ $t('excelExecution.compareBackend', { backend: currentCompareBackendLabel }) }}</p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                      <button class="btn btn-secondary btn-sm" @click="loadImageModelStatus" :disabled="loadingImageModelStatus || downloadingImageModel || selectingImageModel || deletingImageModel || clearingImageModelSelection">
                        {{ loadingImageModelStatus ? $t('common.refreshing') : $t('common.refreshStatus') }}
                      </button>
                      <button class="btn btn-secondary btn-sm" @click="expandModelSelectorPanel">
                        {{ $t('excelExecution.changeSelectedModel') }}
                      </button>
                    </div>
                  </div>
                </section>
                <section v-else class="excel-section-card excel-top-model-panel mb-0 rounded-[28px] border border-white/70 bg-white/65 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
                  <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div class="min-w-0">
                      <p class="eyebrow">{{ $t('excelExecution.imageModelSetup') }}</p>
                      <div class="mt-2 flex flex-wrap items-center gap-3">
                        <h3 class="text-lg font-semibold tracking-tight">{{ $t('excelExecution.imageModelTitle') }}</h3>
                        <span class="rounded-full bg-white/80 px-3 py-1 text-sm text-gray-500">
                          {{ activeImageModelName ? $t('excelExecution.activeImageModel', { model: activeImageModelName }) : $t('excelExecution.noActiveImageModel') }}
                        </span>
                      </div>
                      <p class="mt-2 text-sm leading-6 text-gray-500">
                        {{ $t('excelExecution.imageModelSubtitle') }}
                      </p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                      <button class="btn btn-secondary btn-sm" @click="loadImageModelStatus" :disabled="loadingImageModelStatus || downloadingImageModel || selectingImageModel || deletingImageModel || clearingImageModelSelection">
                        {{ loadingImageModelStatus ? $t('common.refreshing') : $t('common.refreshStatus') }}
                      </button>
                      <button class="btn btn-primary btn-sm" @click="downloadRecommendedImageModel" :disabled="downloadingImageModel || selectingImageModel || deletingImageModel || clearingImageModelSelection || missingImageModelDependencies.length > 0">
                        {{ downloadingImageModel ? $t('excelExecution.downloadingImageModel') : $t('excelExecution.downloadRecommendedModel') }}
                      </button>
                      <button class="btn btn-secondary btn-sm" @click="clearSelectedImageModel" :disabled="clearingImageModelSelection || downloadingImageModel || selectingImageModel || deletingImageModel || !activeImageModelName">
                        {{ $t('excelExecution.useOpenCv') }}
                      </button>
                    </div>
                  </div>

                  <div v-if="imageModelStatusError" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {{ imageModelStatusError }}
                  </div>

                  <div class="mt-4 flex flex-wrap items-center gap-3 text-sm text-gray-600">
                    <span>{{ $t('excelExecution.compareBackend', { backend: currentCompareBackendLabel }) }}</span>
                    <span>{{ $t('excelExecution.downloadedModels', { count: imageModelStatus.imported_models?.length || 0 }) }}</span>
                    <span :class="missingImageModelDependencies.length ? 'text-warning' : 'text-success'">
                      {{ $t('excelExecution.runtimeStatus', { status: missingImageModelDependencies.length ? $t('common.missingDependencies') : $t('common.ready') }) }}
                    </span>
                  </div>

                  <div v-if="imageModelMessage" class="mt-4 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-800">
                    {{ imageModelMessage }}
                  </div>

                  <div v-if="missingImageModelDependencies.length" class="mt-4 rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-amber-900">
                    <p class="font-medium">{{ $t('excelExecution.dinoDependencyWarning') }}</p>
                    <p class="mt-2">{{ $t('excelExecution.currentPython', { version: imageDependencyStatus.python_version || $t('common.unknown') }) }}</p>
                    <p>{{ $t('excelExecution.recommendedPython', { version: imageDependencyStatus.recommended_python_version || '3.12' }) }}</p>
                    <p class="mt-1 leading-6">{{ $t('excelExecution.missingDependencies', { dependencies: missingImageModelDependencies.join(', ') }) }}</p>

                    <div v-if="imageDependencyStatus.notes?.length" class="mt-3 space-y-1 text-xs leading-5 text-amber-800">
                      <div v-for="(note, index) in imageDependencyStatus.notes" :key="index">{{ note }}</div>
                    </div>

                    <div v-if="imageDependencyStatus.install_steps?.length" class="mt-4 rounded-lg bg-white/70 p-4">
                      <p class="text-sm font-medium mb-2">{{ $t('excelExecution.handlingSteps') }}</p>
                      <div class="space-y-1 text-sm leading-6">
                        <div v-for="(step, index) in imageDependencyStatus.install_steps" :key="index">
                          {{ index + 1 }}. {{ step }}
                        </div>
                      </div>
                    </div>

                    <div v-if="imageDependencyStatus.install_commands?.length" class="mt-4 rounded-lg bg-slate-950 p-4 font-mono text-xs leading-6 text-slate-100">
                      <div v-for="(command, index) in imageDependencyStatus.install_commands" :key="index">{{ command }}</div>
                    </div>
                  </div>

                  <div v-if="imageModelStatus.imported_models?.length" class="space-y-2 mt-4">
                    <div v-for="model in imageModelStatus.imported_models" :key="model.name" class="border rounded-lg p-4 bg-white/80">
                      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div class="flex-1 min-w-0">
                          <div class="flex flex-wrap items-center gap-2">
                            <p class="font-medium">{{ model.name }}</p>
                            <span v-if="model.is_active" class="rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700">{{ $t('excelExecution.modelInUse') }}</span>
                            <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{{ $t('excelExecution.modelFiles', { count: model.file_count }) }}</span>
                          </div>
                          <p v-if="model.repo_id" class="mt-2 text-xs text-gray-500 break-all">{{ model.repo_id }}</p>
                          <p class="text-gray-500 text-sm break-all mt-2">{{ model.path }}</p>
                        </div>
                        <div class="flex items-center gap-2">
                          <button class="btn btn-secondary" @click="selectImageModel(model.name)" :disabled="selectingImageModel || deletingImageModel || downloadingImageModel || clearingImageModelSelection || model.is_active || missingImageModelDependencies.length > 0">
                            {{ model.is_active ? $t('excelExecution.selectedImageModel') : $t('excelExecution.useThisImageModel') }}
                          </button>
                          <button class="btn btn-danger" @click="deleteImageModel(model.name)" :disabled="deletingImageModel || selectingImageModel || downloadingImageModel || clearingImageModelSelection">
                            {{ $t('common.delete') }}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-else class="mt-4 bg-yellow-50 p-4 rounded-lg">
                    <p class="text-sm text-gray-600">{{ $t('excelExecution.noDownloadedModels') }}</p>
                  </div>
                </section>
                </div>
                <section v-if="showCompactReportPanel" class="excel-top-compact-card excel-section-card excel-report-panel mb-6 rounded-[24px] border border-white/70 bg-white/65 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
                  <div class="excel-top-compact-header">
                    <div class="min-w-0">
                      <p class="eyebrow">{{ $t('reports.groups.image.eyebrow') }}</p>
                      <h3 class="excel-top-compact-title">{{ $t('reports.groups.image.title') }}</h3>
                      <p class="excel-top-compact-meta">
                        {{ latestImageReport ? latestImageReport.title : $t('excelExecution.noImageReports') }}
                      </p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="rounded-full bg-white/80 px-3 py-1 text-sm text-gray-500">
                        {{ imageReportRows.length }}
                      </span>
                      <button class="btn btn-secondary btn-sm" @click="loadImageReports" :disabled="loadingImageReports">
                        {{ loadingImageReports ? $t('common.refreshing') : $t('common.refreshStatus') }}
                      </button>
                      <button class="btn btn-secondary btn-sm" @click="expandReportPanel">
                        {{ $t('excelExecution.expandReportPanel') }}
                      </button>
                    </div>
                  </div>

                  <div v-if="imageReportsError" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {{ imageReportsError }}
                  </div>

                  <div v-else-if="loadingImageReports && !imageReportRows.length" class="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    {{ $t('common.loading') }}
                  </div>

                  <div v-else-if="latestImageReport" class="mt-4 flex flex-wrap items-center gap-3">
                    <span :class="['excel-report-overview-pill', `excel-report-overview-pill-${latestImageReport.overviewTone}`]">
                      {{ latestImageReport.overviewText }}
                    </span>
                    <div class="excel-report-metrics">
                      <span>{{ $t('reports.detail.summary.total') }} {{ latestImageReport.summary.total }}</span>
                      <span>{{ $t('reports.detail.summary.passed') }} {{ latestImageReport.summary.passed }}</span>
                      <span>{{ $t('reports.detail.summary.failed') }} {{ latestImageReport.summary.failed }}</span>
                      <span>{{ $t('reports.list.passRate') }} {{ latestImageReport.passRate }}</span>
                    </div>
                  </div>

                  <div v-else class="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    {{ $t('excelExecution.reportReadyHint') }}
                  </div>
                </section>

                <section v-else class="excel-section-card excel-report-panel mb-6 rounded-[28px] border border-white/70 bg-white/65 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
                  <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div class="min-w-0">
                      <p class="eyebrow">{{ $t('reports.groups.image.eyebrow') }}</p>
                      <div class="mt-2 flex flex-wrap items-center gap-3">
                        <h3 class="text-lg font-semibold tracking-tight">{{ $t('reports.groups.image.title') }}</h3>
                        <span class="rounded-full bg-white/80 px-3 py-1 text-sm text-gray-500">
                          {{ imageReportRows.length }}
                        </span>
                      </div>
                      <p class="mt-2 text-sm leading-6 text-gray-500">
                        {{ $t('reports.groups.image.description') }}
                      </p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                      <button class="btn btn-secondary btn-sm" @click="loadImageReports" :disabled="loadingImageReports">
                        {{ loadingImageReports ? $t('common.refreshing') : $t('common.refreshStatus') }}
                      </button>
                      <button class="btn btn-secondary btn-sm" @click="collapseReportPanel">
                        {{ $t('excelExecution.collapseReportPanel') }}
                      </button>
                    </div>
                  </div>

                  <div v-if="imageReportsError" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {{ imageReportsError }}
                  </div>

                  <div v-else-if="loadingImageReports && !imageReportRows.length" class="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    {{ $t('common.loading') }}
                  </div>

                  <div v-else-if="imageReportRows.length" class="excel-report-list mt-4">
                    <article v-for="item in imageReportRows" :key="item.report_id" class="excel-report-row">
                      <div class="excel-report-main">
                        <strong>{{ item.title }}</strong>
                        <p>{{ formatReportDate(item.updated_at) }} · {{ $t('reports.groups.image.kindLabel') }}</p>
                      </div>

                      <div class="excel-report-summary">
                        <span :class="['excel-report-overview-pill', `excel-report-overview-pill-${item.overviewTone}`]">
                          {{ item.overviewText }}
                        </span>
                        <div class="excel-report-metrics">
                          <span>{{ $t('reports.detail.summary.total') }} {{ item.summary.total }}</span>
                          <span>{{ $t('reports.detail.summary.passed') }} {{ item.summary.passed }}</span>
                          <span>{{ $t('reports.detail.summary.failed') }} {{ item.summary.failed }}</span>
                          <span>{{ $t('reports.list.passRate') }} {{ item.passRate }}</span>
                        </div>
                      </div>

                      <div class="excel-report-actions">
                        <button
                          type="button"
                          class="btn btn-primary btn-sm"
                          :disabled="!item.report_url"
                          @click="openReport(item.report_url)"
                        >
                          {{ $t('reports.detail.openHtml') }}
                        </button>
                      </div>
                    </article>
                  </div>

                  <div v-else class="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    {{ $t('excelExecution.noImageReports') }}
                  </div>
                </section>

                <div v-if="selectedFile" class="mb-6">
                  <div v-if="loadingAnalysis">
                    <p>{{ $t('common.analyzing') }}</p>
                  </div>

                  <div v-else-if="excelAnalysis">
                    <div v-if="excelAnalysis.valid_rows.length > 0">
                      <p class="mb-3">{{ $t('common.foundValidRows', { count: excelAnalysis.valid_rows.length }) }}</p>

                      <div class="mb-4 flex flex-wrap gap-4 items-center">
                        <div>
                          <label class="form-label mr-2">{{ $t('excelExecution.filterResult') }}</label>
                          <select v-model="filterResult" class="form-select">
                            <option value="">{{ $t('common.all') }}</option>
                            <option value="PASS">PASS</option>
                            <option value="Fail">Fail</option>
                            <option value="NT">NT</option>
                            <option value="NA">NA</option>
                            <option value="empty">{{ $t('common.empty') }}</option>
                          </select>
                        </div>
                        <div class="flex-1 min-w-[200px]">
                          <label class="form-label mr-2">{{ $t('common.search') }}</label>
                          <input
                            v-model="searchKeyword"
                            type="text"
                            class="form-input w-full"
                            :placeholder="$t('excelExecution.searchPlaceholder')"
                          >
                        </div>
                      </div>

                      <div class="excel-sticky-bar">
                        <div class="mb-4 flex justify-between items-center gap-3">
                          <div class="flex flex-wrap gap-3">
                            <button
                              @click="executeSelectedRows()"
                              class="btn btn-success"
                              :disabled="selectedRows.length === 0 || isBatchExecuting || !selectedDevice"
                              :title="!selectedDevice ? $t('common.deviceRequired') : ''"
                            >
                              {{ $t('excelExecution.batchExecute', { count: selectedRows.length }) }}
                            </button>
                            <button
                              @click="executeAllRows()"
                              class="btn btn-primary"
                              :disabled="allRowIndexes.length === 0 || isBatchExecuting || !selectedDevice"
                              :title="!selectedDevice ? $t('common.deviceRequired') : ''"
                            >
                              {{ $t('excelExecution.executeAll', { count: allRowIndexes.length }) }}
                            </button>
                          </div>
                          <button
                            @click="stopAllExecution()"
                            class="btn btn-danger"
                            :disabled="!isBatchExecuting"
                          >
                            {{ $t('excelExecution.stopAll') }}
                          </button>
                        </div>

                      <section
                        v-if="showBatchExecutionProgress"
                        class="excel-section-card mb-4 rounded-[24px] border border-sky-100 bg-sky-50/80 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_14px_30px_rgba(14,116,144,0.08)]"
                      >
                        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                          <div class="min-w-0">
                            <p class="eyebrow">{{ $t('excelExecution.batchProgressTitle') }}</p>
                            <div class="mt-2 flex flex-wrap items-center gap-3">
                              <h3 class="text-lg font-semibold tracking-tight text-slate-900">{{ batchExecutionState.label }}</h3>
                              <span class="rounded-full bg-white/85 px-3 py-1 text-sm text-slate-600">
                                {{ $t('excelExecution.batchProgressSummary', { completed: batchExecutionState.completed, total: batchExecutionState.total }) }}
                              </span>
                              <span
                                class="rounded-full px-3 py-1 text-xs font-semibold"
                                :class="batchExecutionState.active ? 'bg-sky-100 text-sky-700' : batchExecutionState.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'"
                              >
                                {{ batchExecutionStatusLabel }}
                              </span>
                            </div>
                            <p v-if="batchExecutionState.currentRowIndex" class="mt-2 text-sm leading-6 text-slate-600">
                              {{ $t('excelExecution.batchProgressCurrentCase', { row: batchExecutionState.currentRowIndex, title: batchExecutionState.currentCaseTitle }) }}
                            </p>
                            <p v-else-if="batchExecutionState.status === 'completed'" class="mt-2 text-sm leading-6 text-slate-600">
                              {{ $t('excelExecution.batchProgressCompletedHint') }}
                            </p>
                            <p v-else-if="batchExecutionState.status === 'stopped'" class="mt-2 text-sm leading-6 text-slate-600">
                              {{ $t('excelExecution.batchProgressStoppedHint', { count: batchExecutionRemainingCount }) }}
                            </p>
                          </div>
                          <div class="flex shrink-0 flex-col items-end gap-1 text-right">
                            <span class="text-2xl font-semibold tracking-tight text-slate-900">{{ batchExecutionPercent }}%</span>
                            <span class="text-sm text-slate-500">{{ $t('excelExecution.batchProgressRemaining', { count: batchExecutionRemainingCount }) }}</span>
                          </div>
                        </div>

                        <div class="mt-4 h-3 overflow-hidden rounded-full bg-white/85">
                          <div
                            class="h-full rounded-full bg-gradient-to-r from-sky-500 via-cyan-500 to-emerald-500 transition-all duration-300"
                            :style="{ width: `${batchExecutionPercent}%` }"
                          ></div>
                        </div>
                      </section>

                      <div class="mb-4 flex flex-wrap items-center gap-3 text-sm text-gray-600">
                        <span>{{ $t('excelExecution.verifyFolder', { name: verifyImageFolderName || $t('excelExecution.verifyFolderDefault') }) }}</span>
                        <button class="btn btn-secondary btn-sm" @click="triggerVerifyImageFolderPicker()">
                          {{ $t('common.chooseFolder') }}
                        </button>
                        <span v-if="verifyImageFileCount > 0">{{ $t('excelExecution.indexedImages', { count: verifyImageFileCount }) }}</span>

                        <button
                          class="btn btn-secondary btn-sm ml-auto"
                          @click="showExecutionSettings = !showExecutionSettings"
                        >
                          ⚙ {{ showExecutionSettings ? '隐藏设置' : '执行设置' }}
                        </button>
                      </div>

                      <!-- 执行设置面板 -->
                      <div v-if="showExecutionSettings" class="mb-4 rounded-xl border border-gray-200 bg-gray-50/80 p-4">
                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

                          <!-- 匹配阈值 -->
                          <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">匹配阈值</label>
                            <div class="flex items-center gap-2">
                              <input
                                v-model.number="matchThreshold"
                                type="range"
                                min="0.5"
                                max="1"
                                step="0.01"
                                class="flex-1"
                              >
                              <input
                                v-model.number="matchThreshold"
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                class="form-input w-16 text-center text-sm"
                              >
                            </div>
                          </div>

                          <!-- 截图来源 -->
                          <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">截图来源</label>
                            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors"
                                :class="screenshotSource === 'adb' ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="screenshotSource = 'adb'"
                              >ADB</button>
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                                :class="screenshotSource === 'capture_card' ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="screenshotSource = 'capture_card'"
                              >采集卡</button>
                            </div>
                          </div>

                          <!-- 执行模式 -->
                          <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">执行模式</label>
                            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors"
                                :class="executionMode === 'single' ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="executionMode = 'single'"
                              >单次</button>
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                                :class="executionMode === 'loop_row' ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="executionMode = 'loop_row'"
                              >单行循环</button>
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                                :class="executionMode === 'loop_list' ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="executionMode = 'loop_list'"
                              >列表循环</button>
                            </div>
                          </div>

                          <!-- 循环设置 -->
                          <template v-if="executionMode !== 'single'">
                            <div class="flex flex-col gap-1.5">
                              <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">循环类型</label>
                              <div class="flex items-center gap-2">
                                <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
                                  <button
                                    class="px-3 py-1.5 transition-colors"
                                    :class="loopType === 'finite' ? 'bg-emerald-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                    @click="loopType = 'finite'"
                                  >有限</button>
                                  <button
                                    class="px-3 py-1.5 transition-colors border-l border-gray-200"
                                    :class="loopType === 'infinite' ? 'bg-emerald-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                    @click="loopType = 'infinite'"
                                  >无限</button>
                                </div>
                                <template v-if="loopType === 'finite'">
                                  <input
                                    v-model.number="loopCount"
                                    type="number"
                                    min="1"
                                    max="9999"
                                    class="form-input w-16 text-center text-sm"
                                  >
                                  <span class="text-xs text-gray-400">次</span>
                                </template>
                              </div>
                            </div>
                          </template>

                          <!-- 是否校验 -->
                          <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">执行后校验</label>
                            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors"
                                :class="enableVerification ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="enableVerification = true"
                              >开启</button>
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                                :class="!enableVerification ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="enableVerification = false"
                              >关闭</button>
                            </div>
                          </div>

                          <!-- 是否录屏 -->
                          <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">执行录屏</label>
                            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors"
                                :class="enableRecording ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="enableRecording = true"
                              >开启</button>
                              <button
                                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                                :class="!enableRecording ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
                                @click="enableRecording = false"
                              >关闭</button>
                            </div>
                          </div>

                        </div>
                      </div>
                      </div><!-- /excel-sticky-bar -->

                      <div class="excel-table-shell mb-4 overflow-x-auto rounded-[28px] border border-white/70 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
                        <table class="excel-results-table w-full min-w-[1160px] table-fixed">
                          <colgroup>
                            <col style="width: 48px;">
                            <col style="width: 86px;">
                            <col style="width: 170px;">
                            <col>
                            <col style="width: 170px;">
                            <col style="width: 128px;">
                            <col style="width: 128px;">
                          </colgroup>
                          <thead class="bg-slate-50/90">
                            <tr>
                              <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                                <input
                                  type="checkbox"
                                  @change="toggleSelectAll"
                                  :checked="isPageAllSelected"
                                >
                              </th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelExecution.columns.result') }}</th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelExecution.columns.title') }}</th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelExecution.columns.steps') }}</th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelExecution.columns.verifyImage') }}</th>
                              <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelExecution.columns.actions') }}</th>
                              <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelExecution.columns.executionResult') }}</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="item in pagedRows" :key="item.idx">
                              <td class="border px-3 py-3 text-center align-top">
                                <input
                                  type="checkbox"
                                  :checked="selectedRows.includes(item.idx)"
                                  @change="toggleSelectRow(item.idx)"
                                >
                              </td>
                              <td class="border px-3 py-3 align-top">
                                <button
                                  :ref="(el) => setResultBtnRef(item.idx, el)"
                                  class="w-full text-left cursor-pointer hover:bg-gray-50 rounded px-1 py-0.5 -m-1"
                                  :title="$t('excelExecution.clickToToggleResult')"
                                  @click.stop="toggleResultPopover(item.idx, $event)"
                                >
                                  <span v-if="item.row.result" :class="getResultClass(item.row.result)">
                                    {{ item.row.result }}
                                  </span>
                                  <span v-else-if="item.row.test_result" :class="getResultClass(item.row.test_result)">
                                    {{ item.row.test_result }}
                                  </span>
                                  <span v-else class="text-gray-400">-</span>
                                </button>
                              </td>
                              <td class="border px-3 py-3 align-top">
                                <span v-if="item.row.title" class="block truncate text-primary" :title="item.row.title">{{ item.row.title }}</span>
                                <span v-else>-</span>
                              </td>
                              <td class="border px-3 py-3 align-top">
                                <div v-if="executingRows[item.idx] && getRowCommandGroups(item.row).length" class="space-y-2">
                                  <div
                                    v-for="group in getRowCommandGroups(item.row)"
                                    :key="group.id"
                                    class="excel-step-group"
                                  >
                                    <span
                                      v-for="command in group.commands"
                                      :key="command.id"
                                      class="excel-step-command"
                                      :class="{ 'excel-step-command-active': isRowCommandActive(item.idx, command) }"
                                      :title="command.raw"
                                    >
                                      <span class="excel-step-command-key">{{ command.key }}</span>
                                      <span v-if="command.meta" class="excel-step-command-meta">{{ command.meta }}</span>
                                      <span
                                        v-if="getRowCommandProgressText(item.idx, command)"
                                        class="excel-step-command-progress"
                                      >
                                        {{ getRowCommandProgressText(item.idx, command) }}
                                      </span>
                                    </span>
                                  </div>
                                </div>
                                <div
                                  v-else-if="getRowCommandSequence(item.row).length"
                                  class="excel-step-sequence-collapsed"
                                  :title="getRowCommandSequenceTitle(item.row)"
                                >
                                  <span
                                    v-for="command in getRowCommandSequence(item.row)"
                                    :key="command.id"
                                    class="excel-step-command"
                                    :title="command.raw"
                                  >
                                    <span class="excel-step-command-key">{{ command.key }}</span>
                                    <span v-if="command.meta" class="excel-step-command-meta">{{ command.meta }}</span>
                                  </span>
                                </div>
                                <span v-else>-</span>
                              </td>
                              <td class="border px-3 py-3 align-top">
                                <span
                                  v-if="item.row.verify_image && item.row.verify_image !== 'nan'"
                                  class="block cursor-pointer truncate text-primary hover:underline"
                                  :title="item.row.verify_image"
                                  @click="previewVerifyImage(item.row.verify_image)"
                                >
                                  {{ item.row.verify_image }}
                                </span>
                                <span v-else>-</span>
                              </td>
                              <td class="border px-3 py-3 text-center align-top">
                                <div class="excel-row-actions flex flex-col items-center gap-2">
                                  <button
                                    @click="openCaseEditModal(item)"
                                    class="btn btn-secondary min-w-[88px] whitespace-nowrap"
                                    :disabled="savingCaseFields || executingRows[item.idx]"
                                  >
                                    {{ $t('common.edit') }}
                                  </button>
                                  <button
                                    v-if="!executingRows[item.idx]"
                                    @click="executeExcelRowByIndex(item.idx)"
                                    class="btn btn-primary min-w-[88px] whitespace-nowrap"
                                    :disabled="!selectedDevice"
                                    :title="!selectedDevice ? $t('common.deviceRequired') : ''"
                                  >
                                    {{ $t('common.execute') }}
                                  </button>
                                  <button
                                    v-else
                                    @click="stopExecution(item.idx)"
                                    class="btn btn-danger min-w-[88px] whitespace-nowrap"
                                  >
                                    {{ $t('common.stop') }}
                                  </button>
                                </div>
                              </td>
                              <td class="border px-3 py-3 text-center align-top">
                                <button
                                  v-if="(rowScreenshots[item.idx] || rowResultMeta[item.idx]?.video_url) && !executingRows[item.idx]"
                                  @click="showExecutionResult(item.idx)"
                                  class="btn btn-sm btn-info min-w-[96px] whitespace-nowrap"
                                >
                                  {{ $t('excelExecution.viewResult') }}
                                </button>
                                <span v-else>-</span>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      <div class="flex items-center justify-between flex-wrap gap-3">
                        <div class="flex items-center gap-2">
                          <span>{{ $t('common.perPage') }}</span>
                          <select v-model.number="pageSize" class="form-select">
                            <option :value="10">10</option>
                            <option :value="20">20</option>
                            <option :value="50">50</option>
                          </select>
                          <span>{{ $t('common.items') }}</span>
                        </div>
                        <div class="flex items-center gap-2 flex-wrap">
                          <button class="btn btn-secondary" @click="handlePrevPage" :disabled="currentPage === 1">{{ $t('common.previousPage') }}</button>
                          <span>{{ $t('common.pageInfo', { current: currentPage, total: totalPages }) }}</span>
                          <div class="flex items-center gap-1">
                            <span>{{ $t('common.goTo') }}</span>
                            <input
                              type="number"
                              v-model.number="jumpPage"
                              class="form-input w-16 text-center"
                              :min="1"
                              :max="totalPages"
                              @keyup.enter="handleJumpPage"
                            >
                            <button class="btn btn-primary btn-sm" @click="handleJumpPage" :disabled="!jumpPage || jumpPage < 1 || jumpPage > totalPages">{{ $t('common.jump') }}</button>
                          </div>
                          <button class="btn btn-secondary" @click="handleNextPage" :disabled="currentPage === totalPages">{{ $t('common.nextPage') }}</button>
                          <span>{{ $t('common.total', { count: filteredRows.length }) }}</span>
                        </div>
                      </div>

                      <div v-if="excelAnalysis.skipped_rows.length > 0" class="excel-note-card bg-yellow-50 p-4 rounded-lg mb-4 mt-4">
                        <h4 class="font-medium mb-2">{{ $t('excelExecution.skippedRows') }}</h4>
                        <div class="space-y-2 max-h-40 overflow-y-auto">
                          <div v-for="(row, index) in excelAnalysis.skipped_rows" :key="index" class="text-sm">
                            <div class="break-all">{{ $t('excelExecution.rowFallbackTitle', { row: row.row }) }}: {{ row.reason }}</div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div v-else>
                      <p class="text-danger">{{ $t('excelExecution.noValidCommands') }}</p>
                    </div>
                  </div>
                </div>
                </div>
              </div>

              <div
                v-if="showValidationResultModal && validationResult"
                class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
                @click.self="closeValidationResultModal"
              >
                <div class="bg-white rounded-[24px] shadow-xl p-5 w-[92vw] max-w-4xl max-h-[88vh] overflow-hidden flex flex-col">
                  <div class="flex items-start justify-between gap-4 mb-4">
                    <div class="min-w-0">
                      <h3 class="text-lg font-medium break-words">
                        {{ $t('common.fileValidationResult', { status: validationResult.success ? $t('common.pass') : $t('common.fail'), count: validationResult.total_rows }) }}
                      </h3>
                      <p v-if="selectedFile" class="text-sm text-gray-500 mt-1 break-all">{{ selectedFile }}</p>
                    </div>
                    <button @click="closeValidationResultModal" class="text-gray-500 hover:text-gray-700">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  <div class="overflow-y-auto pr-1 space-y-4">
                    <div
                      class="rounded-[20px] border px-4 py-4"
                      :class="validationResult.success ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'"
                    >
                      <div class="flex items-start gap-3">
                        <span
                          class="text-2xl leading-none"
                          :class="validationResult.success ? 'text-green-600' : 'text-red-600'"
                        >
                          {{ validationResult.success ? '✅' : '❌' }}
                        </span>
                        <div class="min-w-0">
                          <p class="font-medium text-slate-800 break-words">
                            {{ $t('common.fileValidationResult', { status: validationResult.success ? $t('common.pass') : $t('common.fail'), count: validationResult.total_rows }) }}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div v-if="validationResult.errors && validationResult.errors.length > 0" class="rounded-[20px] border border-red-200 bg-red-50 px-4 py-4">
                      <p class="text-sm font-medium text-red-700 mb-2">{{ $t('common.errors') }}</p>
                      <div class="max-h-72 overflow-y-auto space-y-1 text-sm text-red-600">
                        <div v-for="(error, idx) in validationResult.errors" :key="idx" class="break-all">
                          • {{ error }}
                        </div>
                      </div>
                    </div>

                    <div v-if="validationResult.warnings && validationResult.warnings.length > 0" class="rounded-[20px] border border-yellow-200 bg-yellow-50 px-4 py-4">
                      <p class="text-sm font-medium text-yellow-700 mb-2">{{ $t('common.warnings') }}</p>
                      <div class="max-h-56 overflow-y-auto space-y-1 text-sm text-yellow-700">
                        <div v-for="(warning, idx) in validationResult.warnings" :key="idx" class="break-all">
                          • {{ warning }}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="mt-5 flex justify-end">
                    <button class="btn btn-secondary" @click="closeValidationResultModal">
                      {{ $t('common.close') }}
                    </button>
                  </div>
                </div>
              </div>

              <div
                v-if="showScreenshotModal"
                class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
                @click.self="closeScreenshotModal"
              >
                <div class="bg-white rounded-lg shadow-xl p-4 w-[95vw] max-w-[95vw] h-[90vh] max-h-[90vh] overflow-hidden flex flex-col">
                  <div class="flex justify-between items-center mb-2">
                    <div>
                      <h3 class="text-lg font-medium">{{ $t('excelExecution.executionComparison') }}</h3>
                      <p v-if="modalResultTitle" class="text-sm text-gray-500 mt-1">
                        {{ modalResultTitle }}
                      </p>
                    </div>
                    <button @click="closeScreenshotModal" class="text-gray-500 hover:text-gray-700">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div class="mb-3 flex flex-wrap items-center gap-3 text-sm">
                    <span
                      v-if="modalAssertResults.length > 1"
                      class="px-3 py-1 rounded-full font-medium"
                      :class="{
                        'bg-green-100 text-green-700': (modalOverallVerifyResult || '').toUpperCase() === 'PASS',
                        'bg-red-100 text-red-700': ['FAIL', 'ERROR'].includes((modalOverallVerifyResult || '').toUpperCase()),
                        'bg-gray-100 text-gray-700': !modalOverallVerifyResult,
                      }"
                    >
                      {{ $t('excelExecution.overallVerifyResult', { result: modalOverallVerifyResult || '-' }) }}
                    </span>
                    <span
                      v-if="modalAssertResults.length === 0 && modalResultStatus"
                      class="px-3 py-1 rounded-full font-medium"
                      :class="{
                        'bg-green-100 text-green-700': modalResultStatus.toUpperCase() === 'PASS',
                        'bg-red-100 text-red-700': ['FAIL', 'ERROR'].includes(modalResultStatus.toUpperCase()),
                        'bg-amber-100 text-amber-700': modalResultStatus.toUpperCase() === 'NT',
                        'bg-blue-100 text-blue-700': modalResultStatus.toUpperCase() === 'NA'
                      }"
                    >
                      {{ modalResultStatus }}
                    </span>
                    <span v-if="modalResultScore !== null" class="text-gray-600">
                      {{ $t('excelExecution.matchScore', { score: Number(modalResultScore).toFixed(3) }) }}
                    </span>
                  </div>

                  <div v-if="modalAssertResults.length > 1" class="mb-3 flex flex-wrap items-center gap-2">
                    <span class="text-xs text-gray-500">{{ $t('excelExecution.assertSwitchLabel') }}</span>
                    <button
                      v-for="(item, idx) in modalAssertResults"
                      :key="`assert-${idx}`"
                      type="button"
                      class="px-3 py-1 rounded-full text-xs border transition-colors"
                      :class="{
                        'bg-blue-600 text-white border-blue-600': idx === modalAssertActiveIndex,
                        'bg-white text-slate-600 border-slate-300 hover:border-blue-400': idx !== modalAssertActiveIndex,
                      }"
                      @click="switchModalAssertResult(idx)"
                    >
                      {{ idx + 1 }}.
                      <span
                        class="ml-1 font-semibold"
                        :class="{
                          'text-green-600': item.verify_result === 'PASS' && idx !== modalAssertActiveIndex,
                          'text-red-600': ['FAIL', 'ERROR'].includes(item.verify_result) && idx !== modalAssertActiveIndex,
                          'text-white': idx === modalAssertActiveIndex,
                        }"
                      >
                        {{ item.verify_result || '-' }}
                      </span>
                    </button>
                  </div>
                  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0 overflow-auto">
                    <div class="border rounded-lg p-3 flex flex-col min-h-[320px]">
                      <div class="flex justify-between items-center mb-3 gap-2 flex-wrap">
                        <h4 class="font-medium">{{ $t('excelExecution.adbScreenshot') }}</h4>
                        <div class="flex gap-2">
                          <button
                            class="btn btn-sm"
                            :class="isRegionSelectMode ? 'btn-warning' : 'btn-outline'"
                            @click="toggleRegionSelectMode"
                            :title="isRegionSelectMode ? '取消框选' : '框选保存'"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4h7v7H4V4zM13 4h7v7h-7V4zM4 13h7v7H4v-7zM13 13h7v7h-7v-7z" />
                            </svg>
                            {{ isRegionSelectMode ? '取消' : '框选保存' }}
                          </button>
                          <button
                            class="btn btn-sm btn-primary"
                            @click="directSaveScreenshot"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            直接保存
                          </button>
                        </div>
                      </div>
                      <!-- 文件名输入 -->
                      <div class="flex items-center gap-2 mb-2">
                        <label class="text-xs text-gray-500 whitespace-nowrap">文件名:</label>
                        <input
                          v-model="screenshotSaveFileName"
                          class="form-input flex-1 text-sm py-1"
                          placeholder="输入保存文件名"
                        >
                      </div>
                      <!-- 截图容器（支持框选） -->
                      <div
                        ref="screenshotContainerRef"
                        class="flex-1 flex justify-center items-center bg-gray-50 rounded-lg overflow-hidden relative select-none"
                        :class="{ 'cursor-crosshair': isRegionSelectMode }"
                        @mousedown="onScreenshotMouseDown"
                        @mousemove="onScreenshotMouseMove"
                        @mouseup="onScreenshotMouseUp"
                        @mouseleave="onScreenshotMouseUp"
                      >
                        <img
                          v-if="modalScreenshotUrl && !screenshotLoadError"
                          ref="screenshotImgRef"
                          :src="modalScreenshotUrl + '?t=' + screenshotTimestamp"
                          class="max-h-full max-w-full object-contain"
                          :alt="$t('excelExecution.screenshotAlt')"
                          draggable="false"
                          @load="screenshotLoadError = false"
                          @error="screenshotLoadError = true"
                        >
                        <span v-else-if="screenshotLoadError" class="text-red-400">截图加载失败（文件可能已被清除）</span>
                        <span v-else class="text-gray-400">{{ $t('excelExecution.noScreenshot') }}</span>
                        <!-- 框选矩形 -->
                        <div
                          v-if="isRegionSelectMode && regionOverlayStyle"
                          class="absolute border-2 border-blue-500 bg-blue-200/20 pointer-events-none"
                          :style="regionOverlayStyle"
                        ></div>
                        <!-- 框选提示 -->
                        <div
                          v-if="isRegionSelectMode && !regionStart"
                          class="absolute inset-0 flex items-center justify-center pointer-events-none"
                        >
                          <span class="bg-black/60 text-white text-sm px-3 py-1.5 rounded-full">拖动鼠标框选要保存的区域</span>
                        </div>
                      </div>
                    </div>
                    <div class="border rounded-lg p-3 flex flex-col min-h-[320px]">
                      <h4 class="font-medium mb-3">{{ $t('excelExecution.caseVerifyImage') }}</h4>
                      <p v-if="modalVerifyImageName" class="text-sm text-gray-500 mb-2">{{ modalVerifyImageName }}</p>
                      <div class="flex-1 flex justify-center items-center bg-gray-50 rounded-lg overflow-hidden">
                        <img
                          v-if="modalVerifyImageUrl"
                          :src="modalVerifyImageUrl"
                          class="max-h-full max-w-full object-contain"
                          :alt="$t('excelExecution.verifyImageAlt')"
                          @error="$event.target.style.display='none'; $event.target.nextElementSibling && ($event.target.nextElementSibling.style.display='')"
                        >
                        <span v-else class="text-gray-400">{{ modalVerifyImagePlaceholder || $t('excelExecution.noVerifyImage') }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- 执行录屏 -->
                  <div v-if="modalVideoUrl" class="mt-4 flex items-center gap-3">
                    <button
                      class="btn btn-primary btn-sm"
                      @click="openVideoWithLocalPlayer"
                    >
                      🎬 用本地播放器打开
                    </button>
                    <button
                      class="btn btn-secondary btn-sm"
                      @click="showVideoPlayer = !showVideoPlayer"
                    >
                      {{ showVideoPlayer ? '关闭预览' : '▶ 浏览器预览' }}
                    </button>
                    <a :href="modalVideoUrl" download class="btn btn-secondary btn-sm">下载录屏</a>
                  </div>
                  <div v-if="modalVideoUrl && showVideoPlayer" class="mt-3 border rounded-lg p-2">
                    <div class="text-sm text-gray-500 mb-2">
                      💡 提示：如果浏览器无法播放，请使用"用本地播放器打开"按钮。
                    </div>
                    <video
                      ref="videoPlayerRef"
                      controls
                      autoplay
                      preload="metadata"
                      class="w-full max-w-2xl mx-auto rounded"
                    >
                      <source :src="modalVideoUrl" :type="videoMimeType">
                      您的浏览器不支持视频播放
                    </video>
                  </div>
                </div>
              </div>

              <div
                v-if="showVerifyImageModal"
                class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60]"
                @click.self="closeVerifyImagePreviewModal"
              >
                <div class="bg-white rounded-xl shadow-xl p-4 w-auto max-w-xl max-h-[70vh] overflow-hidden flex flex-col">
                  <div class="flex justify-between items-center mb-2 shrink-0">
                    <div>
                      <h3 class="text-lg font-medium">{{ $t('excelExecution.verifyPreview') }}</h3>
                      <p v-if="verifyImagePreviewName" class="text-sm text-gray-500 mt-1">{{ verifyImagePreviewName }}</p>
                    </div>
                    <button @click="closeVerifyImagePreviewModal" class="text-gray-500 hover:text-gray-700">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  <div v-if="verifyImagePreviewList.length > 1" class="mb-2 flex flex-wrap items-center gap-2">
                    <span class="text-xs text-gray-500">
                      {{ $t('excelExecution.verifyPreviewCounter', {
                        current: verifyImagePreviewActiveIndex + 1,
                        total: verifyImagePreviewList.length,
                      }) }}
                    </span>
                    <button
                      v-for="(item, idx) in verifyImagePreviewList"
                      :key="`vp-${idx}`"
                      type="button"
                      class="px-2.5 py-1 rounded-full text-xs border transition-colors"
                      :class="{
                        'bg-blue-600 text-white border-blue-600': idx === verifyImagePreviewActiveIndex,
                        'bg-white text-slate-600 border-slate-300 hover:border-blue-400': idx !== verifyImagePreviewActiveIndex,
                        'opacity-60': item.missing,
                      }"
                      :title="item.missing ? $t('excelExecution.verifyImageNotFound') : item.relativePath || item.name"
                      @click="switchVerifyImagePreview(idx)"
                    >
                      {{ idx + 1 }}
                    </button>
                  </div>

                  <div class="flex justify-center items-center flex-1 min-h-0">
                    <img
                      v-if="verifyImageUrl"
                      :src="verifyImageUrl"
                      class="max-h-full max-w-full object-contain"
                      :alt="$t('excelExecution.verifyImageAlt')"
                    >
                    <span v-else class="text-gray-400">{{ $t('excelExecution.verifyImageNotFound') }}</span>
                  </div>
                </div>
              </div>

              <div
                v-if="showCaseEditModal"
                class="fixed inset-0 bg-black bg-opacity-50 flex items-stretch justify-center p-4 z-50"
                @click.self="closeCaseEditModal"
              >
                <div class="bg-white rounded-2xl shadow-xl flex flex-col w-full max-w-[min(1760px,98vw)] max-h-[94vh] m-auto">
                  <header class="flex-shrink-0 flex items-start justify-between gap-4 px-6 pt-5 pb-4 border-b border-slate-200">
                    <div>
                      <h3 class="text-lg font-medium">{{ $t('excelExecution.editCaseInfo') }}</h3>
                      <p v-if="editingCaseExcelRow" class="text-sm text-gray-500 mt-1">
                        {{ $t('excelExecution.editCaseRow', { row: editingCaseExcelRow }) }}
                      </p>
                    </div>
                    <button @click="closeCaseEditModal" class="text-gray-500 hover:text-gray-700" :disabled="savingCaseFields">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </header>

                  <div class="excel-edit-modal-body flex-1 min-h-0 grid grid-cols-1 gap-6 px-6 py-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.6fr)]">
                    <div class="excel-edit-modal-left min-h-0 lg:overflow-y-auto pr-1 space-y-6">
                      <div class="space-y-4">
                        <div>
                          <label class="form-label">{{ $t('excelExecution.caseTitle') }}</label>
                          <input
                            v-model="editingCaseForm.title"
                            type="text"
                            class="form-input w-full"
                            :placeholder="$t('excelExecution.caseTitlePlaceholder')"
                          >
                        </div>
                        <div>
                          <label class="form-label">{{ $t('excelExecution.originalSteps') }}</label>
                          <textarea
                            v-model="editingCaseForm.ori_step"
                            class="form-input w-full min-h-[120px] resize-y"
                            :placeholder="$t('excelExecution.originalStepsPlaceholder')"
                            @focus="setEditCommandTargetField('ori_step')"
                          ></textarea>
                        </div>
                        <div>
                          <label class="form-label">{{ $t('excelExecution.preScript') }}</label>
                          <textarea
                            v-model="editingCaseForm.pre_script"
                            class="form-input w-full min-h-[120px] resize-y"
                            :placeholder="$t('excelExecution.preScriptPlaceholder')"
                            @focus="setEditCommandTargetField('pre_script')"
                          ></textarea>
                        </div>
                        <div>
                          <label class="form-label">{{ $t('excelExecution.verifyImageField') }}</label>
                          <div class="flex items-center gap-2">
                            <input
                              v-model="editingCaseForm.verify_image"
                              type="text"
                              class="form-input flex-1 min-w-0"
                              :placeholder="$t('excelExecution.verifyImagePlaceholder')"
                            >
                            <button
                              class="btn btn-secondary btn-sm shrink-0"
                              :disabled="!editingCaseForm.verify_image || editingCaseForm.verify_image === 'nan'"
                              :title="$t('excelExecution.verifyPreview')"
                              @click="previewVerifyImage(editingCaseForm.verify_image)"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        <div>
                          <label class="form-label">{{ $t('excelExecution.columns.result') }}</label>
                          <select v-model="editingCaseForm.test_result" class="form-select">
                            <option value="">{{ $t('common.empty') }}</option>
                            <option value="PASS">PASS</option>
                            <option value="Fail">Fail</option>
                            <option value="NT">NT</option>
                            <option value="NA">NA</option>
                          </select>
                        </div>
                      </div>

                      <aside class="rounded-[28px] border border-slate-200 bg-slate-50/90 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
                        <div class="mb-3">
                          <h4 class="text-sm font-semibold text-slate-900">{{ $t('excelExecution.monitorHelperTitle') }}</h4>
                          <p class="mt-1 text-xs leading-5 text-slate-500">{{ $t('excelExecution.monitorHelperDesc') }}</p>
                          <p class="mt-2 text-xs font-medium" :class="editKeyMonitorActive || editKeyMonitorStarting ? 'text-emerald-600' : 'text-slate-500'">
                            {{ editKeyMonitorActive || editKeyMonitorStarting ? $t('excelExecution.monitorStatusActive') : $t('excelExecution.monitorStatusIdle') }}
                          </p>
                        </div>

                        <div class="mb-3 rounded-2xl border border-amber-200 bg-amber-50/80 px-3 py-3">
                          <div class="text-xs font-semibold text-amber-700 mb-2">
                            {{ $t('excelExecution.mappingSchemes.label') }}
                          </div>
                          <select
                            :value="activeMappingSchemeName"
                            class="form-select form-select-sm w-full"
                            :disabled="editMappingSchemeBusy"
                            @change="onEditMappingSchemeChange"
                          >
                            <option v-for="scheme in mappingSchemesList" :key="scheme.name" :value="scheme.name">
                              {{ scheme.name }}{{ scheme.is_active ? ' ★' : '' }} ({{ scheme.mapping_count }})
                            </option>
                          </select>
                          <p v-if="editMappingSchemeError" class="mt-2 text-xs text-rose-600">{{ editMappingSchemeError }}</p>
                          <p v-else class="mt-2 text-xs text-amber-700/80">
                            {{ $t('excelExecution.mappingSchemes.hint') }}
                          </p>
                        </div>

                        <div class="space-y-3">
                          <div>
                            <p class="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">{{ $t('excelExecution.monitorTarget') }}</p>
                            <div class="grid grid-cols-2 gap-2">
                              <button
                                type="button"
                                class="rounded-2xl border px-3 py-2 text-sm font-medium transition"
                                :class="editKeyMonitorTargetField === 'ori_step' ? 'border-sky-500 bg-sky-50 text-sky-700' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'"
                                @click="setEditKeyMonitorTargetField('ori_step')"
                              >
                                {{ $t('excelExecution.monitorTargetOriStep') }}
                              </button>
                              <button
                                type="button"
                                class="rounded-2xl border px-3 py-2 text-sm font-medium transition"
                                :class="editKeyMonitorTargetField === 'pre_script' ? 'border-sky-500 bg-sky-50 text-sky-700' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'"
                                @click="setEditKeyMonitorTargetField('pre_script')"
                              >
                                {{ $t('excelExecution.monitorTargetPreScript') }}
                              </button>
                            </div>
                          </div>

                          <div class="grid grid-cols-2 gap-2">
                            <button
                              type="button"
                              class="btn btn-primary btn-sm"
                              :disabled="editKeyMonitorActive || editKeyMonitorStarting"
                              @click="startEditKeyMonitor"
                            >
                              {{ $t('excelExecution.monitorStart') }}
                            </button>
                            <button
                              type="button"
                              class="btn btn-secondary btn-sm"
                              :disabled="!editKeyMonitorActive && !editKeyMonitorStarting"
                              @click="stopEditKeyMonitor"
                            >
                              {{ $t('excelExecution.monitorStop') }}
                            </button>
                          </div>

                          <div>
                            <label class="form-label text-xs">{{ $t('excelExecution.monitorSequence') }}</label>
                            <textarea
                              :value="editKeyMonitorWorkingSequence"
                              class="form-input w-full min-h-[180px] resize-y"
                              :placeholder="$t('excelExecution.monitorPlaceholder')"
                              :readonly="editKeyMonitorActive || editKeyMonitorStarting"
                              @input="handleEditKeyMonitorSequenceInput"
                            ></textarea>
                            <p v-if="editKeyMonitorActive && !editKeyMonitorSequence" class="mt-2 text-xs text-slate-500">
                              {{ $t('excelExecution.monitorListening') }}
                            </p>
                          </div>

                          <div v-if="editKeyMonitorError" class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
                            {{ editKeyMonitorError }}
                          </div>

                          <div class="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                            <button
                              type="button"
                              class="btn btn-primary btn-sm"
                              :disabled="!canApplyEditKeyMonitorSequence"
                              @click="applyEditKeyMonitorSequenceToField"
                            >
                              {{ $t('excelExecution.monitorApply') }}
                            </button>
                            <button
                              type="button"
                              class="btn btn-secondary btn-sm"
                              :disabled="!editKeyMonitorSequenceDirty"
                              @click="restoreEditKeyMonitorSequence"
                            >
                              {{ $t('excelExecution.monitorRestore') }}
                            </button>
                            <button
                              type="button"
                              class="btn btn-secondary btn-sm"
                              :disabled="!editKeyMonitorWorkingSequence"
                              @click="clearEditKeyMonitorContent"
                            >
                              {{ $t('excelExecution.monitorClear') }}
                            </button>
                          </div>
                        </div>
                      </aside>
                    </div>

                    <div class="excel-edit-modal-right min-h-0 flex flex-col">
                      <section class="rounded-[28px] border border-slate-200 bg-white p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
                        <div class="flex-shrink-0 flex flex-wrap items-start justify-between gap-3 mb-3">
                          <div>
                            <h4 class="text-sm font-semibold text-slate-900">{{ $t('excelExecution.devicePreviewTitle') }}</h4>
                            <p class="text-xs text-slate-500">{{ editDevicePreviewIdentityLabel }}</p>
                            <p v-if="editDevicePreviewTargetFileName" class="mt-1 text-xs font-medium text-emerald-700">
                              {{ $t('excelExecution.devicePreviewTargetName', { name: editDevicePreviewTargetFileName }) }}
                            </p>
                            <p v-else class="mt-1 text-xs text-rose-600">
                              {{ $t('excelExecution.devicePreviewMissingTargetName') }}
                            </p>
                          </div>
                          <div class="flex flex-wrap gap-2">
                            <button class="btn btn-secondary btn-sm" @click="handleEditDevicePreviewRefresh" :disabled="editDevicePreviewLoading">
                              {{ editDevicePreviewLoading ? $t('excelExecution.devicePreviewRefreshing') : $t('excelExecution.refreshDevicePreview') }}
                            </button>
                            <button
                              v-if="editDevicePreviewSelectionActive || editDevicePreviewSelectionCrop"
                              class="btn btn-secondary btn-sm"
                              @click="clearEditDevicePreviewSelection"
                            >
                              {{ $t('excelExecution.cancelDevicePreviewSelection') }}
                            </button>
                            <button
                              class="btn btn-primary btn-sm"
                              @click="saveEditDevicePreviewSelection"
                              :disabled="!editDevicePreviewSelectionCrop || editDevicePreviewSaving || !editDevicePreviewTargetFileName"
                            >
                              {{ editDevicePreviewSaving ? $t('excelExecution.savingDevicePreviewSelection') : $t('excelExecution.saveDevicePreviewSelection') }}
                            </button>
                          </div>
                        </div>

                        <label class="flex-shrink-0 mb-3 grid gap-1 max-w-xs">
                          <span class="text-xs font-medium text-slate-600">{{ $t('excelExecution.devicePreviewSourceLabel') }}</span>
                          <select v-model="editDevicePreviewSource" class="form-select form-select-sm">
                            <option :value="EDIT_DEVICE_PREVIEW_SOURCE_ADB">{{ $t('excelExecution.devicePreviewSourceAdb') }}</option>
                            <option :value="EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD">{{ $t('excelExecution.devicePreviewSourceCaptureCard') }}</option>
                          </select>
                        </label>

                        <div v-if="editDevicePreviewUsesCaptureCard" class="flex-shrink-0 mb-3 grid gap-1 max-w-md">
                          <span class="text-xs font-medium text-slate-600">{{ $t('excelExecution.captureCardDeviceLabel') }}</span>
                          <div class="flex gap-2">
                            <select
                              :value="editCaptureCardActiveDeviceId"
                              class="form-select form-select-sm flex-1 min-w-0"
                              :disabled="editCaptureCardListLoading || editCaptureCardSwitching"
                              @change="onEditCaptureCardDeviceSelectChange"
                            >
                              <option v-if="editCaptureCardDevicesList.length === 0" :value="editCaptureCardActiveDeviceId">
                                {{ editCaptureCardListLoading ? $t('excelExecution.captureCardScanning') : $t('excelExecution.captureCardNoDevices') }}
                              </option>
                              <option
                                v-for="dev in editCaptureCardDevicesList"
                                :key="dev.device_id"
                                :value="dev.device_id"
                              >
                                {{ dev.label }}
                              </option>
                            </select>
                            <button
                              type="button"
                              class="btn btn-secondary btn-sm whitespace-nowrap"
                              :disabled="editCaptureCardListLoading || editCaptureCardSwitching"
                              @click="loadEditCaptureCardDevices"
                            >
                              {{ editCaptureCardListLoading ? $t('excelExecution.captureCardScanning') : $t('excelExecution.captureCardRescan') }}
                            </button>
                          </div>
                          <span v-if="editCaptureCardError" class="text-[11px] text-rose-600">{{ editCaptureCardError }}</span>
                          <span v-else class="text-[11px] text-slate-500">{{ $t('excelExecution.captureCardHint') }}</span>
                        </div>

                        <div
                          ref="editDevicePreviewFrameRef"
                          class="excel-device-preview-frame excel-device-preview-frame--fill"
                          :class="{
                            'excel-device-preview-frame--selectable': editDevicePreviewUrl,
                            'excel-device-preview-frame--selecting': editDevicePreviewSelectionActive,
                          }"
                          @pointerdown="beginEditDevicePreviewSelection"
                          @pointermove="updateEditDevicePreviewSelection"
                          @pointerup="finishEditDevicePreviewSelection"
                          @pointercancel="finishEditDevicePreviewSelection"
                        >
                          <template v-if="editDevicePreviewUrl">
                            <img
                              ref="editDevicePreviewImageRef"
                              :src="editDevicePreviewUrl"
                              :alt="$t('excelExecution.devicePreviewTitle')"
                              class="excel-device-preview-image"
                              draggable="false"
                              @load="handleEditDevicePreviewImageLoad"
                              @error="handleEditDevicePreviewImageError"
                            >
                            <div v-if="editDevicePreviewSelectionRect" class="excel-device-preview-selection-layer">
                              <div class="excel-device-preview-selection-box" :style="editDevicePreviewSelectionStyle"></div>
                            </div>
                          </template>
                          <div v-else class="excel-device-preview-state">
                            <span v-if="editDevicePreviewLoading">{{ $t('excelExecution.devicePreviewLoading') }}</span>
                            <span v-else-if="editDevicePreviewError">{{ editDevicePreviewError }}</span>
                            <span v-else>{{ $t('excelExecution.devicePreviewEmpty') }}</span>
                          </div>
                        </div>

                        <div class="flex-shrink-0 mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                          <span v-if="editDevicePreviewSelectionCrop">
                            {{ $t('excelExecution.devicePreviewSelectionReady', {
                              width: editDevicePreviewSelectionCrop.width,
                              height: editDevicePreviewSelectionCrop.height,
                            }) }}
                          </span>
                          <span v-else>{{ $t('excelExecution.devicePreviewSelectionHint') }}</span>
                          <span v-if="editDevicePreviewCapturedLabel">
                            {{ $t('excelExecution.devicePreviewCapturedAt', { time: editDevicePreviewCapturedLabel }) }}
                          </span>
                        </div>

                        <label class="flex-shrink-0 mt-3 grid gap-1">
                          <span class="text-xs font-medium text-slate-600">{{ $t('excelExecution.devicePreviewSaveDirLabel') }}</span>
                          <input
                            v-model="editDevicePreviewSaveDir"
                            type="text"
                            class="form-input form-input-sm"
                            :placeholder="$t('excelExecution.devicePreviewSaveDirPlaceholder')"
                          >
                          <span class="text-[11px] text-slate-500">{{ $t('excelExecution.devicePreviewSaveDirNote') }}</span>
                        </label>

                        <div v-if="editDevicePreviewSaveMessage" class="flex-shrink-0 mt-2 text-xs text-emerald-600">
                          {{ editDevicePreviewSaveMessage }}
                        </div>
                        <div v-if="editDevicePreviewError && editDevicePreviewUrl" class="flex-shrink-0 mt-2 text-xs text-rose-600">
                          {{ editDevicePreviewError }}
                        </div>
                      </section>
                    </div>
                  </div>

                  <footer class="flex-shrink-0 flex flex-wrap justify-end items-center gap-3 px-6 py-4 border-t border-slate-200">
                    <button
                      class="btn btn-secondary mr-auto"
                      :disabled="savingCaseFields || executingEditCaseSteps || !canExecuteEditCaseSteps"
                      @click="executeEditCaseSteps"
                      :title="canExecuteEditCaseSteps ? '' : $t('common.deviceRequired')"
                    >
                      {{ executingEditCaseSteps ? $t('excelExecution.executingCaseSteps') : $t('excelExecution.executeCaseSteps') }}
                    </button>
                    <span v-if="editCaseStepsError" class="text-sm text-rose-600">{{ editCaseStepsError }}</span>
                    <span v-else-if="editCaseStepsMessage" class="text-sm text-emerald-600">{{ editCaseStepsMessage }}</span>
                    <button class="btn btn-secondary" @click="closeCaseEditModal" :disabled="savingCaseFields || executingEditCaseSteps">
                      {{ $t('common.cancel') }}
                    </button>
                    <button class="btn btn-primary" @click="saveCaseFields" :disabled="savingCaseFields || executingEditCaseSteps">
                      {{ savingCaseFields ? $t('excelExecution.saving') : $t('common.saveChanges') }}
                    </button>
                  </footer>
                </div>
              </div>
            </div>

        <!-- 结果切换小弹窗（Teleport 到 body，避免被表格 overflow 裁剪） -->
        <Teleport to="body">
          <div
            v-if="resultPopoverIndex !== null"
            class="fixed z-[9999] bg-white border border-slate-200 rounded-lg shadow-lg py-1 min-w-[100px]"
            :style="{ left: resultPopoverPos.left + 'px', top: resultPopoverPos.top + 'px' }"
            @click.stop
          >
            <button
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-green-50 text-green-700 flex items-center gap-2"
              @click="setResultValue(resultPopoverIndex, 'PASS')"
            >
              <span class="w-2 h-2 rounded-full bg-green-500"></span>
              PASS
            </button>
            <button
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-red-50 text-red-700 flex items-center gap-2"
              @click="setResultValue(resultPopoverIndex, 'Fail')"
            >
              <span class="w-2 h-2 rounded-full bg-red-500"></span>
              Fail
            </button>
            <button
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-amber-50 text-amber-700 flex items-center gap-2"
              @click="setResultValue(resultPopoverIndex, 'NT')"
            >
              <span class="w-2 h-2 rounded-full bg-amber-500"></span>
              NT
            </button>
            <button
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50 text-blue-700 flex items-center gap-2"
              @click="setResultValue(resultPopoverIndex, 'NA')"
            >
              <span class="w-2 h-2 rounded-full bg-blue-500"></span>
              NA
            </button>
            <button
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 text-gray-500 flex items-center gap-2"
              @click="setResultValue(resultPopoverIndex, '')"
            >
              <span class="w-2 h-2 rounded-full bg-gray-300"></span>
              {{ $t('common.clear') }}
            </button>
          </div>
        </Teleport>

        <UploadExcelConfirmModal
          :visible="uploadConfirmVisible"
          @confirm="confirmUpload"
          @cancel="cancelUpload"
        />

        <!-- 校验文件夹提醒弹窗 -->
        <Transition name="vfa-fade">
          <div v-if="verifyFolderAlertVisible" class="fixed inset-0 bg-black/40 flex items-center justify-center z-[9999]" @click.self="onVerifyFolderContinue">
            <div class="excel-vfa-card">
              <div class="excel-vfa-icon">📂</div>
              <h3 class="excel-vfa-title">{{ $t('excelExecution.alerts.selectVerifyFolderFirst') }}</h3>
              <p class="excel-vfa-desc">{{ $t('excelExecution.alerts.verifyFolderHint') }}</p>
              <div class="excel-vfa-actions">
                <button class="btn btn-secondary" @click="onVerifyFolderContinue">{{ $t('excelExecution.alerts.continueAnyway') }}</button>
                <button class="btn btn-primary" @click="onVerifyFolderGoSelect">{{ $t('excelExecution.alerts.goSelectFolder') }}</button>
              </div>
            </div>
          </div>
        </Transition>
          </template>

<script setup>
import { ref, onMounted, computed, watch, onUnmounted, nextTick, reactive } from 'vue'
import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import UploadExcelConfirmModal from '../components/UploadExcelConfirmModal.vue'
import { useUploadExcelConfirm } from '../composables/useUploadExcelConfirm.js'

const { t } = useI18n({ useScope: 'global' })

const createEmptyImageModelStatus = () => ({
  imported_models: [],
  active_model: null,
  compare_backend: 'opencv',
  dependencies: {
    missing: [],
    install_steps: [],
    install_commands: [],
    notes: [],
    python_version: '',
    recommended_python_version: '3.12'
  },
  recommended_model: {
    name: 'DINOv2-Base',
    repo_id: 'facebook/dinov2-base'
  }
})

const selectedDevice = ref('')
const excelFiles = ref([])
const selectedFile = ref('')
const excelAnalysis = ref(null)
const validationResult = ref(null)
const executionResults = ref([])
const executionLogContainer = ref(null)
const rowIndex = ref(1)
const loadingFiles = ref(false)
const loadingAnalysis = ref(false)
const executingRows = ref({})
const stopExecutionFlags = ref({})
const executionAbortControllers = ref({})
const selectedRows = ref([])
const filterResult = ref('')
const searchKeyword = ref('')
const rowScreenshots = ref({})
const rowResultMeta = ref({})
const rowAllResults = ref({})
const rowExecutionProgress = ref({})
const showValidationResultModal = ref(false)
const showScreenshotModal = ref(false)
const modalScreenshotUrl = ref('')
const modalVideoUrl = ref('')
const showVideoPlayer = ref(false)
const videoConverting = ref(false)  // 视频是否正在转换中
// 根据视频 URL 扩展名返回正确的 MIME 类型
const videoMimeType = computed(() => {
  const url = modalVideoUrl.value || ''
  if (url.endsWith('.webm')) return 'video/webm'
  if (url.endsWith('.avi')) return 'video/x-msvideo'
  return 'video/mp4'
})
const screenshotLoadError = ref(false)
const screenshotTimestamp = ref(Date.now())
const modalVerifyImageUrl = ref('')
const modalVerifyImageName = ref('')
const modalVerifyImagePlaceholder = ref('')
const modalResultTitle = ref('')
const modalResultStatus = ref('')
const modalResultScore = ref(null)
// 多次 ASSERT 校验：列表 + 当前展示的索引；列表为空时表示单次校验/旧逻辑
const modalAssertResults = ref([])
const modalAssertActiveIndex = ref(0)
const modalOverallVerifyResult = ref('')
// 截图保存相关状态
const screenshotSaveFileName = ref('')
const isRegionSelectMode = ref(false)
const regionStart = ref(null)  // { x, y } 相对图片容器的坐标
const regionEnd = ref(null)    // { x, y }
const screenshotImgRef = ref(null)
const screenshotContainerRef = ref(null)
const showVerifyImageModal = ref(false)
const showCaseEditModal = ref(false)
const verifyImageUrl = ref('')
const verifyImagePreviewName = ref('')
// 多张校验图预览：每张含 {name, url, relativePath, missing}；为空表示单张/旧逻辑
const verifyImagePreviewList = ref([])
const verifyImagePreviewActiveIndex = ref(0)
const verifyImageFolderInput = ref(null)
const verifyImageFolderName = ref('')
const verifyImageFileCount = ref(0)

// 校验文件夹提醒弹窗
const verifyFolderAlertVisible = ref(false)
const verifyFolderAlertDismissed = ref(false)
const verifyFolderAlertResolve = ref(null)
const showVerifyFolderAlert = () => {
  if (verifyFolderAlertDismissed.value) return Promise.resolve('continue')
  return new Promise((resolve) => {
    verifyFolderAlertResolve.value = resolve
    verifyFolderAlertVisible.value = true
  })
}
const onVerifyFolderContinue = () => {
  verifyFolderAlertVisible.value = false
  verifyFolderAlertDismissed.value = true
  verifyFolderAlertResolve.value?.('continue')
}
const onVerifyFolderGoSelect = () => {
  verifyFolderAlertVisible.value = false
  verifyFolderAlertResolve.value?.('select')
  triggerVerifyImageFolderPicker()
}
const localVerifyImageMap = ref({})
const pendingVerifyImageRequest = ref(null)
const currentPage = ref(1)
const jumpPage = ref(1)
const pageSize = ref(20)
const isBatchExecuting = ref(false)
const hasExecutionInProgress = computed(() => {
  if (isBatchExecuting.value) {
    return true
  }

  return Object.values(executingRows.value).some(Boolean)
})
const savingCaseFields = ref(false)
const batchExecutionState = reactive({
  active: false,
  status: 'idle',
  label: '',
  total: 0,
  completed: 0,
  currentRowIndex: null,
  currentCaseTitle: ''
})
const fileSelectorPanelExpanded = ref(false)
const modelSelectorPanelExpanded = ref(false)
const reportPanelExpanded = ref(false)
const imageCompareBackendConfirmed = ref(false)
const matchThreshold = ref(0.8)
const screenshotSource = ref('adb')
const executionMode = ref('single')
const loopType = ref('finite')
const loopCount = ref(10)
const showExecutionSettings = ref(false)
const enableVerification = ref(true)
const enableRecording = ref(true)
const MAX_PERSISTED_EXECUTION_RESULTS = 200
const EXCEL_EXECUTION_STORAGE_KEY = 'checkpilot.excelExecution.state'
const VERIFY_IMAGE_FOLDER_DB_NAME = 'checkpilot.excelExecution.directoryHandles'
const VERIFY_IMAGE_FOLDER_STORE_NAME = 'handles'
const VERIFY_IMAGE_FOLDER_HANDLE_KEY = 'verify-image-folder'
const editingCaseIndex = ref(null)
const editingCaseExcelRow = ref(null)
const editingCaseForm = reactive({
  title: '',
  ori_step: '',
  pre_script: '',
  verify_image: '',
  test_result: ''
})
const editKeyMonitorActive = ref(false)
const editKeyMonitorStarting = ref(false)
const editKeyMonitorSequence = ref('')
const editKeyMonitorEditableSequence = ref('')
const editKeyMonitorSequenceDirty = ref(false)
const editKeyMonitorTargetField = ref('pre_script')
const editKeyMonitorMappings = ref({})
const editKeyMonitorError = ref('')

// 映射规则方案（在编辑模态里选择/切换）
const mappingSchemesList = ref([])
const activeMappingSchemeName = ref('')
const editMappingSchemeBusy = ref(false)
const editMappingSchemeError = ref('')

// 设备画面 + 框选保存截图
const EDIT_DEVICE_PREVIEW_SOURCE_ADB = 'adb'
const EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD = 'capture_card'
const EDIT_DEVICE_PREVIEW_REFRESH_INTERVAL = 3000
const editDevicePreviewSource = ref(EDIT_DEVICE_PREVIEW_SOURCE_ADB)
const editDevicePreviewUrl = ref('')
const editDevicePreviewLabel = ref('')
const editDevicePreviewLoading = ref(false)
const editDevicePreviewError = ref('')
const editDevicePreviewCapturedAt = ref(0)
const editDevicePreviewSaveDir = ref('')
const editDevicePreviewSelectionActive = ref(false)
const editDevicePreviewSelectionRect = ref(null)
const editDevicePreviewSelectionCrop = ref(null)
const editDevicePreviewSaving = ref(false)
const editDevicePreviewSaveMessage = ref('')
const editDevicePreviewFrameRef = ref(null)
const editDevicePreviewImageRef = ref(null)
let editDevicePreviewTimer = null
let editDevicePreviewRequestActive = false
let editDevicePreviewSelectionPointerId = null
let editDevicePreviewSelectionStartPoint = null
const editDevicePreviewStreamVersion = ref(0)

// 编辑模态：采集卡设备选择
const editCaptureCardDevicesList = ref([])
const editCaptureCardActiveDeviceId = ref(null)
const editCaptureCardListLoading = ref(false)
const editCaptureCardSwitching = ref(false)
const editCaptureCardError = ref('')
let editCaptureCardListLoaded = false

// 执行步骤按钮
const executingEditCaseSteps = ref(false)
const editCaseStepsMessage = ref('')
const editCaseStepsError = ref('')
const imageModelStatus = ref(createEmptyImageModelStatus())
const loadingImageModelStatus = ref(false)
const downloadingImageModel = ref(false)
const selectingImageModel = ref(false)
const deletingImageModel = ref(false)
const clearingImageModelSelection = ref(false)
const imageModelStatusError = ref('')
const imageModelMessage = ref('')
const imageReports = ref([])
const loadingImageReports = ref(false)
const imageReportsError = ref('')
let editKeyMonitorStatusTimer = null
let editKeyMonitorStatusRequestActive = false
let isRestoringExecutionState = false

// 路由实例
const router = useRouter()
const route = useRoute()

const readPersistedExecutionState = () => {
  try {
    const raw = localStorage.getItem(EXCEL_EXECUTION_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (error) {
    console.error('读取页面状态失败:', error)
    return null
  }
}

const supportsPersistentDirectoryHandle = () => {
  return typeof window !== 'undefined'
    && typeof window.showDirectoryPicker === 'function'
    && typeof window.indexedDB !== 'undefined'
}

const openVerifyImageFolderHandleDb = () => {
  return new Promise((resolve, reject) => {
    if (!supportsPersistentDirectoryHandle()) {
      resolve(null)
      return
    }

    const request = window.indexedDB.open(VERIFY_IMAGE_FOLDER_DB_NAME, 1)

    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(VERIFY_IMAGE_FOLDER_STORE_NAME)) {
        db.createObjectStore(VERIFY_IMAGE_FOLDER_STORE_NAME)
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('打开目录句柄存储失败'))
  })
}

const readPersistedVerifyImageFolderHandle = async () => {
  const db = await openVerifyImageFolderHandleDb()
  if (!db) {
    return null
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(VERIFY_IMAGE_FOLDER_STORE_NAME, 'readonly')
    const store = transaction.objectStore(VERIFY_IMAGE_FOLDER_STORE_NAME)
    const request = store.get(VERIFY_IMAGE_FOLDER_HANDLE_KEY)

    request.onsuccess = () => resolve(request.result || null)
    request.onerror = () => reject(request.error || new Error('读取目录句柄失败'))
    transaction.oncomplete = () => db.close()
    transaction.onerror = () => db.close()
    transaction.onabort = () => db.close()
  })
}

const persistVerifyImageFolderHandle = async (directoryHandle) => {
  const db = await openVerifyImageFolderHandleDb()
  if (!db) {
    return
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(VERIFY_IMAGE_FOLDER_STORE_NAME, 'readwrite')
    const store = transaction.objectStore(VERIFY_IMAGE_FOLDER_STORE_NAME)
    const request = store.put(directoryHandle, VERIFY_IMAGE_FOLDER_HANDLE_KEY)

    request.onsuccess = () => resolve(true)
    request.onerror = () => reject(request.error || new Error('保存目录句柄失败'))
    transaction.oncomplete = () => db.close()
    transaction.onerror = () => db.close()
    transaction.onabort = () => db.close()
  })
}

const isDirectoryHandle = (value) => {
  return Boolean(value && typeof value === 'object' && value.kind === 'directory')
}

const queryVerifyImageFolderPermission = async (directoryHandle) => {
  if (!isDirectoryHandle(directoryHandle)) {
    return 'denied'
  }

  if (typeof directoryHandle.queryPermission !== 'function') {
    return 'granted'
  }

  try {
    return await directoryHandle.queryPermission({ mode: 'read' })
  } catch (error) {
    console.error('查询目录权限失败:', error)
    return 'denied'
  }
}

const collectVerifyImageFilesFromDirectory = async (directoryHandle, currentPath, nextImageMap) => {
  // 先收集所有条目（File System Access API 的迭代器本身是串行的）
  const entries = []
  for await (const entry of directoryHandle.values()) {
    entries.push(entry)
  }

  const fileEntries = entries.filter(e => e.kind === 'file')
  const dirEntries = entries.filter(e => e.kind === 'directory')

  // 并行处理当前目录的所有文件，大幅加速大文件夹扫描
  if (fileEntries.length > 0) {
    const results = await Promise.all(
      fileEntries.map(async (entry) => {
        try {
          const file = await entry.getFile()
          const isImageFile = file.type.startsWith('image/') || /\.(png|jpg|jpeg|bmp|webp)$/i.test(file.name)
          if (!isImageFile) return null

          const key = normalizeVerifyImageName(file.name)
          if (!key) return null

          return {
            key,
            name: file.name,
            relativePath: currentPath ? `${currentPath}/${file.name}` : file.name,
            url: URL.createObjectURL(file),
            file,
          }
        } catch {
          return null
        }
      })
    )

    // 合并并行结果，跳过重复 key
    for (const result of results) {
      if (result && !nextImageMap[result.key]) {
        nextImageMap[result.key] = {
          name: result.name,
          relativePath: result.relativePath,
          url: result.url,
          file: result.file,
        }
      }
    }
  }

  // 并行处理子目录
  if (dirEntries.length > 0) {
    await Promise.all(
      dirEntries.map(entry => {
        const nestedPath = currentPath ? `${currentPath}/${entry.name}` : entry.name
        return collectVerifyImageFilesFromDirectory(entry, nestedPath, nextImageMap)
      })
    )
  }
}

const finalizeVerifyImageFolderSelection = (nextImageMap, folderName, pendingRequest = null) => {
  clearLocalVerifyImageCache()
  localVerifyImageMap.value = nextImageMap
  verifyImageFileCount.value = Object.keys(nextImageMap).length
  verifyImageFolderName.value = folderName || t('excelExecution.localFolderSelected')
  persistExecutionState()

  if (!pendingRequest) {
    return
  }

  if (pendingRequest.mode === 'preview') {
    if (!applyVerifyImagePreview(pendingRequest.imageName)) {
      alert(t('excelExecution.alerts.sameImageNotFound', { name: pendingRequest.imageName }))
    }
    return
  }

  if (pendingRequest.mode === 'result') {
    const matchedEntry = getLocalVerifyImageEntry(pendingRequest.imageName)
    openExecutionResultModal(pendingRequest.rowIndex, matchedEntry)
    if (!matchedEntry) {
      alert(t('excelExecution.alerts.sameImageNotFound', { name: pendingRequest.imageName }))
    }
  }
}

const applyVerifyImageDirectoryHandle = async (directoryHandle, options = {}) => {
  const { persist = true, pendingRequest = null } = options
  const nextImageMap = {}
  const rootPath = directoryHandle?.name || ''

  await collectVerifyImageFilesFromDirectory(directoryHandle, rootPath, nextImageMap)
  finalizeVerifyImageFolderSelection(nextImageMap, directoryHandle?.name || '', pendingRequest)

  if (persist) {
    await persistVerifyImageFolderHandle(directoryHandle)
  }
}

const restorePersistedVerifyImageFolder = async () => {
  if (!supportsPersistentDirectoryHandle()) {
    return false
  }

  try {
    const directoryHandle = await readPersistedVerifyImageFolderHandle()
    if (!isDirectoryHandle(directoryHandle)) {
      return false
    }

    const permission = await queryVerifyImageFolderPermission(directoryHandle)
    if (permission !== 'granted') {
      return false
    }

    await applyVerifyImageDirectoryHandle(directoryHandle, { persist: false })
    return true
  } catch (error) {
    console.error('恢复校验图片文件夹失败:', error)
    return false
  }
}

const persistExecutionState = () => {
  if (isRestoringExecutionState) {
    return
  }

  try {
    localStorage.setItem(EXCEL_EXECUTION_STORAGE_KEY, JSON.stringify({
      selectedDevice: selectedDevice.value || '',
      selectedFile: selectedFile.value || '',
      imageCompareBackendConfirmed: Boolean(imageCompareBackendConfirmed.value),
      rowIndex: rowIndex.value,
      filterResult: filterResult.value,
      searchKeyword: searchKeyword.value,
      currentPage: currentPage.value,
      jumpPage: jumpPage.value,
      pageSize: pageSize.value,
      selectedRows: Array.isArray(selectedRows.value) ? selectedRows.value : [],
      executionResults: executionResults.value.slice(-MAX_PERSISTED_EXECUTION_RESULTS),
      rowScreenshots: rowScreenshots.value,
      rowResultMeta: rowResultMeta.value,
      verifyImageFolderName: verifyImageFolderName.value || '',
      hadLocalVerifyImages: verifyImageFileCount.value > 0,
      matchThreshold: matchThreshold.value,
      screenshotSource: screenshotSource.value,
      executionMode: executionMode.value,
      loopType: loopType.value,
      loopCount: loopCount.value,
      enableVerification: enableVerification.value,
      enableRecording: enableRecording.value,
    }))
  } catch (error) {
    console.error('保存页面状态失败:', error)
  }
}

const applyRowResultMetaToAnalysis = () => {
  if (!excelAnalysis.value?.valid_rows) {
    return
  }

  Object.entries(rowResultMeta.value || {}).forEach(([rowIndexKey, meta]) => {
    const numericIndex = Number(rowIndexKey)
    const rowData = excelAnalysis.value?.valid_rows?.[numericIndex - 1]
    if (rowData && meta?.verify_result) {
      rowData.result = meta.verify_result
    }
  })
}

const restoreSavedDevice = async (savedDevice) => {
  if (!savedDevice) {
    return ''
  }

  // 先检查后端是否已选中该设备，避免不必要的 /api/devices/list 调用
  // （该接口内部会触发 prune_current_device_if_offline，可能干扰首页设备列表）
  try {
    const currentResponse = await fetch('/api/devices/current')
    if (currentResponse.ok) {
      const currentData = await currentResponse.json()
      if (currentData.device === savedDevice) {
        return savedDevice
      }
    }
  } catch {}

  try {
    const listResponse = await fetch('/api/devices/list')
    if (!listResponse.ok) {
      return ''
    }

    const listData = await listResponse.json()
    const devices = Array.isArray(listData.devices) ? listData.devices : []
    const deviceIndex = devices.indexOf(savedDevice)
    if (deviceIndex < 0) {
      return ''
    }

    const selectResponse = await fetch('/api/devices/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ device_index: deviceIndex })
    })

    if (!selectResponse.ok) {
      return ''
    }

    const selectData = await selectResponse.json()
    return selectData.status === 'success' ? selectData.device || savedDevice : ''
  } catch (error) {
    console.error('恢复设备选择失败:', error)
    return ''
  }
}

const restoreExecutionState = async () => {
  const savedState = readPersistedExecutionState()
  if (!savedState) {
    return
  }

  isRestoringExecutionState = true
  try {
    if (!selectedDevice.value && savedState.selectedDevice) {
      const restoredDevice = await restoreSavedDevice(savedState.selectedDevice)
      if (restoredDevice) {
        selectedDevice.value = restoredDevice
      }
    }

    if (savedState.selectedFile && excelFiles.value.includes(savedState.selectedFile)) {
      selectedFile.value = savedState.selectedFile
      await analyzeFile({ silent: true, resetView: false })
    }

    imageCompareBackendConfirmed.value = Boolean(savedState.imageCompareBackendConfirmed || activeImageModelName.value)

    if (typeof savedState.matchThreshold === 'number' && savedState.matchThreshold >= 0 && savedState.matchThreshold <= 1) {
      matchThreshold.value = savedState.matchThreshold
    }
    if (savedState.screenshotSource === 'capture_card') {
      screenshotSource.value = 'capture_card'
    }
    if (['single', 'loop_row', 'loop_list'].includes(savedState.executionMode)) {
      executionMode.value = savedState.executionMode
    }
    if (['finite', 'infinite'].includes(savedState.loopType)) {
      loopType.value = savedState.loopType
    }
    if (typeof savedState.loopCount === 'number' && savedState.loopCount >= 1) {
      loopCount.value = Math.floor(savedState.loopCount)
    }
    if (typeof savedState.enableVerification === 'boolean') {
      enableVerification.value = savedState.enableVerification
    }
    if (typeof savedState.enableRecording === 'boolean') {
      enableRecording.value = savedState.enableRecording
    }

    rowIndex.value = Number(savedState.rowIndex) || 1
    filterResult.value = savedState.filterResult || ''
    searchKeyword.value = savedState.searchKeyword || ''
    currentPage.value = Number(savedState.currentPage) || 1
    jumpPage.value = Number(savedState.jumpPage) || currentPage.value
    pageSize.value = Number(savedState.pageSize) || 20
    selectedRows.value = Array.isArray(savedState.selectedRows) ? savedState.selectedRows : []
    executionResults.value = Array.isArray(savedState.executionResults) ? savedState.executionResults : []
    rowScreenshots.value = savedState.rowScreenshots && typeof savedState.rowScreenshots === 'object' ? savedState.rowScreenshots : {}
    rowResultMeta.value = savedState.rowResultMeta && typeof savedState.rowResultMeta === 'object' ? savedState.rowResultMeta : {}
    applyRowResultMetaToAnalysis()

    const restoredVerifyFolder = await restorePersistedVerifyImageFolder()
    if (!restoredVerifyFolder && savedState.hadLocalVerifyImages && savedState.verifyImageFolderName) {
      executionResults.value.push({
        status: 'info',
        message: t('excelExecution.alerts.refreshFolderReminder', { name: savedState.verifyImageFolderName })
      })
    }
  } finally {
    isRestoringExecutionState = false
    persistExecutionState()
  }
}

const clearExecutionAbortController = (index) => {
  if (!executionAbortControllers.value[index]) {
    return
  }

  delete executionAbortControllers.value[index]
  executionAbortControllers.value = { ...executionAbortControllers.value }
}

const abortExecution = (index) => {
  const controller = executionAbortControllers.value[index]
  if (controller && !controller.signal.aborted) {
    controller.abort()
  }
}

const isAbortError = (error) => {
  if (!error) {
    return false
  }

  const message = String(error.message || error || '').toLowerCase()
  return error.name === 'AbortError' || message.includes('abort') || message.includes('aborted')
}

const confirmStopExecutionBeforeLeave = () => {
  if (!hasExecutionInProgress.value) {
    return true
  }

  const confirmed = confirm(t('excelExecution.alerts.leaveWhileExecutingConfirm'))
  if (!confirmed) {
    return false
  }

  stopAllExecution()
  return true
}

// 导航守卫，处理页面离开时的确认

onBeforeRouteLeave((to, from, next) => {
  if (!confirmStopExecutionBeforeLeave()) {
    next(false)
    return
  }

  // 检查是否有截图
  if (Object.keys(rowScreenshots.value).length > 0) {
    const confirmLeave = confirm(t('excelExecution.alerts.leavePageConfirm'))
    if (confirmLeave) {
      // 调用API删除所有截图
      fetch('/api/screenshot/clear', {
        method: 'DELETE'
      })
      .then(response => response.json())
      .then(data => {
        console.log('清除截图成功:', data)
        // 清除前端截图状态
        Object.keys(rowScreenshots.value).forEach(key => {
          delete rowScreenshots.value[key]
        })
        // 强制响应式更新
        rowScreenshots.value = { ...rowScreenshots.value }
        next()
      })
      .catch(error => {
        console.error('清除截图失败:', error)
        // 即使API调用失败，也要继续导航
        rowScreenshots.value = {}
        next()
      })
    } else {
      // 取消导航
      next(false)
    }
  } else {
    // 没有截图，直接离开
    next()
  }
})

onUnmounted(() => {
  Object.keys(executionAbortControllers.value).forEach((key) => {
    abortExecution(key)
  })
  void stopAndResetEditKeyMonitor()
  clearLocalVerifyImageCache()
  document.removeEventListener('click', closeResultPopover)
})

 



// 计算属性：筛选和搜索后的行
const filteredRows = computed(() => {
  if (!excelAnalysis.value || !excelAnalysis.value.valid_rows) return []
  let items = excelAnalysis.value.valid_rows.map((row, i) => ({ row, idx: i + 1 }))
  if (filterResult.value) {
    if (filterResult.value === 'empty') {
      items = items.filter(x => !x.row.test_result || x.row.test_result === '')
    } else {
      items = items.filter(x => {
        const result = x.row.test_result || ''
        return result.toUpperCase() === filterResult.value.toUpperCase()
      })
    }
  }
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    items = items.filter(x => {
      if (x.row.title && String(x.row.title).toLowerCase().includes(keyword)) return true
      if (x.row.verify_image && String(x.row.verify_image).toLowerCase().includes(keyword)) return true
      return false
    })
  }
  return items
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)))
const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})
const allRowIndexes = computed(() => {
  const validRows = excelAnalysis.value?.valid_rows || []
  return validRows.map((_, index) => index + 1)
})
const isPageAllSelected = computed(() => {
  if (pagedRows.value.length === 0) return false
  const pageIdxs = pagedRows.value.map(x => x.idx)
  return pageIdxs.every(id => selectedRows.value.includes(id))
})

const executionLogStats = computed(() => {
  return executionResults.value.reduce((stats, result) => {
    const status = result?.status || 'info'
    if (status === 'success') {
      stats.success += 1
    } else if (status === 'error') {
      stats.error += 1
    } else {
      stats.info += 1
    }
    return stats
  }, { info: 0, success: 0, error: 0 })
})

const imageDependencyStatus = computed(() => imageModelStatus.value?.dependencies || createEmptyImageModelStatus().dependencies)
const missingImageModelDependencies = computed(() => Array.isArray(imageDependencyStatus.value.missing) ? imageDependencyStatus.value.missing : [])
const activeImageModelName = computed(() => imageModelStatus.value?.active_model?.name || '')
const isOpenCvCompareBackend = computed(() => (imageModelStatus.value?.compare_backend || 'opencv') === 'opencv')
const hasAnalyzedCurrentFile = computed(() => Boolean(selectedFile.value && (validationResult.value || excelAnalysis.value)))
const currentCompareBackendLabel = computed(() => {
  if (activeImageModelName.value) {
    return t('excelExecution.compareBackendDinov2', { model: activeImageModelName.value })
  }
  return t('excelExecution.compareBackendOpenCv')
})
const shouldCollapseTopSelectors = computed(() => Boolean(
  selectedFile.value
  && (
    activeImageModelName.value
    || imageCompareBackendConfirmed.value
    || (hasAnalyzedCurrentFile.value && isOpenCvCompareBackend.value)
  )
))
const showCompactFileSelectorPanel = computed(() => shouldCollapseTopSelectors.value && !fileSelectorPanelExpanded.value)
const showCompactModelSelectorPanel = computed(() => shouldCollapseTopSelectors.value && !modelSelectorPanelExpanded.value)
const showCompactReportPanel = computed(() => !reportPanelExpanded.value)

const buildReportOverviewMeta = (summary) => {
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

const imageReportRows = computed(() => {
  return imageReports.value.map((item) => {
    const summary = {
      total: Number(item.summary?.total || 0),
      passed: Number(item.summary?.passed || 0),
      failed: Number(item.summary?.failed || 0),
      blocked: Number(item.summary?.blocked || 0)
    }
    const passRate = summary.total > 0
      ? `${((summary.passed / summary.total) * 100).toFixed(2)}%`
      : '0.00%'
    const overview = buildReportOverviewMeta(summary)

    return {
      ...item,
      summary,
      passRate,
      overviewText: overview.text,
      overviewTone: overview.tone
    }
  })
})

const latestImageReport = computed(() => imageReportRows.value[0] || null)
const showBatchExecutionProgress = computed(() => batchExecutionState.active || batchExecutionState.total > 0)
const batchExecutionPercent = computed(() => {
  if (batchExecutionState.total <= 0) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round((batchExecutionState.completed / batchExecutionState.total) * 100)))
})
const batchExecutionRemainingCount = computed(() => Math.max(0, batchExecutionState.total - batchExecutionState.completed))
const batchExecutionStatusLabel = computed(() => {
  if (batchExecutionState.active) {
    return t('excelExecution.batchProgressRunning')
  }
  if (batchExecutionState.status === 'completed') {
    return t('excelExecution.batchProgressCompletedStatus')
  }
  if (batchExecutionState.status === 'stopped') {
    return t('excelExecution.batchProgressStoppedStatus')
  }
  return ''
})

const resetBatchExecutionState = () => {
  batchExecutionState.active = false
  batchExecutionState.status = 'idle'
  batchExecutionState.label = ''
  batchExecutionState.total = 0
  batchExecutionState.completed = 0
  batchExecutionState.currentRowIndex = null
  batchExecutionState.currentCaseTitle = ''
}

const getBatchExecutionCaseTitle = (rowIndex) => {
  const rowData = excelAnalysis.value?.valid_rows?.[rowIndex - 1]
  return rowData?.title || t('excelExecution.rowFallbackTitle', { row: rowIndex })
}

const expandFileSelectorPanel = () => {
  fileSelectorPanelExpanded.value = true
}

const expandModelSelectorPanel = () => {
  modelSelectorPanelExpanded.value = true
}

const expandReportPanel = () => {
  reportPanelExpanded.value = true
}

const collapseReportPanel = () => {
  reportPanelExpanded.value = false
}

watch(selectedFile, (nextFile, previousFile) => {
  if (!nextFile) {
    fileSelectorPanelExpanded.value = false
    return
  }

  if (activeImageModelName.value && nextFile !== previousFile) {
    fileSelectorPanelExpanded.value = false
  }
})

watch(activeImageModelName, (nextModel, previousModel) => {
  if (!nextModel) {
    modelSelectorPanelExpanded.value = false
    return
  }

  imageCompareBackendConfirmed.value = true

  if (selectedFile.value && nextModel !== previousModel) {
    modelSelectorPanelExpanded.value = false
  }
})

// 加载当前设备
onMounted(async () => {
  await Promise.all([loadCurrentDevice(), loadExcelFiles(), loadImageModelStatus({ silent: true }), loadImageReports({ silent: true })])
  await restoreExecutionState()
  // 点击页面任意位置关闭结果弹窗
  document.addEventListener('click', closeResultPopover)
})

// 加载当前设备（仅读取，不做自动选择/恢复，避免调用 /api/devices/list 等有副作用的接口干扰首页设备列表）
const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device || ''
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
}

// 加载Excel文件列表
const loadExcelFiles = async () => {
  loadingFiles.value = true
  try {
    const response = await fetch('/api/excel/files')
    const data = await response.json()
    excelFiles.value = data.files
  } catch (error) {
    console.error('获取Excel文件列表失败:', error)
  } finally {
    loadingFiles.value = false
  }
}

const loadImageModelStatus = async (options = {}) => {
  const { silent = false } = options
  loadingImageModelStatus.value = true
  if (!silent) {
    imageModelStatusError.value = ''
  }

  try {
    const response = await fetch('/api/excel/image-models/status')
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelExecution.alerts.loadImageModelStatusFailed')))
    }

    const data = await response.json()
    imageModelStatus.value = {
      ...createEmptyImageModelStatus(),
      ...data,
      dependencies: {
        ...createEmptyImageModelStatus().dependencies,
        ...(data.dependencies || {})
      },
      recommended_model: {
        ...createEmptyImageModelStatus().recommended_model,
        ...(data.recommended_model || {})
      }
    }
    if (!silent) {
      imageModelMessage.value = ''
    }
  } catch (error) {
    imageModelStatusError.value = error instanceof Error ? error.message : t('excelExecution.alerts.loadImageModelStatusFailed')
  } finally {
    loadingImageModelStatus.value = false
  }
}

const downloadRecommendedImageModel = async () => {
  downloadingImageModel.value = true
  imageModelStatusError.value = ''
  imageModelMessage.value = ''

  try {
    const payload = {
      model_name: imageModelStatus.value?.recommended_model?.name || 'DINOv2-Base',
      repo_id: imageModelStatus.value?.recommended_model?.repo_id || 'facebook/dinov2-base'
    }
    const response = await fetch('/api/excel/image-models/download', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelExecution.alerts.downloadImageModelFailed')))
    }

    const data = await response.json()
    imageModelMessage.value = t('excelExecution.alerts.downloadImageModelSuccess', { model: data.model_name || payload.model_name })
    await loadImageModelStatus({ silent: true })
  } catch (error) {
    imageModelStatusError.value = error instanceof Error ? error.message : t('excelExecution.alerts.downloadImageModelFailed')
  } finally {
    downloadingImageModel.value = false
  }
}

const selectImageModel = async (modelName) => {
  selectingImageModel.value = true
  imageModelStatusError.value = ''
  imageModelMessage.value = ''

  try {
    const response = await fetch('/api/excel/image-models/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ model_name: modelName })
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelExecution.alerts.selectImageModelFailed')))
    }

    await loadImageModelStatus({ silent: true })
    imageCompareBackendConfirmed.value = true
    imageModelMessage.value = t('excelExecution.alerts.selectImageModelSuccess', { model: modelName })
  } catch (error) {
    imageModelStatusError.value = error instanceof Error ? error.message : t('excelExecution.alerts.selectImageModelFailed')
  } finally {
    selectingImageModel.value = false
  }
}

const clearSelectedImageModel = async () => {
  clearingImageModelSelection.value = true
  imageModelStatusError.value = ''
  imageModelMessage.value = ''

  try {
    const response = await fetch('/api/excel/image-models/clear-selection', {
      method: 'POST'
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelExecution.alerts.clearImageModelFailed')))
    }

    await loadImageModelStatus({ silent: true })
    imageCompareBackendConfirmed.value = true
    imageModelMessage.value = t('excelExecution.alerts.switchToOpenCvSuccess')
  } catch (error) {
    imageModelStatusError.value = error instanceof Error ? error.message : t('excelExecution.alerts.clearImageModelFailed')
  } finally {
    clearingImageModelSelection.value = false
  }
}

const deleteImageModel = async (modelName) => {
  if (!confirm(t('excelExecution.alerts.deleteImageModelConfirm', { model: modelName }))) {
    return
  }

  deletingImageModel.value = true
  imageModelStatusError.value = ''
  imageModelMessage.value = ''

  try {
    const response = await fetch(`/api/excel/image-models?model_name=${encodeURIComponent(modelName)}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelExecution.alerts.deleteImageModelFailed')))
    }

    await loadImageModelStatus({ silent: true })
    imageModelMessage.value = t('excelExecution.alerts.deleteImageModelSuccess', { model: modelName })
  } catch (error) {
    imageModelStatusError.value = error instanceof Error ? error.message : t('excelExecution.alerts.deleteImageModelFailed')
  } finally {
    deletingImageModel.value = false
  }
}

const readErrorMessage = async (response, fallbackMessage) => {
  try {
    const data = await response.json()
    return data.detail || data.message || fallbackMessage
  } catch {
    return fallbackMessage
  }
}

const formatReportDate = (value) => {
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

const openReport = (url) => {
  if (!url) {
    return
  }

  window.open(url, '_blank', 'noopener')
}

const loadImageReports = async (options = {}) => {
  const { silent = false } = options
  loadingImageReports.value = true
  imageReportsError.value = ''

  try {
    const response = await fetch('/api/reports')
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('reports.alerts.loadReportsFailed')))
    }

    const data = await response.json()
    const reports = Array.isArray(data.reports) ? data.reports : []
    imageReports.value = reports.filter((item) => item?.kind === 'excel-batch')
  } catch (error) {
    imageReportsError.value = error instanceof Error ? error.message : t('reports.alerts.loadReportsFailed')
    if (!silent) {
      console.error('加载图片校验报告失败:', error)
    }
  } finally {
    loadingImageReports.value = false
  }
}

const formatBatchScore = (score) => {
  if (!Number.isFinite(score)) {
    return ''
  }
  return `${(score * 100).toFixed(2)}%`
}

const buildExcelBatchResultDetail = (message, score, compareEngine = '', modelName = '') => {
  const normalizedMessage = String(message || '').trim()
  const scoreText = formatBatchScore(Number(score))
  const engineText = compareEngine === 'dinov2'
    ? (modelName ? `DINOv2 ${modelName}` : 'DINOv2')
    : ''
  if (normalizedMessage && scoreText && !normalizedMessage.includes(scoreText)) {
    return engineText
      ? `${normalizedMessage}（相似度 ${scoreText}） · ${engineText}`
      : `${normalizedMessage}（相似度 ${scoreText}）`
  }
  if (normalizedMessage) {
    return engineText ? `${normalizedMessage} · ${engineText}` : normalizedMessage
  }
  if (scoreText) {
    return engineText ? `相似度 ${scoreText} · ${engineText}` : `相似度 ${scoreText}`
  }
  return engineText
}

const normalizeCompareDetails = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }

  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== null && item !== '')
  )
}

const buildRowExecutionLogEntry = (rowIndex, result) => {
  return {
    row_index: rowIndex,
    happened_at: new Date().toISOString(),
    status: result?.status || 'info',
    message: result?.message || ''
  }
}

const getBatchReportTitle = () => {
  const baseName = selectedFile.value ? selectedFile.value.replace(/\.[^.]+$/, '') : 'Excel'
  return `${baseName}报告`
}

const buildExcelBatchReportRows = async (rowIndexes) => {
  const validRows = excelAnalysis.value?.valid_rows || []
  return Promise.all(rowIndexes.map(async (rowIndex) => {
    const row = validRows[rowIndex - 1] || {}
    const meta = rowResultMeta.value[rowIndex] || {}
    const status = meta.verify_result || (meta.status === 'error' ? 'ERROR' : 'UNKNOWN')
    const detail = meta.detail || meta.last_message || (
      status.toUpperCase() === 'PASS' ? '验证通过' :
      ['FAIL', 'ERROR'].includes(status.toUpperCase()) ? '验证失败' :
      status.toUpperCase() === 'NT' ? '未测试' :
      status.toUpperCase() === 'NA' ? '不适用' :
      '未返回结果详情'
    )
    const matchedEntry = row.verify_image ? getLocalVerifyImageEntry(row.verify_image) : null
    let verifyImageDataUrl = ''

    if (matchedEntry?.file) {
      try {
        verifyImageDataUrl = await readFileAsDataUrl(matchedEntry.file)
      } catch (error) {
        console.error('读取报告原图片快照失败:', error)
      }
    }

    // 收集该行的所有执行轮次
    const allRuns = rowAllResults.value[rowIndex] || []
    const runs = allRuns.length > 0 ? allRuns.map((r, i) => ({
      run_index: i + 1,
      status: r.status || '',
      score: Number.isFinite(r.score) ? r.score : null,
      detail: r.detail || '',
      screenshot_url: r.screenshot_url || '',
      video_url: r.video_url || '',
      compare_engine: r.compare_engine || '',
      model_name: r.model_name || '',
      compare_details: normalizeCompareDetails(r.compare_details),
      execution_logs: r.execution_logs || [],
    })) : [{
      run_index: 1,
      status,
      score: Number.isFinite(meta.score) ? meta.score : null,
      detail,
      screenshot_url: meta.screenshot_url || rowScreenshots.value[rowIndex] || '',
      video_url: meta.video_url || '',
      compare_engine: meta.compare_engine || '',
      model_name: meta.model_name || '',
      compare_details: normalizeCompareDetails(meta.compare_details),
      execution_logs: [],
    }]

    return {
      row_index: rowIndex,
      case_title: row.title || t('excelExecution.rowFallbackTitle', { row: rowIndex }),
      verify_result: status,
      score: Number.isFinite(meta.score) ? meta.score : null,
      detail,
      verify_image: row.verify_image || '',
      verify_image_data_url: verifyImageDataUrl,
      screenshot_url: meta.screenshot_url || rowScreenshots.value[rowIndex] || '',
      video_url: meta.video_url || '',
      compare_engine: meta.compare_engine || '',
      model_name: meta.model_name || '',
      compare_details: normalizeCompareDetails(meta.compare_details),
      runs,
    }
  }))
}

const createExcelBatchReport = async (rowIndexes, label) => {
  const rowResults = await buildExcelBatchReportRows(rowIndexes)
  if (rowResults.length === 0) {
    return null
  }

  try {
    const response = await fetch('/api/reports/excel-batch', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: getBatchReportTitle(),
        file_name: selectedFile.value || '',
        label,
        device: selectedDevice.value || '',
        row_results: rowResults,
        execution_logs: executionResults.value.map((item) => ({
          status: item.status,
          message: item.message,
          row_index: Number.isInteger(item.row_index) ? item.row_index : null,
          happened_at: item.happened_at || ''
        }))
      })
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelExecution.alerts.reportGenerateFailed')))
    }

    const data = await response.json()
    if (data.report?.title) {
      executionResults.value.push({
        status: 'success',
        message: t('excelExecution.alerts.reportGenerated', { title: data.report.title })
      })
    }
    await loadImageReports({ silent: true })
    return data.report || null
  } catch (error) {
    executionResults.value.push({
      status: 'error',
      message: error instanceof Error ? error.message : t('excelExecution.alerts.reportGenerateFailed')
    })
    return null
  }
}

// 选择文件
const selectFile = (file) => {
  selectedFile.value = file
  if (!activeImageModelName.value) {
    imageCompareBackendConfirmed.value = false
  }
  resetBatchExecutionState()
  excelAnalysis.value = null
  validationResult.value = null
  rowExecutionProgress.value = {}
  showValidationResultModal.value = false
  executionResults.value = []
  rowScreenshots.value = {}
  rowResultMeta.value = {}
  selectedRows.value = []
  currentPage.value = 1
  jumpPage.value = 1
  rowIndex.value = 1
}

const editKeyMonitorWorkingSequence = computed(() => {
  return (editKeyMonitorActive.value || editKeyMonitorStarting.value)
    ? editKeyMonitorSequence.value
    : editKeyMonitorEditableSequence.value
})

const openValidationResultModal = () => {
  if (validationResult.value) {
    showValidationResultModal.value = true
  }
}

const closeValidationResultModal = () => {
  showValidationResultModal.value = false
}

const canApplyEditKeyMonitorSequence = computed(() => {
  return normalizeEditKeyMonitorSequence(editKeyMonitorWorkingSequence.value).length > 0
})

const setEditKeyMonitorTargetField = (field) => {
  if (field === 'ori_step' || field === 'pre_script') {
    editKeyMonitorTargetField.value = field
  }
}

const normalizeEditKeyMonitorSequence = (sequence) => {
  return String(sequence || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .join(',')
}

const compressAdjacentEditCommands = (sequence) => {
  // 把 KEY/N/D,KEY/M/D 合并为 KEY/(N+M)/D。带 "*" 占位延迟或非数字 count 的
  // 段不做合并，避免破坏监听过程中的占位行。
  const parts = String(sequence || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  const out = []
  for (const part of parts) {
    const segs = part.split('/')
    if (segs.length < 3) {
      out.push(part)
      continue
    }
    const key = segs[0]
    const count = parseInt(segs[1], 10)
    const delay = segs[2]
    if (delay === '*' || Number.isNaN(count)) {
      out.push(part)
      continue
    }
    const last = out.length > 0 ? out[out.length - 1] : null
    if (last) {
      const lastSegs = last.split('/')
      if (lastSegs.length >= 3 && lastSegs[0] === key && lastSegs[2] === delay) {
        const lastCount = parseInt(lastSegs[1], 10) || 1
        out[out.length - 1] = `${key}/${lastCount + (count || 1)}/${delay}`
        continue
      }
    }
    out.push(`${key}/${count || 1}/${delay}`)
  }
  return out.join(',')
}

const applyEditKeyMonitorMappingsToSequence = (sequence, mappings = editKeyMonitorMappings.value) => {
  const normalized = normalizeEditKeyMonitorSequence(sequence)
  if (!normalized || !mappings || typeof mappings !== 'object') {
    return normalized
  }

  return normalized
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((part) => {
      const segments = part.split('/')
      if (segments.length < 3) {
        return part
      }

      const sourceKey = (segments[0] || '').trim().toUpperCase()
      const mappedKey = mappings[sourceKey]
      if (typeof mappedKey !== 'string' || !mappedKey.trim()) {
        return part
      }

      return `${mappedKey.trim().toUpperCase()}/${segments[1]}/${segments[2]}`
    })
    .join(',')
}

const syncEditKeyMonitorSequence = (sequence, mappings = editKeyMonitorMappings.value) => {
  const normalized = applyEditKeyMonitorMappingsToSequence(sequence, mappings)
  editKeyMonitorSequence.value = normalized
  editKeyMonitorEditableSequence.value = normalized
  editKeyMonitorSequenceDirty.value = false
}

const stopEditKeyMonitorStatusPolling = () => {
  if (editKeyMonitorStatusTimer) {
    clearInterval(editKeyMonitorStatusTimer)
    editKeyMonitorStatusTimer = null
  }
  editKeyMonitorStatusRequestActive = false
}

const startEditKeyMonitorStatusPolling = () => {
  if (editKeyMonitorStatusTimer) {
    return
  }

  editKeyMonitorStatusTimer = setInterval(async () => {
    if (editKeyMonitorStatusRequestActive) {
      return
    }

    editKeyMonitorStatusRequestActive = true
    try {
      const res = await fetch('/api/keymonitor/status')
      if (!res.ok) {
        return
      }

      const data = await res.json()
      editKeyMonitorActive.value = !!data.active
      if (data.active) {
        editKeyMonitorStarting.value = false
        syncEditKeyMonitorSequence(data.live_sequence || '')
      } else {
        editKeyMonitorSequence.value = applyEditKeyMonitorMappingsToSequence(data.latest_sequence || '')
        if (!editKeyMonitorStarting.value && !editKeyMonitorSequenceDirty.value) {
          editKeyMonitorEditableSequence.value = applyEditKeyMonitorMappingsToSequence(data.latest_sequence || '')
        }
      }

      editKeyMonitorError.value = data.last_error || editKeyMonitorError.value
    } catch {
    } finally {
      editKeyMonitorStatusRequestActive = false
    }
  }, 800)
}

const loadEditKeyMonitorMappings = async () => {
  try {
    const res = await fetch('/api/keymonitor/mappings')
    if (!res.ok) {
      throw new Error(t('excelExecution.alerts.loadEditMonitorFailed'))
    }

    const data = await res.json()
    editKeyMonitorMappings.value = data.mappings || {}
    if (typeof data.active_scheme === 'string') {
      activeMappingSchemeName.value = data.active_scheme
    }
    if (Array.isArray(data.schemes)) {
      mappingSchemesList.value = data.schemes
    }
    editKeyMonitorSequence.value = applyEditKeyMonitorMappingsToSequence(editKeyMonitorSequence.value, editKeyMonitorMappings.value)
    editKeyMonitorEditableSequence.value = applyEditKeyMonitorMappingsToSequence(editKeyMonitorEditableSequence.value, editKeyMonitorMappings.value)
    editKeyMonitorSequenceDirty.value = editKeyMonitorEditableSequence.value !== editKeyMonitorSequence.value
  } catch (error) {
    editKeyMonitorMappings.value = {}
    editKeyMonitorError.value = error.message || t('excelExecution.alerts.loadEditMonitorFailed')
  }
}

const onEditMappingSchemeChange = async (event) => {
  const targetName = String(event?.target?.value || '').trim()
  if (!targetName || targetName === activeMappingSchemeName.value) {
    return
  }
  editMappingSchemeBusy.value = true
  editMappingSchemeError.value = ''
  try {
    const res = await fetch(`/api/keymonitor/mapping-schemes/${encodeURIComponent(targetName)}/activate`, {
      method: 'PUT'
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(data?.detail || t('excelExecution.alerts.switchMappingSchemeFailed'))
    }
    if (typeof data.active_scheme === 'string') {
      activeMappingSchemeName.value = data.active_scheme
    }
    if (Array.isArray(data.schemes)) {
      mappingSchemesList.value = data.schemes
    }
    editKeyMonitorMappings.value = data.mappings || {}
    editKeyMonitorSequence.value = applyEditKeyMonitorMappingsToSequence(editKeyMonitorSequence.value, editKeyMonitorMappings.value)
    editKeyMonitorEditableSequence.value = applyEditKeyMonitorMappingsToSequence(editKeyMonitorEditableSequence.value, editKeyMonitorMappings.value)
    editKeyMonitorSequenceDirty.value = editKeyMonitorEditableSequence.value !== editKeyMonitorSequence.value
  } catch (error) {
    editMappingSchemeError.value = error.message || t('excelExecution.alerts.switchMappingSchemeFailed')
    // 切换失败时，让下拉回到原激活方案，避免显示与后端不一致
    if (event?.target) {
      event.target.value = activeMappingSchemeName.value
    }
  } finally {
    editMappingSchemeBusy.value = false
  }
}

const startEditKeyMonitor = async () => {
  startEditKeyMonitorStatusPolling()
  syncEditKeyMonitorSequence('')
  editKeyMonitorError.value = ''
  editKeyMonitorStarting.value = true

  try {
    const res = await fetch('/api/keymonitor/start', { method: 'POST' })
    if (res.ok) {
      editKeyMonitorActive.value = true
      return
    }

    const data = await res.json().catch(() => ({}))
    editKeyMonitorError.value = data?.detail || t('excelExecution.alerts.startEditMonitorFailed')
    editKeyMonitorStarting.value = false
  } catch {
    editKeyMonitorError.value = t('excelExecution.alerts.startEditMonitorFailed')
    editKeyMonitorStarting.value = false
  }
}

const stopEditKeyMonitor = async () => {
  try {
    const res = await fetch('/api/keymonitor/stop', { method: 'POST' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail || t('excelExecution.alerts.stopEditMonitorFailed'))
    }

    const data = await res.json()
    editKeyMonitorActive.value = false
    editKeyMonitorStarting.value = false
    syncEditKeyMonitorSequence(data.sequence || '')
  } catch (error) {
    editKeyMonitorError.value = error.message || t('excelExecution.alerts.stopEditMonitorFailed')
  }
}

const finalizeEditKeyMonitorSequence = async () => {
  if (!editKeyMonitorActive.value && !editKeyMonitorStarting.value) {
    return normalizeEditKeyMonitorSequence(editKeyMonitorWorkingSequence.value)
  }

  const res = await fetch('/api/keymonitor/stop', { method: 'POST' })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || t('excelExecution.alerts.stopEditMonitorFailed'))
  }

  editKeyMonitorActive.value = false
  editKeyMonitorStarting.value = false
  const finalizedSequence = applyEditKeyMonitorMappingsToSequence(data.sequence || '')
  syncEditKeyMonitorSequence(finalizedSequence)
  return normalizeEditKeyMonitorSequence(finalizedSequence)
}

const applyEditKeyMonitorSequenceToField = async () => {
  try {
    const sequence = await finalizeEditKeyMonitorSequence()
    if (!sequence) {
      return
    }

    const targetField = editKeyMonitorTargetField.value === 'ori_step' ? 'ori_step' : 'pre_script'
    const currentValue = normalizeEditKeyMonitorSequence(editingCaseForm[targetField]).replace(/,+$/, '')
    const merged = currentValue ? `${currentValue},${sequence}` : sequence
    editingCaseForm[targetField] = compressAdjacentEditCommands(merged)
  } catch (error) {
    editKeyMonitorError.value = error.message || t('excelExecution.alerts.applyEditMonitorFailed')
  }
}

const handleEditKeyMonitorSequenceInput = (event) => {
  if (editKeyMonitorActive.value || editKeyMonitorStarting.value) {
    return
  }

  editKeyMonitorEditableSequence.value = event?.target?.value || ''
  editKeyMonitorSequenceDirty.value = true
}

const restoreEditKeyMonitorSequence = () => {
  editKeyMonitorEditableSequence.value = editKeyMonitorSequence.value
  editKeyMonitorSequenceDirty.value = false
}

const clearEditKeyMonitorContent = async () => {
  try {
    if (editKeyMonitorActive.value || editKeyMonitorStarting.value) {
      await fetch('/api/keymonitor/stop', { method: 'POST' })
    }
    await fetch('/api/keymonitor/clear', { method: 'POST' })
  } catch {}

  editKeyMonitorActive.value = false
  editKeyMonitorStarting.value = false
  syncEditKeyMonitorSequence('')
  editKeyMonitorError.value = ''
}

const resetEditKeyMonitorState = () => {
  stopEditKeyMonitorStatusPolling()
  editKeyMonitorActive.value = false
  editKeyMonitorStarting.value = false
  editKeyMonitorSequence.value = ''
  editKeyMonitorEditableSequence.value = ''
  editKeyMonitorSequenceDirty.value = false
  editKeyMonitorTargetField.value = 'pre_script'
  editKeyMonitorMappings.value = {}
  editKeyMonitorError.value = ''
  editMappingSchemeError.value = ''
}

// ───────────────────── 编辑模态：设备画面预览 + 框选保存 ─────────────────────

const editDevicePreviewUsesCaptureCard = computed(() => editDevicePreviewSource.value === EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD)
const editDevicePreviewIdentityLabel = computed(() => {
  if (editDevicePreviewLabel.value) {
    return editDevicePreviewLabel.value
  }
  if (editDevicePreviewUsesCaptureCard.value) {
    return t('excelExecution.devicePreviewCaptureCardLabel')
  }
  return selectedDevice.value || ''
})
const editDevicePreviewCapturedLabel = computed(() => {
  if (!editDevicePreviewCapturedAt.value) {
    return ''
  }
  return new Date(editDevicePreviewCapturedAt.value).toLocaleString()
})
const editDevicePreviewSelectionStyle = computed(() => {
  if (!editDevicePreviewSelectionRect.value) {
    return null
  }
  return {
    left: `${editDevicePreviewSelectionRect.value.x}px`,
    top: `${editDevicePreviewSelectionRect.value.y}px`,
    width: `${editDevicePreviewSelectionRect.value.width}px`,
    height: `${editDevicePreviewSelectionRect.value.height}px`,
  }
})

const editDevicePreviewTargetFileName = computed(() => {
  const raw = String(editingCaseForm.verify_image || '').trim()
  if (!raw) {
    return ''
  }
  // 用 verify_image 字段的 basename 作为强制文件名（带扩展名）
  const cleaned = raw.replace(/[\\/]+$/, '')
  const segments = cleaned.split(/[\\/]/)
  const basename = segments[segments.length - 1] || ''
  return basename.trim()
})

const buildEditDevicePreviewQuery = () => {
  const params = new URLSearchParams()
  params.set('source', editDevicePreviewSource.value)
  params.set('ts', String(Date.now()))
  return params.toString()
}

const buildEditDevicePreviewStreamUrl = () => {
  // 采集卡走 MJPEG 实时流：src 一次设置就持续推帧、不会重新加载，避免框选时
  // 因为 <img> 重新解码导致 metrics 短暂归零、selection rect 被瞬间擦掉。
  const params = new URLSearchParams()
  params.set('source', EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD)
  // 加一个版本号让用户主动 refresh 时能强制换 src
  params.set('stream', String(editDevicePreviewStreamVersion.value))
  return `/api/devices/preview/stream?${params.toString()}`
}

const stopEditDevicePreviewTimer = () => {
  if (editDevicePreviewTimer) {
    clearInterval(editDevicePreviewTimer)
    editDevicePreviewTimer = null
  }
}

const startEditDevicePreviewTimer = () => {
  stopEditDevicePreviewTimer()
  // 采集卡走 MJPEG 流，不需要轮询；ADB 才靠定时器拉单帧。
  if (editDevicePreviewSource.value === EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD) {
    return
  }
  editDevicePreviewTimer = setInterval(() => {
    if (editDevicePreviewRequestActive) {
      return
    }
    if (editDevicePreviewSelectionActive.value || editDevicePreviewSelectionCrop.value) {
      // 用户在框选时不刷新，避免画面变动
      return
    }
    void loadEditDevicePreview({ silent: true })
  }, EDIT_DEVICE_PREVIEW_REFRESH_INTERVAL)
}

const loadEditDevicePreview = async ({ silent = false } = {}) => {
  if (editDevicePreviewRequestActive) {
    return
  }
  if (editDevicePreviewSource.value === EDIT_DEVICE_PREVIEW_SOURCE_ADB && !selectedDevice.value) {
    editDevicePreviewError.value = t('excelExecution.alerts.devicePreviewRequiresDevice')
    editDevicePreviewUrl.value = ''
    editDevicePreviewLoading.value = false
    return
  }
  // 采集卡：直接挂上 MJPEG 流；浏览器拿到 multipart/x-mixed-replace 后会持续替换内容，
  // <img> 元素的 src 在这之后再不会变，所以 framing/选区不会再被中途擦掉。
  if (editDevicePreviewSource.value === EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD) {
    editDevicePreviewLabel.value = t('excelExecution.devicePreviewCaptureCardLabel')
    if (!editDevicePreviewUrl.value || !editDevicePreviewUrl.value.startsWith('/api/devices/preview/stream')) {
      editDevicePreviewUrl.value = buildEditDevicePreviewStreamUrl()
    }
    editDevicePreviewError.value = ''
    return
  }

  // 框选进行中或已经画好了选区时，绝不刷新画面 src，避免 <img> 重渲染导致选框消失。
  // setInterval 里已有第一道防线，这里是兜底——保护刚 pointerdown 那一瞬间已经在路上的 fetch。
  if (editDevicePreviewSelectionActive.value || editDevicePreviewSelectionCrop.value) {
    return
  }

  editDevicePreviewRequestActive = true
  if (!silent) {
    editDevicePreviewLoading.value = true
  }
  editDevicePreviewError.value = ''

  try {
    const response = await fetch(`/api/devices/preview?${buildEditDevicePreviewQuery()}`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || t('excelExecution.alerts.loadDevicePreviewFailed'))
    }

    // 二次防御：等 fetch 拿到结果时用户已经开始框选/已有选区，就把这一帧丢掉
    if (editDevicePreviewSelectionActive.value || editDevicePreviewSelectionCrop.value) {
      return
    }

    editDevicePreviewLabel.value = data.preview_label || ''
    editDevicePreviewCapturedAt.value = Number(data.captured_at) || Date.now()
    editDevicePreviewUrl.value = data.screenshot_url || ''
  } catch (error) {
    editDevicePreviewError.value = error.message || t('excelExecution.alerts.loadDevicePreviewFailed')
    if (!editDevicePreviewUrl.value) {
      editDevicePreviewLoading.value = false
    }
  } finally {
    editDevicePreviewRequestActive = false
  }
}

const handleEditDevicePreviewRefresh = () => {
  resetEditDevicePreviewSelection()
  editDevicePreviewSaveMessage.value = ''
  if (editDevicePreviewSource.value === EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD) {
    // 采集卡：换一个 stream 版本号让 <img> 重连流
    editDevicePreviewStreamVersion.value += 1
    editDevicePreviewUrl.value = buildEditDevicePreviewStreamUrl()
    return
  }
  void loadEditDevicePreview()
}

const handleEditDevicePreviewImageLoad = () => {
  editDevicePreviewLoading.value = false
}

const handleEditDevicePreviewImageError = () => {
  editDevicePreviewLoading.value = false
  editDevicePreviewError.value = t('excelExecution.alerts.loadDevicePreviewFailed')
}

const resetEditDevicePreviewSelection = () => {
  editDevicePreviewSelectionActive.value = false
  editDevicePreviewSelectionRect.value = null
  editDevicePreviewSelectionCrop.value = null
  editDevicePreviewSelectionPointerId = null
  editDevicePreviewSelectionStartPoint = null
}

const clearEditDevicePreviewSelection = () => {
  resetEditDevicePreviewSelection()
  editDevicePreviewSaveMessage.value = ''
  editDevicePreviewError.value = ''
}

const computeEditDevicePreviewMetrics = () => {
  const image = editDevicePreviewImageRef.value
  const frame = editDevicePreviewFrameRef.value
  if (!image || !frame) {
    return null
  }
  const frameRect = frame.getBoundingClientRect()
  const imageRect = image.getBoundingClientRect()
  const naturalWidth = image.naturalWidth || image.width || 0
  const naturalHeight = image.naturalHeight || image.height || 0
  const displayWidth = imageRect.width || naturalWidth
  const displayHeight = imageRect.height || naturalHeight

  // 图片在 frame 里通常是 object-fit: contain + flex 居中，所以左右/上下可能有留白。
  // 选区 rect 用的是相对 frame 的坐标（CSS 渲染需要），但 natural 像素裁切必须扣掉
  // 这一段居中偏移，否则截图会和框选位置错开。
  const offsetX = imageRect.left - frameRect.left
  const offsetY = imageRect.top - frameRect.top

  return {
    frameRect,
    imageRect,
    naturalWidth,
    naturalHeight,
    displayWidth,
    displayHeight,
    offsetX,
    offsetY,
  }
}

const beginEditDevicePreviewSelection = (event) => {
  if (!editDevicePreviewUrl.value) return
  if (event.button !== 0) return
  const metrics = computeEditDevicePreviewMetrics()
  if (!metrics) return

  const pointX = event.clientX - metrics.frameRect.left
  const pointY = event.clientY - metrics.frameRect.top
  // 在留白处点击直接忽略，避免起点漂到图片外
  if (
    pointX < metrics.offsetX ||
    pointX > metrics.offsetX + metrics.displayWidth ||
    pointY < metrics.offsetY ||
    pointY > metrics.offsetY + metrics.displayHeight
  ) {
    return
  }

  event.preventDefault()
  // 必须用 currentTarget（绑定 @pointerdown 的 frame）而不是 target（命中的 <img>）。
  // 把 pointerCapture 转移到 <img> 会让后续 pointermove/pointerup 全部派发给 <img>
  // 而非 frame，frame 上的事件 handler 收不到，selection rect 立刻被 pointercancel 擦掉。
  try {
    event.currentTarget?.setPointerCapture?.(event.pointerId)
  } catch {}
  editDevicePreviewSelectionPointerId = event.pointerId
  editDevicePreviewSelectionStartPoint = { x: pointX, y: pointY }
  editDevicePreviewSelectionActive.value = true
  editDevicePreviewSelectionRect.value = {
    x: pointX,
    y: pointY,
    width: 0,
    height: 0,
  }
  editDevicePreviewSelectionCrop.value = null
}

const updateEditDevicePreviewSelectionGeometry = (startPoint, endPoint, metrics) => {
  // 把选区限制在图片实际显示范围内，避免拖到留白区导致裁切坐标越界
  const minX = metrics.offsetX
  const maxX = metrics.offsetX + metrics.displayWidth
  const minY = metrics.offsetY
  const maxY = metrics.offsetY + metrics.displayHeight
  const clampedEnd = {
    x: Math.min(maxX, Math.max(minX, endPoint.x)),
    y: Math.min(maxY, Math.max(minY, endPoint.y)),
  }

  const x = Math.min(startPoint.x, clampedEnd.x)
  const y = Math.min(startPoint.y, clampedEnd.y)
  const width = Math.abs(clampedEnd.x - startPoint.x)
  const height = Math.abs(clampedEnd.y - startPoint.y)
  editDevicePreviewSelectionRect.value = { x, y, width, height }

  const { naturalWidth, naturalHeight, displayWidth, displayHeight, offsetX, offsetY } = metrics
  if (!naturalWidth || !naturalHeight || !displayWidth || !displayHeight) {
    editDevicePreviewSelectionCrop.value = null
    return
  }
  // 把 frame 内坐标先减去图片居中偏移，再按 natural / display 比例换算到原始像素
  const scaleX = naturalWidth / displayWidth
  const scaleY = naturalHeight / displayHeight
  const cropX = Math.max(0, Math.round((x - offsetX) * scaleX))
  const cropY = Math.max(0, Math.round((y - offsetY) * scaleY))
  const cropWidth = Math.min(
    naturalWidth - cropX,
    Math.max(0, Math.round(width * scaleX))
  )
  const cropHeight = Math.min(
    naturalHeight - cropY,
    Math.max(0, Math.round(height * scaleY))
  )
  if (cropWidth < 4 || cropHeight < 4) {
    editDevicePreviewSelectionCrop.value = null
    return
  }
  editDevicePreviewSelectionCrop.value = {
    x: cropX,
    y: cropY,
    width: cropWidth,
    height: cropHeight,
  }
}

const updateEditDevicePreviewSelection = (event) => {
  if (!editDevicePreviewSelectionActive.value || editDevicePreviewSelectionPointerId !== event.pointerId || !editDevicePreviewSelectionStartPoint) {
    return
  }
  const metrics = computeEditDevicePreviewMetrics()
  if (!metrics) return
  const endPoint = {
    x: event.clientX - metrics.frameRect.left,
    y: event.clientY - metrics.frameRect.top,
  }
  updateEditDevicePreviewSelectionGeometry(editDevicePreviewSelectionStartPoint, endPoint, metrics)
}

const finishEditDevicePreviewSelection = (event) => {
  if (!editDevicePreviewSelectionActive.value || editDevicePreviewSelectionPointerId !== event.pointerId) {
    return
  }
  editDevicePreviewSelectionActive.value = false
  try {
    event.currentTarget?.releasePointerCapture?.(event.pointerId)
  } catch {}
  editDevicePreviewSelectionPointerId = null
  editDevicePreviewSelectionStartPoint = null
  if (!editDevicePreviewSelectionCrop.value) {
    editDevicePreviewSelectionRect.value = null
  }
}

const saveEditDevicePreviewSelection = async () => {
  if (!editDevicePreviewSelectionCrop.value || editDevicePreviewSaving.value) {
    return
  }
  const targetFileName = editDevicePreviewTargetFileName.value
  if (!targetFileName) {
    editDevicePreviewError.value = t('excelExecution.alerts.devicePreviewMissingTargetName')
    return
  }
  const image = editDevicePreviewImageRef.value
  if (!image || !image.complete) {
    editDevicePreviewError.value = t('excelExecution.alerts.saveDevicePreviewSelectionFailed')
    return
  }

  editDevicePreviewSaving.value = true
  editDevicePreviewSaveMessage.value = ''
  editDevicePreviewError.value = ''

  try {
    const crop = editDevicePreviewSelectionCrop.value
    const canvas = document.createElement('canvas')
    canvas.width = crop.width
    canvas.height = crop.height
    const context = canvas.getContext('2d')
    if (!context) {
      throw new Error(t('excelExecution.alerts.saveDevicePreviewSelectionFailed'))
    }
    context.drawImage(image, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height)
    const dataUrl = canvas.toDataURL('image/png')
    const imageBase64 = dataUrl.split(',')[1]
    if (!imageBase64) {
      throw new Error(t('excelExecution.alerts.saveDevicePreviewSelectionFailed'))
    }

    const response = await fetch('/api/devices/preview/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image_base64: imageBase64,
        file_name: targetFileName,
        save_dir: editDevicePreviewSaveDir.value.trim() || undefined,
        overwrite: true,
      })
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || t('excelExecution.alerts.saveDevicePreviewSelectionFailed'))
    }

    editDevicePreviewSaveMessage.value = t('excelExecution.devicePreviewSelectionSaved', {
      path: data.saved_path || data.file_name || targetFileName,
    })
    resetEditDevicePreviewSelection()
  } catch (error) {
    editDevicePreviewError.value = error.message || t('excelExecution.alerts.saveDevicePreviewSelectionFailed')
  } finally {
    editDevicePreviewSaving.value = false
  }
}

const startEditDevicePreview = () => {
  resetEditDevicePreviewSelection()
  editDevicePreviewSaveMessage.value = ''
  editDevicePreviewError.value = ''
  void loadEditDevicePreview()
  startEditDevicePreviewTimer()
  if (editDevicePreviewSource.value === EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD) {
    void ensureEditCaptureCardDevicesLoaded()
  }
}

const stopEditDevicePreview = () => {
  stopEditDevicePreviewTimer()
  editDevicePreviewUrl.value = ''
  editDevicePreviewLoading.value = false
  editDevicePreviewError.value = ''
  editDevicePreviewLabel.value = ''
  editDevicePreviewCapturedAt.value = 0
  editDevicePreviewSaveMessage.value = ''
  resetEditDevicePreviewSelection()
}

watch(editDevicePreviewSource, (next, prev) => {
  if (!showCaseEditModal.value) return
  if (next === prev) return
  resetEditDevicePreviewSelection()
  editDevicePreviewSaveMessage.value = ''
  editDevicePreviewUrl.value = ''
  stopEditDevicePreviewTimer()
  void loadEditDevicePreview()
  startEditDevicePreviewTimer()
  // 切到采集卡时如果还没拉过设备列表，立刻拉一次，避免下拉里"没设备让用户选择"
  if (next === EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD) {
    void ensureEditCaptureCardDevicesLoaded()
  }
})

// ───────────────────── 编辑模态：采集卡设备选择 ─────────────────────

const ensureEditCaptureCardDevicesLoaded = async () => {
  if (editCaptureCardListLoaded || editCaptureCardListLoading.value) {
    return
  }
  await loadEditCaptureCardDevices()
}

const loadEditCaptureCardDevices = async () => {
  editCaptureCardListLoading.value = true
  editCaptureCardError.value = ''
  try {
    const response = await fetch('/api/devices/capture-card/devices')
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || t('excelExecution.alerts.loadCaptureCardDevicesFailed'))
    }
    editCaptureCardDevicesList.value = Array.isArray(data.devices) ? data.devices : []
    if (data.active_device && Number.isInteger(data.active_device.device_id)) {
      editCaptureCardActiveDeviceId.value = data.active_device.device_id
    }
    editCaptureCardListLoaded = true
  } catch (error) {
    editCaptureCardError.value = error?.message || t('excelExecution.alerts.loadCaptureCardDevicesFailed')
  } finally {
    editCaptureCardListLoading.value = false
  }
}

const onEditCaptureCardDeviceSelectChange = async (event) => {
  const next = Number(event?.target?.value)
  if (!Number.isFinite(next) || next === editCaptureCardActiveDeviceId.value) {
    return
  }
  await switchEditCaptureCardDevice(next)
}

const switchEditCaptureCardDevice = async (deviceId) => {
  editCaptureCardSwitching.value = true
  editCaptureCardError.value = ''
  try {
    const response = await fetch('/api/devices/capture-card/active', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: Number(deviceId) }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || t('excelExecution.alerts.switchCaptureCardDeviceFailed'))
    }
    if (data.active_device && Number.isInteger(data.active_device.device_id)) {
      editCaptureCardActiveDeviceId.value = data.active_device.device_id
    }
    // 切换成功立即重新挂载流，避免显示上一台设备的最后一帧
    if (editDevicePreviewSource.value === EDIT_DEVICE_PREVIEW_SOURCE_CAPTURE_CARD) {
      editDevicePreviewStreamVersion.value += 1
      editDevicePreviewUrl.value = buildEditDevicePreviewStreamUrl()
    }
  } catch (error) {
    editCaptureCardError.value = error?.message || t('excelExecution.alerts.switchCaptureCardDeviceFailed')
  } finally {
    editCaptureCardSwitching.value = false
  }
}

const stopAndResetEditKeyMonitor = async () => {
  stopEditKeyMonitorStatusPolling()

  if (editKeyMonitorActive.value || editKeyMonitorStarting.value) {
    try {
      await fetch('/api/keymonitor/stop', { method: 'POST' })
    } catch {}
  }

  resetEditKeyMonitorState()
}

const openCaseEditModal = (item) => {
  editingCaseIndex.value = item.idx
  editingCaseExcelRow.value = item.row.row
  editingCaseForm.title = item.row.title || ''
  editingCaseForm.ori_step = item.row.oriStep || item.row.step || ''
  editingCaseForm.pre_script = item.row.preScript || ''
  editingCaseForm.verify_image = item.row.verify_image || ''
  const rawResult = item.row.result || item.row.test_result || ''
  editingCaseForm.test_result = String(rawResult).toUpperCase() === 'FAIL' ? 'Fail' : rawResult
  editKeyMonitorTargetField.value = hasMeaningfulValue(item.row.preScript) ? 'pre_script' : 'ori_step'
  editCaseStepsMessage.value = ''
  editCaseStepsError.value = ''
  // 每次打开模态都重新拉一次采集卡设备列表，避免出现"没设备让用户选择"的空下拉
  editCaptureCardListLoaded = false
  showCaseEditModal.value = true
  startEditKeyMonitorStatusPolling()
  loadEditKeyMonitorMappings()
  startEditDevicePreview()
}

const closeCaseEditModal = () => {
  showCaseEditModal.value = false
  editingCaseIndex.value = null
  editingCaseExcelRow.value = null
  editingCaseForm.title = ''
  editingCaseForm.ori_step = ''
  editingCaseForm.pre_script = ''
  editingCaseForm.verify_image = ''
  editingCaseForm.test_result = ''
  editCaseStepsMessage.value = ''
  editCaseStepsError.value = ''
  void stopAndResetEditKeyMonitor()
  stopEditDevicePreview()
}

// "执行步骤" 按钮：把 ori_step + pre_script 直接发给设备执行，不截图、不做图像比对
const editCaseStepsExecutableCommands = computed(() => {
  const segments = []
  for (const raw of [editingCaseForm.ori_step, editingCaseForm.pre_script]) {
    const text = String(raw || '').trim()
    if (!text) continue
    const cleaned = text
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item && item.toLowerCase() !== 'tts')
    segments.push(...cleaned)
  }
  return segments
})

const canExecuteEditCaseSteps = computed(() => {
  return Boolean(selectedDevice.value)
    && editCaseStepsExecutableCommands.value.length > 0
})

const executeEditCaseSteps = async () => {
  if (!canExecuteEditCaseSteps.value || executingEditCaseSteps.value) {
    return
  }

  const commandsText = editCaseStepsExecutableCommands.value.join(',')
  executingEditCaseSteps.value = true
  editCaseStepsError.value = ''
  editCaseStepsMessage.value = ''

  try {
    const response = await fetch('/api/devices/commands/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commands: commandsText })
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || t('excelExecution.alerts.executeCaseStepsFailed'))
    }
    const failed = (Array.isArray(data?.results) ? data.results : []).filter((item) => item.status === 'error')
    if (failed.length > 0) {
      editCaseStepsError.value = failed.map((item) => item.message).join('；')
    } else {
      editCaseStepsMessage.value = t('excelExecution.alerts.batchComplete', {
        label: t('excelExecution.executeCaseSteps'),
        count: editCaseStepsExecutableCommands.value.length,
      })
    }
  } catch (error) {
    editCaseStepsError.value = error?.message || t('excelExecution.alerts.executeCaseStepsFailed')
  } finally {
    executingEditCaseSteps.value = false
  }
}

const saveCaseFields = async () => {
  if (!selectedFile.value || !editingCaseIndex.value || !editingCaseExcelRow.value) {
    return
  }

  savingCaseFields.value = true
  try {
    const response = await fetch('/api/excel/update_case_fields', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        file_name: selectedFile.value,
        excel_row: editingCaseExcelRow.value,
        title: editingCaseForm.title,
        ori_step: editingCaseForm.ori_step,
        pre_script: editingCaseForm.pre_script,
        step: editingCaseForm.ori_step,
        verify_image: editingCaseForm.verify_image,
        test_result: editingCaseForm.test_result
      })
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelExecution.alerts.updateCaseFailedSimple')))
    }

    const rowData = excelAnalysis.value?.valid_rows?.[editingCaseIndex.value - 1]
    if (rowData) {
      const nextCommands = [
        ...normalizeCommandList(editingCaseForm.ori_step),
        ...normalizeCommandList(editingCaseForm.pre_script)
      ]

      rowData.title = editingCaseForm.title
      if (hasMeaningfulValue(rowData.oriStep) || hasMeaningfulValue(rowData.preScript) || Array.isArray(rowData.commands)) {
        rowData.oriStep = editingCaseForm.ori_step
        rowData.preScript = editingCaseForm.pre_script
      } else {
        rowData.step = editingCaseForm.ori_step
      }
      rowData.commands = nextCommands
      if (Array.isArray(rowData.command)) {
        rowData.command = [...nextCommands]
      }
      rowData.verify_image = editingCaseForm.verify_image
      rowData.result = editingCaseForm.test_result
      rowData.test_result = editingCaseForm.test_result
    }

    closeCaseEditModal()
  } catch (error) {
    console.error('更新用例字段失败:', error)
    alert(t('excelExecution.alerts.updateCaseFailed', { detail: error.message }))
  } finally {
    savingCaseFields.value = false
  }
}

const normalizeVerifyImageName = (imageName) => {
  return String(imageName || '')
    .split(/[/\\]/)
    .pop()
    ?.trim()
    .toLowerCase() || ''
}

const getResultClass = (value) => {
  const upper = String(value || '').toUpperCase()
  if (upper === 'PASS') return 'text-success'
  if (['FAIL', 'ERROR'].includes(upper)) return 'text-danger'
  if (upper === 'NT') return 'text-warning'
  if (upper === 'NA') return 'text-info'
  return 'text-gray-400'
}

const hasMeaningfulValue = (value) => {
  if (value === null || value === undefined) {
    return false
  }

  const normalized = String(value).trim()
  return normalized !== '' && normalized.toLowerCase() !== 'nan'
}

const normalizeCommandList = (value) => {
  if (Array.isArray(value)) {
    return value
      .map((item) => String(item ?? '').trim())
      .filter((item) => hasMeaningfulValue(item))
  }

  if (!hasMeaningfulValue(value)) {
    return []
  }

  return String(value)
    .split(/[\r\n,，]+/)
    .map((item) => item.trim())
    .filter((item) => hasMeaningfulValue(item))
}

const parseCommandRepeat = (value) => {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
}

const parseCommandDelay = (value) => {
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0
}

const formatCommandDelay = (delay) => {
  if (!delay) {
    return ''
  }

  const normalized = Number.isInteger(delay)
    ? String(delay)
    : String(Number(delay.toFixed(delay >= 10 ? 0 : 1)))

  return `${normalized}s`
}

const buildRowCommandToken = (rawCommand, sequenceIndex, groupIndex, commandIndex) => {
  if (!hasMeaningfulValue(rawCommand)) {
    return null
  }

  const raw = String(rawCommand).trim()
  const parts = raw.split('/')
  const key = String(parts[0] || raw).trim().toUpperCase()
  const repeat = parseCommandRepeat(parts[1])
  const delay = parseCommandDelay(parts[2])
  const meta = []

  if (repeat > 1) {
    meta.push(`x${repeat}`)
  }
  if (delay > 0) {
    meta.push(formatCommandDelay(delay))
  }

  return {
    id: `cmd-${groupIndex}-${commandIndex}-${sequenceIndex}`,
    raw,
    key,
    repeat,
    delay,
    meta: meta.join(' / '),
    sequenceIndex
  }
}

const getRowCommandGroups = (row) => {
  const groups = []
  const seenSources = new Set()
  let sequenceIndex = 0

  const addGroup = (sourceValue) => {
    const commands = normalizeCommandList(sourceValue)
    if (!commands.length) {
      return
    }

    const signature = commands.join('|')
    if (seenSources.has(signature)) {
      return
    }

    seenSources.add(signature)
    const groupIndex = groups.length
    const parsedCommands = commands
      .map((command, commandIndex) => buildRowCommandToken(command, sequenceIndex + commandIndex, groupIndex, commandIndex))
      .filter(Boolean)

    if (!parsedCommands.length) {
      return
    }

    sequenceIndex += parsedCommands.length
    groups.push({
      id: `step-group-${groupIndex}`,
      commands: parsedCommands
    })
  }

  if (Array.isArray(row?.commands) && row.commands.length > 0) {
    addGroup(row.commands)
    return groups
  }

  if (Array.isArray(row?.command) && row.command.length > 0) {
    addGroup(row.command)
    return groups
  }

  const hasSplitStepFields = hasMeaningfulValue(row?.oriStep) || hasMeaningfulValue(row?.preScript)
  if (hasSplitStepFields) {
    addGroup(row?.oriStep)
    addGroup(row?.preScript)
    return groups
  }

  addGroup(row?.step)
  addGroup(row?.command)
  return groups
}

const getRowCommandSequence = (row) => {
  return getRowCommandGroups(row).flatMap((group) => group.commands)
}

const getRowCommandSequenceTitle = (row) => {
  return getRowCommandSequence(row)
    .map((command) => command.raw)
    .join(', ')
}

const getExecutingKeyFromMessage = (message) => {
  if (typeof message !== 'string') {
    return ''
  }

  // 匹配 "✓ DOWN 发送成功" 或 "✓ DOWN (1/9) 发送成功" 格式
  const successMatch = message.match(/^✓\s+(\S+)/)
  if (successMatch && message.includes('发送成功')) {
    return successMatch[1].trim().toUpperCase()
  }

  // 匹配 "✗ DOWN 发送失败" 格式
  const failMatch = message.match(/^✗\s+(\S+)/)
  if (failMatch && message.includes('发送失败')) {
    return failMatch[1].trim().toUpperCase()
  }

  // 匹配 "发送 HOME (keycode=3)" 格式（兼容）
  const sendMatch = message.match(/^发送\s+(\S+)/)
  if (sendMatch) {
    return sendMatch[1].trim().toUpperCase()
  }

  return ''
}

const setRowExecutionProgress = (rowIndex, progress) => {
  rowExecutionProgress.value = {
    ...rowExecutionProgress.value,
    [rowIndex]: progress
  }
}

const clearRowExecutionProgress = (rowIndex) => {
  if (!Object.prototype.hasOwnProperty.call(rowExecutionProgress.value, rowIndex)) {
    return
  }

  const nextProgress = { ...rowExecutionProgress.value }
  delete nextProgress[rowIndex]
  rowExecutionProgress.value = nextProgress
}

const updateRowExecutionProgress = (rowIndex, message) => {
  const key = getExecutingKeyFromMessage(message)
  if (!key) {
    return
  }

  const rowData = excelAnalysis.value?.valid_rows?.[rowIndex - 1]
  if (!rowData) {
    return
  }

  const sequence = getRowCommandSequence(rowData)
  if (!sequence.length) {
    return
  }

  const previous = rowExecutionProgress.value[rowIndex] || null
  let nextIndex = -1
  let nextRepeat = 1

  if (previous && Number.isInteger(previous.sequenceIndex) && previous.sequenceIndex >= 0) {
    const currentCommand = sequence[previous.sequenceIndex]
    if (currentCommand?.key === key && previous.repeatProgress < currentCommand.repeat) {
      nextIndex = previous.sequenceIndex
      nextRepeat = previous.repeatProgress + 1
    } else {
      nextIndex = sequence.findIndex((command, commandIndex) => commandIndex > previous.sequenceIndex && command.key === key)
    }
  }

  if (nextIndex === -1) {
    nextIndex = sequence.findIndex((command) => command.key === key)
  }

  if (nextIndex === -1) {
    return
  }

  const activeCommand = sequence[nextIndex]
  setRowExecutionProgress(rowIndex, {
    sequenceIndex: nextIndex,
    repeatProgress: nextRepeat,
    repeatTotal: activeCommand.repeat,
    key: activeCommand.key,
    raw: activeCommand.raw
  })
}

const getRowCommandProgress = (rowIndex, command) => {
  const progress = rowExecutionProgress.value[rowIndex]
  if (!progress || progress.sequenceIndex !== command.sequenceIndex) {
    return null
  }

  return progress
}

const isRowCommandActive = (rowIndex, command) => {
  return Boolean(getRowCommandProgress(rowIndex, command))
}

const getRowCommandProgressText = (rowIndex, command) => {
  const progress = getRowCommandProgress(rowIndex, command)
  if (!progress || command.repeat <= 1) {
    return ''
  }

  return `${Math.min(progress.repeatProgress, command.repeat)}/${command.repeat}`
}

const getLocalVerifyImageEntry = (imageName) => {
  const key = normalizeVerifyImageName(imageName)
  return key ? localVerifyImageMap.value[key] || null : null
}

const clearLocalVerifyImageCache = () => {
  Object.values(localVerifyImageMap.value).forEach((entry) => {
    if (entry?.url) {
      URL.revokeObjectURL(entry.url)
    }
  })
  localVerifyImageMap.value = {}
  verifyImageFileCount.value = 0
  verifyImageFolderName.value = ''
}

const triggerVerifyImageFolderPicker = async (request = null) => {
  pendingVerifyImageRequest.value = request

  if (supportsPersistentDirectoryHandle()) {
    try {
      const directoryHandle = await window.showDirectoryPicker()
      pendingVerifyImageRequest.value = null
      await applyVerifyImageDirectoryHandle(directoryHandle, {
        persist: true,
        pendingRequest: request
      })
      return
    } catch (error) {
      if (error?.name === 'AbortError') {
        pendingVerifyImageRequest.value = null
        return
      }

      console.error('选择校验图片文件夹失败，回退为目录上传:', error)
    }
  }

  verifyImageFolderInput.value?.click()
}

const inferFolderName = (files) => {
  const firstFile = files[0]
  if (!firstFile) return ''
  const relativePath = firstFile.webkitRelativePath || ''
  if (!relativePath.includes('/')) return t('excelExecution.localFolderSelected')
  return relativePath.split('/')[0]
}

const applyVerifyImagePreview = (imageName) => {
  const matchedEntry = getLocalVerifyImageEntry(imageName)
  if (!matchedEntry) {
    return false
  }

  verifyImagePreviewName.value = matchedEntry.relativePath || matchedEntry.name
  verifyImageUrl.value = matchedEntry.url
  showVerifyImageModal.value = true
  return true
}

const resolveResultModalVerifyImagePlaceholder = (verifyImageName, matchedEntry) => {
  if (matchedEntry?.url) {
    return ''
  }

  if (!verifyImageName) {
    return t('excelExecution.noVerifyImage')
  }

  if (!verifyImageFileCount.value || !verifyImageFolderName.value) {
    return t('excelExecution.verifyFolderNotSelected')
  }

  return t('excelExecution.verifyImageNotFoundInFolder')
}

const closeScreenshotModal = () => {
  showScreenshotModal.value = false
  isRegionSelectMode.value = false
  regionStart.value = null
  regionEnd.value = null
}

const openExecutionResultModal = (rowIndex, matchedEntry = null) => {
  const rowData = excelAnalysis.value?.valid_rows?.[rowIndex - 1]
  const meta = rowResultMeta.value[rowIndex] || {}
  if (!rowData || (!rowScreenshots.value[rowIndex] && !meta.video_url)) {
    return
  }

  const verifyImageName = rowData.verify_image && rowData.verify_image !== 'nan'
    ? rowData.verify_image
    : ''

  const assertResults = Array.isArray(meta.assert_results)
    ? meta.assert_results.filter(Boolean)
    : []

  modalResultTitle.value = rowData.title || t('excelExecution.rowFallbackTitle', { row: rowIndex })
  modalOverallVerifyResult.value = meta.verify_result || rowData.result || rowData.test_result || ''
  modalAssertResults.value = assertResults
  modalAssertActiveIndex.value = 0

  // 设置录屏视频
  modalVideoUrl.value = meta.video_url || ''
  videoConverting.value = meta.video_converting || false

  if (assertResults.length > 0) {
    // 多次校验：默认显示第一条（也可以默认定位到第一个失败/出错项，更易排查）
    const firstFailedIndex = assertResults.findIndex((item) => item && item.verify_result && item.verify_result !== 'PASS')
    modalAssertActiveIndex.value = firstFailedIndex >= 0 ? firstFailedIndex : 0
    applyAssertResultToModal(assertResults[modalAssertActiveIndex.value])
  } else {
    // 单次校验：沿用原逻辑
    modalScreenshotUrl.value = rowScreenshots.value[rowIndex]
    modalVerifyImageName.value = matchedEntry
      ? (matchedEntry.relativePath || matchedEntry.name)
      : verifyImageName
    modalVerifyImageUrl.value = matchedEntry?.url || ''
    modalVerifyImagePlaceholder.value = resolveResultModalVerifyImagePlaceholder(verifyImageName, matchedEntry)
    modalResultStatus.value = meta.verify_result || rowData.result || rowData.test_result || ''
    modalResultScore.value = meta.score ?? null
  }

  // 设置默认保存文件名（使用校验图片名称，去掉扩展名保留原名）
  screenshotSaveFileName.value = verifyImageName.split(',')[0]?.trim() || `screenshot_row_${rowIndex}`
  isRegionSelectMode.value = false
  regionStart.value = null
  regionEnd.value = null
  screenshotLoadError.value = false
  screenshotTimestamp.value = Date.now()
  showVideoPlayer.value = false
  showScreenshotModal.value = true
}

const openVideoWithLocalPlayer = async () => {
  if (!modalVideoUrl.value) return

  // 从 URL 中提取文件名
  const filename = modalVideoUrl.value.split('/').pop()
  if (!filename) return

  try {
    const response = await fetch(`/api/recording/${filename}/open-local`, {
      method: 'POST'
    })
    const data = await response.json()
    if (data.success) {
      console.log('已在本地播放器打开:', data.path)
    }
  } catch (error) {
    console.error('打开本地播放器失败:', error)
    // 降级：尝试下载
    const link = document.createElement('a')
    link.href = modalVideoUrl.value
    link.download = filename
    link.click()
  }
}

const applyAssertResultToModal = (item) => {
  if (!item) return
  modalScreenshotUrl.value = item.screenshot_url || ''
  const matchedEntry = getLocalVerifyImageEntry(item.verify_image)
  modalVerifyImageName.value = matchedEntry
    ? (matchedEntry.relativePath || matchedEntry.name)
    : (item.verify_image || '')
  modalVerifyImageUrl.value = matchedEntry?.url || ''
  modalVerifyImagePlaceholder.value = resolveResultModalVerifyImagePlaceholder(item.verify_image || '', matchedEntry)
  modalResultStatus.value = item.verify_result || ''
  modalResultScore.value = item.score ?? null
}

const switchModalAssertResult = (index) => {
  const list = modalAssertResults.value
  if (!Array.isArray(list) || index < 0 || index >= list.length) return
  modalAssertActiveIndex.value = index
  applyAssertResultToModal(list[index])
}

const handleVerifyImageFolderChange = (event) => {
  const files = Array.from(event.target.files || [])
  const pendingRequest = pendingVerifyImageRequest.value
  pendingVerifyImageRequest.value = null

  if (verifyImageFolderInput.value) {
    verifyImageFolderInput.value.value = ''
  }

  if (files.length === 0) {
    return
  }

  const nextImageMap = {}
  for (const file of files) {
    const isImageFile = file.type.startsWith('image/') || /\.(png|jpg|jpeg|bmp|webp)$/i.test(file.name)
    if (!isImageFile) {
      continue
    }

    const key = normalizeVerifyImageName(file.name)
    if (!key || nextImageMap[key]) {
      continue
    }

    nextImageMap[key] = {
      name: file.name,
      relativePath: file.webkitRelativePath || file.name,
      url: URL.createObjectURL(file),
      file
    }
  }

  finalizeVerifyImageFolderSelection(nextImageMap, inferFolderName(files), pendingRequest)
}

// 分析文件
const analyzeFile = async (options = {}) => {
  const { silent = false, resetView = true } = options
  if (!selectedFile.value) {
    if (!silent) {
      alert(t('excelExecution.alerts.selectFileFirst'))
    }
    return
  }
  
  loadingAnalysis.value = true
  resetBatchExecutionState()
  rowExecutionProgress.value = {}
  showValidationResultModal.value = false
  try {
    const validateResponse = await fetch(`/api/excel/validate?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!validateResponse.ok) {
      throw new Error(t('excelExecution.alerts.validateFailed'))
    }

    const validateData = await validateResponse.json()
    validationResult.value = validateData

    if (!silent) {
      openValidationResultModal()
    }
    
    const response = await fetch(`/api/excel/analyze?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!response.ok) {
      throw new Error(t('excelExecution.alerts.analyzeFailed'))
    }

    const data = await response.json()
    excelAnalysis.value = data
    if (resetView) {
      filterResult.value = ''
      searchKeyword.value = ''
      currentPage.value = 1
      jumpPage.value = 1
      selectedRows.value = []
    }

    if (isOpenCvCompareBackend.value) {
      imageCompareBackendConfirmed.value = true
    }

    if (selectedFile.value && (activeImageModelName.value || isOpenCvCompareBackend.value)) {
      fileSelectorPanelExpanded.value = false
      modelSelectorPanelExpanded.value = false
    }

    applyRowResultMetaToAnalysis()
  } catch (error) {
    console.error('分析文件失败:', error)
    if (!silent) {
      alert(t('excelExecution.alerts.analyzeFailedWithDetail', { detail: error.message }))
    }
  } finally {
    loadingAnalysis.value = false
  }
}

// 执行Excel行（通过输入框）
const executeExcelRow = async () => {
  await executeExcelRowByIndex(rowIndex.value)
}

const readFileAsBase64 = async (file, cacheKey) => {
  // 优先用缓存的 base64，避免重复读 File 对象
  const normalizedKey = cacheKey ? normalizeVerifyImageName(cacheKey) : null
  if (normalizedKey) {
    const entry = localVerifyImageMap.value[normalizedKey]
    if (entry?.base64) return entry.base64
  }

  const base64 = await new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      resolve(result.includes(',') ? result.split(',')[1] : result)
    }
    reader.onerror = () => reject(new Error(t('excelExecution.alerts.readVerifyImageFailed')))
    reader.readAsDataURL(file)
  })

  // 读取成功后写入缓存，后续直接复用
  if (normalizedKey && localVerifyImageMap.value[normalizedKey]) {
    localVerifyImageMap.value[normalizedKey].base64 = base64
  }
  return base64
}

const readFileAsDataUrl = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      resolve(typeof reader.result === 'string' ? reader.result : '')
    }
    reader.onerror = () => reject(new Error(t('excelExecution.alerts.readVerifyImageFailed')))
    reader.readAsDataURL(file)
  })
}

const buildExecutionPayload = async (index) => {
  const payload = {
    file_name: selectedFile.value,
    row_index: index,
    match_threshold: matchThreshold.value,
    screenshot_source: screenshotSource.value,
    enable_verification: enableVerification.value,
    enable_recording: enableRecording.value,
  }

  // 关闭校验时不传校验图数据
  if (!enableVerification.value) {
    return payload
  }

  const rowData = excelAnalysis.value?.valid_rows?.[index - 1]
  const verifyImageRaw = String(rowData?.verify_image || '').trim()
  if (!verifyImageRaw) {
    return payload
  }

  // 多张校验图：按逗号拆分。校验图列只放文件名（无路径），路径污染会被后端再 normalize 一次
  const verifyImageNames = verifyImageRaw
    .split(',')
    .map((name) => name.trim())
    .filter(Boolean)
    .map((name) => name.split(/[/\\]/).pop())

  const verifyImageBase64List = []
  const verifyImageMissingList = []
  let anyMissing = false

  for (const imageName of verifyImageNames) {
    const matched = getLocalVerifyImageEntry(imageName)
    if (matched?.file) {
      verifyImageBase64List.push(await readFileAsBase64(matched.file, imageName))
      verifyImageMissingList.push(false)
    } else {
      verifyImageBase64List.push('')
      // 用户已配置 verify_image 文件夹但找不到该图，通知后端跳过服务端文件系统回退
      const missing = Boolean(verifyImageFolderName.value)
      verifyImageMissingList.push(missing)
      if (missing) anyMissing = true
    }
  }

  payload.verify_image_base64_list = verifyImageBase64List
  payload.verify_image_missing_list = verifyImageMissingList

  // 兼容老逻辑（单张校验图时给个等价字段，后端没切到 list 也能跑）
  if (verifyImageNames.length === 1) {
    payload.verify_image_base64 = verifyImageBase64List[0]
    payload.verify_image_missing = verifyImageMissingList[0]
  } else if (anyMissing && verifyImageNames.length > 0) {
    payload.verify_image_missing = true
  }

  return payload
}

// ===== 循环执行 =====
const loopStopFlags = ref({})

const runLoopExecution = async (index) => {
  const isFiniteLoop = loopType.value === 'finite'
  const total = isFiniteLoop ? Math.max(1, Math.floor(loopCount.value || 1)) : Infinity
  let current = 0
  let stopped = false

  loopStopFlags.value[index] = false
  executionResults.value = []
  rowAllResults.value[index] = []

  const rowData = excelAnalysis.value?.valid_rows?.[index - 1]
  const title = rowData?.title || `第 ${index} 行`

  executionResults.value.push(buildRowExecutionLogEntry(index, {
    status: 'info',
    message: isFiniteLoop
      ? (t('excelExecution.loopStartFinite', { title, count: total }) || `开始有限循环执行：${title}，共 ${total} 轮`)
      : (t('excelExecution.loopStartInfinite', { title }) || `开始无限循环执行：${title}`)
  }))

  while (current < total) {
    if (loopStopFlags.value[index] || stopExecutionFlags.value[index]) {
      stopped = true
      break
    }

    current++
    const progressMsg = isFiniteLoop
      ? (t('excelExecution.loopProgressWithTotal', { current, total }) || `第 ${current}/${total} 轮执行中...`)
      : (t('excelExecution.loopProgress', { current }) || `第 ${current} 轮执行中（无限模式）...`)
    updateRowExecutionProgress(index, progressMsg)

    await runSingleExecutionOnce(index)

    if (loopStopFlags.value[index] || stopExecutionFlags.value[index]) {
      stopped = true
      break
    }

    // 轮次间隔
    if (current < total) {
      await new Promise(r => setTimeout(r, 1000))
    }
  }

  const finalMsg = stopped
    ? (t('excelExecution.loopStopped', { count: current }) || `循环执行已停止，已完成 ${current} 轮`)
    : (t('excelExecution.loopComplete', { count: current }) || `循环执行完成，共 ${current} 轮`)
  executionResults.value.push(buildRowExecutionLogEntry(index, {
    status: stopped ? 'info' : 'success',
    message: finalMsg
  }))
  clearRowExecutionProgress(index)
}

// 单次执行核心（不含循环包装），返回 Promise
const runSingleExecutionOnce = (index) => {
  return new Promise((resolve) => {
    executingRows.value[index] = true
    stopExecutionFlags.value[index] = false
    const abortController = new AbortController()
    executionAbortControllers.value[index] = abortController

    const finishExecution = () => {
      // 收集本次执行结果到 rowAllResults
      const meta = rowResultMeta.value[index]
      if (meta && (meta.verify_result || meta.screenshot_url)) {
        if (!rowAllResults.value[index]) {
          rowAllResults.value[index] = []
        }
        rowAllResults.value[index].push({
          status: meta.verify_result || '',
          score: meta.score ?? null,
          detail: meta.detail || meta.last_message || '',
          screenshot_url: meta.screenshot_url || rowScreenshots.value[index] || '',
          video_url: meta.video_url || '',
          compare_engine: meta.compare_engine || '',
          model_name: meta.model_name || '',
          compare_details: normalizeCompareDetails(meta.compare_details),
          execution_logs: (executionResults.value || []).slice().map(item => ({
            status: item.status,
            message: item.message,
          })),
        })
      }
      executingRows.value[index] = false
      clearExecutionAbortController(index)
      resolve()
    }

    buildExecutionPayload(index)
      .then((payload) => fetch('/api/excel/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortController.signal,
        body: JSON.stringify(payload)
      }))
      .then(response => {
        if (!response.ok) {
          throw new Error(t('excelExecution.alerts.executionFailed'))
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const readChunk = () => {
          if (abortController.signal.aborted || stopExecutionFlags.value[index]) {
            finishExecution()
            return
          }

          reader.read().then(({ done, value }) => {
            if (done) {
              finishExecution()
              return
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop()

            lines.forEach(line => {
              if (line.startsWith('data:')) {
                const data = line.substring(5).trim()
                if (data) {
                  try {
                    const result = JSON.parse(data)
                    const eventRecord = {
                      ...result,
                      ...buildRowExecutionLogEntry(index, result)
                    }
                    executionResults.value.push(eventRecord)
                    updateRowExecutionProgress(index, eventRecord.message)

                    const previousMeta = rowResultMeta.value[index] || {}
                    const isAssertItemEvent = Number.isFinite(eventRecord.assert_index)
                      && (eventRecord.verify_result === 'PASS'
                        || eventRecord.verify_result === 'FAIL'
                        || eventRecord.verify_result === 'ERROR')
                    const isMultiVerifyFinal = Array.isArray(eventRecord.multi_verify_results)

                    if (isAssertItemEvent) {
                      const previousAssertResults = Array.isArray(previousMeta.assert_results)
                        ? [...previousMeta.assert_results]
                        : []
                      previousAssertResults[eventRecord.assert_index] = {
                        assert_index: eventRecord.assert_index,
                        verify_image: eventRecord.verify_image || '',
                        screenshot_url: eventRecord.screenshot_url || '',
                        verify_result: eventRecord.verify_result,
                        score: Object.prototype.hasOwnProperty.call(eventRecord, 'score') ? (eventRecord.score ?? null) : null,
                        message: eventRecord.message || '',
                        compare_engine: eventRecord.compare_engine || '',
                        model_name: eventRecord.model_name || '',
                        compare_details: normalizeCompareDetails(eventRecord.compare_details),
                      }
                      rowResultMeta.value[index] = {
                        ...previousMeta,
                        assert_results: previousAssertResults,
                        status: eventRecord.status || previousMeta.status || '',
                        last_message: eventRecord.message || previousMeta.last_message || '',
                        verify_result: eventRecord.verify_result || previousMeta.verify_result || '',
                        score: Object.prototype.hasOwnProperty.call(eventRecord, 'score') ? (eventRecord.score ?? null) : (previousMeta.score ?? null),
                        screenshot_url: eventRecord.screenshot_url || previousMeta.screenshot_url || '',
                        video_url: eventRecord.video_url || previousMeta.video_url || '',
                        video_converting: eventRecord.video_converting || false,
                        compare_engine: eventRecord.compare_engine || previousMeta.compare_engine || '',
                        model_name: eventRecord.model_name || previousMeta.model_name || '',
                        compare_details: Object.keys(normalizeCompareDetails(eventRecord.compare_details)).length
                          ? normalizeCompareDetails(eventRecord.compare_details)
                          : normalizeCompareDetails(previousMeta.compare_details),
                      }
                      if (eventRecord.screenshot_url) {
                        rowScreenshots.value[index] = eventRecord.screenshot_url
                      }
                    } else if (isMultiVerifyFinal) {
                      const finalAssertResults = eventRecord.multi_verify_results.map((r) => ({
                        assert_index: Number.isFinite(r.assert_index) ? r.assert_index : 0,
                        verify_image: r.verify_image || '',
                        screenshot_url: r.screenshot_url || '',
                        verify_result: r.verify_result || '',
                        score: Object.prototype.hasOwnProperty.call(r, 'score') ? (r.score ?? null) : null,
                        message: r.message || '',
                        compare_engine: r.compare_engine || '',
                        model_name: r.model_name || '',
                        compare_details: normalizeCompareDetails(r.compare_details),
                      }))
                      // 从最后一个 assert 结果中取 compare_details 等信息
                      const lastAssert = finalAssertResults[finalAssertResults.length - 1] || {}
                      rowResultMeta.value[index] = {
                        ...previousMeta,
                        assert_results: finalAssertResults,
                        verify_result: eventRecord.verify_result || previousMeta.verify_result || '',
                        status: eventRecord.status || previousMeta.status || '',
                        last_message: eventRecord.message || previousMeta.last_message || '',
                        screenshot_url: eventRecord.screenshot_url || previousMeta.screenshot_url || '',
                        video_url: eventRecord.video_url || previousMeta.video_url || '',
                        video_converting: eventRecord.video_converting || false,
                        detail: eventRecord.message || previousMeta.detail || '',
                        score: lastAssert.score ?? (previousMeta.score ?? null),
                        compare_engine: lastAssert.compare_engine || previousMeta.compare_engine || '',
                        model_name: lastAssert.model_name || previousMeta.model_name || '',
                        compare_details: Object.keys(lastAssert.compare_details || {}).length
                          ? lastAssert.compare_details
                          : normalizeCompareDetails(previousMeta.compare_details),
                      }
                      if (eventRecord.screenshot_url) {
                        rowScreenshots.value[index] = eventRecord.screenshot_url
                      }
                      const rowData = excelAnalysis.value.valid_rows[index - 1]
                      if (rowData) {
                        rowData.result = eventRecord.verify_result
                        rowData.test_result = eventRecord.verify_result
                      }
                    } else {
                      rowResultMeta.value[index] = {
                        ...previousMeta,
                        status: eventRecord.status || previousMeta.status || '',
                        last_message: eventRecord.message || previousMeta.last_message || '',
                        score: Object.prototype.hasOwnProperty.call(eventRecord, 'score') ? (eventRecord.score ?? null) : (previousMeta.score ?? null),
                        screenshot_url: eventRecord.screenshot_url || previousMeta.screenshot_url || '',
                        video_url: eventRecord.video_url || previousMeta.video_url || '',
                        video_converting: eventRecord.video_converting || false,
                        compare_engine: eventRecord.compare_engine || previousMeta.compare_engine || '',
                        model_name: eventRecord.model_name || previousMeta.model_name || '',
                        compare_details: Object.keys(normalizeCompareDetails(eventRecord.compare_details)).length
                          ? normalizeCompareDetails(eventRecord.compare_details)
                          : normalizeCompareDetails(previousMeta.compare_details),
                        detail: eventRecord.verify_result
                          ? buildExcelBatchResultDetail(eventRecord.message, eventRecord.score, eventRecord.compare_engine, eventRecord.model_name)
                          : (eventRecord.status === 'error' && eventRecord.message ? eventRecord.message : (previousMeta.detail || '')),
                        verify_result: eventRecord.verify_result || previousMeta.verify_result || ''
                      }
                      if (eventRecord.screenshot_url) {
                        rowScreenshots.value[index] = eventRecord.screenshot_url
                      }
                      if (eventRecord.verify_result) {
                        rowResultMeta.value[index] = {
                          ...rowResultMeta.value[index],
                          verify_result: eventRecord.verify_result,
                          score: eventRecord.score ?? null,
                          status: eventRecord.status || previousMeta.status || '',
                          last_message: eventRecord.message || previousMeta.last_message || '',
                          screenshot_url: eventRecord.screenshot_url || previousMeta.screenshot_url || '',
                          video_url: eventRecord.video_url || previousMeta.video_url || '',
                          video_converting: eventRecord.video_converting || false,
                          compare_engine: eventRecord.compare_engine || previousMeta.compare_engine || '',
                          model_name: eventRecord.model_name || previousMeta.model_name || '',
                          compare_details: Object.keys(normalizeCompareDetails(eventRecord.compare_details)).length
                            ? normalizeCompareDetails(eventRecord.compare_details)
                            : normalizeCompareDetails(previousMeta.compare_details),
                          detail: buildExcelBatchResultDetail(eventRecord.message, eventRecord.score, eventRecord.compare_engine, eventRecord.model_name)
                        }
                        const rowData = excelAnalysis.value.valid_rows[index - 1]
                        if (rowData) {
                          rowData.result = eventRecord.verify_result
                          rowData.test_result = eventRecord.verify_result
                        }
                      }
                    }
                  } catch (e) {
                    console.error('解析数据失败:', e)
                  }
                }
              }
            })

            readChunk()
          })
            .catch(error => {
              if (abortController.signal.aborted || stopExecutionFlags.value[index] || isAbortError(error)) {
                finishExecution()
                return
              }
              console.error('读取流失败:', error)
              executionResults.value.push(buildRowExecutionLogEntry(index, {
                status: 'error',
                message: t('excelExecution.alerts.executionFailedWithDetail', { detail: error.message })
              }))
              finishExecution()
            })
        }

        readChunk()
      })
      .catch(error => {
        if (abortController.signal.aborted || stopExecutionFlags.value[index] || isAbortError(error)) {
          finishExecution()
          return
        }
        console.error('执行命令失败:', error)
        executionResults.value.push(buildRowExecutionLogEntry(index, {
          status: 'error',
          message: t('excelExecution.alerts.executionFailedWithDetail', { detail: error.message })
        }))
        finishExecution()
      })
  })
}

// 执行Excel行（通过点击按钮）
const executeExcelRowByIndex = (index) => {
  // 单行循环模式：委托给 runLoopExecution
  if (executionMode.value === 'loop_row') {
    return new Promise(async (resolve) => {
      if (!selectedDevice.value) {
        alert(t('common.deviceRequired'))
        resolve()
        return
      }
      if (!selectedFile.value) {
        alert(t('excelExecution.alerts.selectFileFirst'))
        resolve()
        return
      }
      if (enableVerification.value && !verifyImageFolderName.value) {
        const action = await showVerifyFolderAlert()
        if (action === 'select') { resolve(); return }
      }
      if (!index || index < 1 || index > excelAnalysis.value.valid_rows.length) {
        alert(t('excelExecution.alerts.invalidRow'))
        resolve()
        return
      }
      if (!isBatchExecuting.value && batchExecutionState.total > 0) {
        resetBatchExecutionState()
      }
      runLoopExecution(index).finally(resolve)
    })
  }

  return new Promise(async (resolve) => {
    if (!selectedDevice.value) {
      alert(t('common.deviceRequired'))
      resolve()
      return
    }

    if (!selectedFile.value) {
      alert(t('excelExecution.alerts.selectFileFirst'))
      resolve()
      return
    }

    if (enableVerification.value && !verifyImageFolderName.value) {
      const action = await showVerifyFolderAlert()
      if (action === 'select') { resolve(); return }
    }

    if (!index || index < 1 || index > excelAnalysis.value.valid_rows.length) {
      alert(t('excelExecution.alerts.invalidRow'))
      resolve()
      return
    }

    if (!isBatchExecuting.value && batchExecutionState.total > 0) {
      resetBatchExecutionState()
    }

    executingRows.value[index] = true
    stopExecutionFlags.value[index] = false
    rowResultMeta.value[index] = {}
    rowAllResults.value[index] = []
    clearRowExecutionProgress(index)
    const abortController = new AbortController()
    executionAbortControllers.value[index] = abortController
    if (!isBatchExecuting.value) {
      executionResults.value = []
    }

    let stopReported = false
    const reportStopped = () => {
      if (stopReported) {
        return
      }

      stopReported = true
      executionResults.value.push(buildRowExecutionLogEntry(index, {
        status: 'info',
        message: t('excelExecution.alerts.executionStopped')
      }))
    }

    const finishExecution = () => {
      executingRows.value[index] = false
      clearRowExecutionProgress(index)
      clearExecutionAbortController(index)
      resolve()
    }

    buildExecutionPayload(index)
      .then((payload) => fetch('/api/excel/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: abortController.signal,
        body: JSON.stringify(payload)
      }))
      .then(response => {
        if (!response.ok) {
          throw new Error(t('excelExecution.alerts.executionFailed'))
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const readChunk = () => {
          if (abortController.signal.aborted || stopExecutionFlags.value[index]) {
            reportStopped()
            finishExecution()
            return
          }

          reader.read().then(({ done, value }) => {
            if (done) {
              finishExecution()
              return
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop()

            lines.forEach(line => {
              if (line.startsWith('data:')) {
                const data = line.substring(5).trim()
                if (data) {
                  try {
                    const result = JSON.parse(data)
                    const eventRecord = {
                      ...result,
                      ...buildRowExecutionLogEntry(index, result)
                    }
                    executionResults.value.push(eventRecord)
                    updateRowExecutionProgress(index, eventRecord.message)

                    const previousMeta = rowResultMeta.value[index] || {}
                    const isAssertItemEvent = Number.isFinite(eventRecord.assert_index)
                      && (eventRecord.verify_result === 'PASS'
                        || eventRecord.verify_result === 'FAIL'
                        || eventRecord.verify_result === 'ERROR')
                    const isMultiVerifyFinal = Array.isArray(eventRecord.multi_verify_results)

                    if (isAssertItemEvent) {
                      // 单次 ASSERT 校验：累积到 assert_results 数组里，不动整体 verify_result
                      const previousAssertResults = Array.isArray(previousMeta.assert_results)
                        ? [...previousMeta.assert_results]
                        : []
                      previousAssertResults[eventRecord.assert_index] = {
                        assert_index: eventRecord.assert_index,
                        verify_image: eventRecord.verify_image || '',
                        screenshot_url: eventRecord.screenshot_url || '',
                        verify_result: eventRecord.verify_result,
                        score: Object.prototype.hasOwnProperty.call(eventRecord, 'score') ? (eventRecord.score ?? null) : null,
                        message: eventRecord.message || '',
                        compare_engine: eventRecord.compare_engine || '',
                        model_name: eventRecord.model_name || '',
                        compare_details: normalizeCompareDetails(eventRecord.compare_details),
                      }
                      rowResultMeta.value[index] = {
                        ...previousMeta,
                        assert_results: previousAssertResults,
                        status: eventRecord.status || previousMeta.status || '',
                        last_message: eventRecord.message || previousMeta.last_message || '',
                        video_url: eventRecord.video_url || previousMeta.video_url || '',
                      }
                      if (eventRecord.screenshot_url) {
                        rowScreenshots.value[index] = eventRecord.screenshot_url
                      }
                    } else if (isMultiVerifyFinal) {
                      // 最终汇总事件：把 multi_verify_results 存下来作为详情列表，verify_result 取整体结论
                      const finalAssertResults = eventRecord.multi_verify_results.map((r) => ({
                        assert_index: Number.isFinite(r.assert_index) ? r.assert_index : 0,
                        verify_image: r.verify_image || '',
                        screenshot_url: r.screenshot_url || '',
                        verify_result: r.verify_result || '',
                        score: Object.prototype.hasOwnProperty.call(r, 'score') ? (r.score ?? null) : null,
                        message: r.message || '',
                        compare_engine: r.compare_engine || '',
                        model_name: r.model_name || '',
                        compare_details: normalizeCompareDetails(r.compare_details),
                      }))
                      rowResultMeta.value[index] = {
                        ...previousMeta,
                        assert_results: finalAssertResults,
                        verify_result: eventRecord.verify_result || previousMeta.verify_result || '',
                        status: eventRecord.status || previousMeta.status || '',
                        last_message: eventRecord.message || previousMeta.last_message || '',
                        screenshot_url: eventRecord.screenshot_url || previousMeta.screenshot_url || '',
                        video_url: eventRecord.video_url || previousMeta.video_url || '',
                        detail: eventRecord.message || previousMeta.detail || '',
                      }
                      if (eventRecord.screenshot_url) {
                        rowScreenshots.value[index] = eventRecord.screenshot_url
                      }
                      const rowData = excelAnalysis.value.valid_rows[index - 1]
                      if (rowData) {
                        rowData.result = eventRecord.verify_result
                        rowData.test_result = eventRecord.verify_result
                      }
                    } else {
                      // 普通命令事件：沿用原来的"末次事件覆盖整体 verify_result"语义
                      rowResultMeta.value[index] = {
                        ...previousMeta,
                        status: eventRecord.status || previousMeta.status || '',
                        last_message: eventRecord.message || previousMeta.last_message || '',
                        score: Object.prototype.hasOwnProperty.call(eventRecord, 'score') ? (eventRecord.score ?? null) : (previousMeta.score ?? null),
                        screenshot_url: eventRecord.screenshot_url || previousMeta.screenshot_url || '',
                        video_url: eventRecord.video_url || previousMeta.video_url || '',
                        compare_engine: eventRecord.compare_engine || previousMeta.compare_engine || '',
                        model_name: eventRecord.model_name || previousMeta.model_name || '',
                        compare_details: Object.keys(normalizeCompareDetails(eventRecord.compare_details)).length
                          ? normalizeCompareDetails(eventRecord.compare_details)
                          : normalizeCompareDetails(previousMeta.compare_details),
                        detail: eventRecord.verify_result
                          ? buildExcelBatchResultDetail(eventRecord.message, eventRecord.score, eventRecord.compare_engine, eventRecord.model_name)
                          : (eventRecord.status === 'error' && eventRecord.message ? eventRecord.message : (previousMeta.detail || '')),
                        verify_result: eventRecord.verify_result || previousMeta.verify_result || ''
                      }
                      if (eventRecord.screenshot_url) {
                        rowScreenshots.value[index] = eventRecord.screenshot_url
                      }
                      if (eventRecord.verify_result) {
                        rowResultMeta.value[index] = {
                          ...rowResultMeta.value[index],
                          verify_result: eventRecord.verify_result,
                          score: eventRecord.score ?? null,
                          status: eventRecord.status || previousMeta.status || '',
                          last_message: eventRecord.message || previousMeta.last_message || '',
                          screenshot_url: eventRecord.screenshot_url || previousMeta.screenshot_url || '',
                          video_url: eventRecord.video_url || previousMeta.video_url || '',
                          video_converting: eventRecord.video_converting || false,
                          compare_engine: eventRecord.compare_engine || previousMeta.compare_engine || '',
                          model_name: eventRecord.model_name || previousMeta.model_name || '',
                          compare_details: Object.keys(normalizeCompareDetails(eventRecord.compare_details)).length
                            ? normalizeCompareDetails(eventRecord.compare_details)
                            : normalizeCompareDetails(previousMeta.compare_details),
                          detail: buildExcelBatchResultDetail(eventRecord.message, eventRecord.score, eventRecord.compare_engine, eventRecord.model_name)
                        }
                        const rowData = excelAnalysis.value.valid_rows[index - 1]
                        if (rowData) {
                          rowData.result = eventRecord.verify_result
                          rowData.test_result = eventRecord.verify_result
                        }
                      }
                    }
                  } catch (e) {
                    console.error('解析数据失败:', e)
                  }
                }
              }
            })

            readChunk()
          })
            .catch(error => {
              if (abortController.signal.aborted || stopExecutionFlags.value[index] || isAbortError(error)) {
                reportStopped()
                finishExecution()
                return
              }

              console.error('读取流失败:', error)
              executionResults.value.push(buildRowExecutionLogEntry(index, {
                status: 'error',
                message: t('excelExecution.alerts.executionFailedWithDetail', { detail: error.message })
              }))
              finishExecution()
            })
        }

        readChunk()
      })
      .catch(error => {
        if (abortController.signal.aborted || stopExecutionFlags.value[index] || isAbortError(error)) {
          reportStopped()
          finishExecution()
          return
        }

        console.error('执行命令失败:', error)
        executionResults.value = [
          buildRowExecutionLogEntry(index, { status: 'error', message: t('excelExecution.alerts.executionFailedWithDetail', { detail: error.message }) })
        ]
        finishExecution()
      })
  })
}
// 停止执行
const stopExecution = (index) => {
  stopExecutionFlags.value[index] = true
  loopStopFlags.value[index] = true
  abortExecution(index)
}

// 手动切换执行结果弹窗
const resultPopoverIndex = ref(null)
const resultPopoverPos = ref({ left: 0, top: 0 })
const resultBtnRefs = {}

const setResultBtnRef = (idx, el) => {
  if (el) {
    resultBtnRefs[idx] = el
  }
}

// 切换结果弹窗
const toggleResultPopover = (idx, event) => {
  if (resultPopoverIndex.value === idx) {
    closeResultPopover()
    return
  }
  resultPopoverIndex.value = idx
  // 计算弹窗位置（在按钮下方）
  const btn = resultBtnRefs[idx]
  if (btn) {
    const rect = btn.getBoundingClientRect()
    resultPopoverPos.value = {
      left: rect.left,
      top: rect.bottom + 2
    }
  } else if (event) {
    resultPopoverPos.value = {
      left: event.clientX,
      top: event.clientY + 4
    }
  }
}

// 关闭结果弹窗
const closeResultPopover = () => {
  resultPopoverIndex.value = null
}

// 选择结果值并写入 Excel
const setResultValue = async (idx, value) => {
  closeResultPopover()
  if (!selectedFile.value) return

  const rowData = excelAnalysis.value?.valid_rows?.[idx - 1]
  if (!rowData) return

  const excelRow = rowData.row
  if (!excelRow) return
  const dataRowIndex = Number(excelRow) - 2
  if (dataRowIndex < 0) return

  try {
    const response = await fetch('/api/excel/write_cell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: selectedFile.value,
        column_name: 'testResult',
        row_index: dataRowIndex,
        value: value
      })
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || '写入失败')
    }
    // 同步更新本地数据
    rowData.result = value
    rowData.test_result = value
  } catch (error) {
    console.error('切换执行结果失败:', error)
    alert('写入结果失败: ' + (error?.message || '未知错误'))
  }
}

// 显示执行结果
const showExecutionResult = (rowIndex) => {
  const rowData = excelAnalysis.value?.valid_rows?.[rowIndex - 1]
  const meta = rowResultMeta.value[rowIndex]
  if ((!rowScreenshots.value[rowIndex] && !meta?.video_url) || !rowData) {
    return
  }

  const verifyImageName = rowData.verify_image && rowData.verify_image !== 'nan'
    ? rowData.verify_image
    : ''

  if (!verifyImageName) {
    openExecutionResultModal(rowIndex, null)
    return
  }

  const matchedEntry = getLocalVerifyImageEntry(verifyImageName)
  openExecutionResultModal(rowIndex, matchedEntry)
}

// ===== 截图保存功能 =====
// 计算框选矩形在容器中的 CSS 样式
const regionOverlayStyle = computed(() => {
  if (!regionStart.value || !regionEnd.value) return null
  const left = Math.min(regionStart.value.x, regionEnd.value.x)
  const top = Math.min(regionStart.value.y, regionEnd.value.y)
  const width = Math.abs(regionEnd.value.x - regionStart.value.x)
  const height = Math.abs(regionEnd.value.y - regionStart.value.y)
  // 最小选区阈值，避免误触
  if (width < 5 || height < 5) return null
  return {
    left: left + 'px',
    top: top + 'px',
    width: width + 'px',
    height: height + 'px',
  }
})

// 获取图片在容器中的实际显示区域（object-contain 会留白）
const getImageDisplayRect = () => {
  const img = screenshotImgRef.value
  const container = screenshotContainerRef.value
  if (!img || !container) return null

  const containerRect = container.getBoundingClientRect()
  const containerW = containerRect.width
  const containerH = containerRect.height

  const naturalW = img.naturalWidth
  const naturalH = img.naturalHeight
  if (!naturalW || !naturalH) return null

  // object-contain: 等比缩放后居中
  const scale = Math.min(containerW / naturalW, containerH / naturalH)
  const displayW = naturalW * scale
  const displayH = naturalH * scale
  const offsetX = (containerW - displayW) / 2
  const offsetY = (containerH - displayH) / 2

  return { offsetX, offsetY, displayW, displayH, naturalW, naturalH, containerW, containerH }
}

// 切换框选模式
const toggleRegionSelectMode = () => {
  if (isRegionSelectMode.value) {
    // 退出框选模式
    isRegionSelectMode.value = false
    regionStart.value = null
    regionEnd.value = null
  } else {
    isRegionSelectMode.value = true
    regionStart.value = null
    regionEnd.value = null
  }
}

// 鼠标按下：开始框选
const onScreenshotMouseDown = (e) => {
  if (!isRegionSelectMode.value) return
  const container = screenshotContainerRef.value
  if (!container) return
  const rect = container.getBoundingClientRect()
  regionStart.value = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
  regionEnd.value = null
}

// 鼠标移动：更新框选
const onScreenshotMouseMove = (e) => {
  if (!isRegionSelectMode.value || !regionStart.value) return
  const container = screenshotContainerRef.value
  if (!container) return
  const rect = container.getBoundingClientRect()
  regionEnd.value = {
    x: Math.max(0, Math.min(e.clientX - rect.left, rect.width)),
    y: Math.max(0, Math.min(e.clientY - rect.top, rect.height)),
  }
}

// 鼠标释放：完成框选并触发保存
const onScreenshotMouseUp = () => {
  if (!isRegionSelectMode.value || !regionStart.value) return
  if (!regionEnd.value || !regionOverlayStyle.value) {
    // 选区太小，忽略
    return
  }
  // 完成框选 → 裁剪并保存
  cropAndSaveRegion()
  // 退出框选模式
  isRegionSelectMode.value = false
  regionStart.value = null
  regionEnd.value = null
}

// 裁剪并保存选定区域
const cropAndSaveRegion = async () => {
  const img = screenshotImgRef.value
  if (!img) return

  const displayRect = getImageDisplayRect()
  if (!displayRect) return

  const { offsetX, offsetY, displayW, displayH, naturalW, naturalH } = displayRect
  const start = regionStart.value
  const end = regionEnd.value
  if (!start || !end) return

  // 将容器坐标映射到图片原始像素坐标
  const sx = Math.max(0, (Math.min(start.x, end.x) - offsetX) / displayW * naturalW)
  const sy = Math.max(0, (Math.min(start.y, end.y) - offsetY) / displayH * naturalH)
  const sw = Math.abs(end.x - start.x) / displayW * naturalW
  const sh = Math.abs(end.y - start.y) / displayH * naturalH

  if (sw <= 0 || sh <= 0) return

  const canvas = document.createElement('canvas')
  canvas.width = Math.round(sw)
  canvas.height = Math.round(sh)
  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height)

  canvas.toBlob(async (blob) => {
    if (!blob) {
      alert('截图裁剪失败')
      return
    }
    await saveBlobToFile(blob, screenshotSaveFileName.value || 'screenshot_crop')
  }, 'image/png')
}

// 直接保存完整截图
const directSaveScreenshot = async () => {
  const img = screenshotImgRef.value
  if (!img) {
    alert('暂无截图可保存')
    return
  }

  const naturalW = img.naturalWidth
  const naturalH = img.naturalHeight
  if (!naturalW || !naturalH) {
    alert('截图未加载完成')
    return
  }

  const canvas = document.createElement('canvas')
  canvas.width = naturalW
  canvas.height = naturalH
  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, 0, 0)

  canvas.toBlob(async (blob) => {
    if (!blob) {
      alert('截图保存失败')
      return
    }
    await saveBlobToFile(blob, screenshotSaveFileName.value || 'screenshot')
  }, 'image/png')
}

// blob 转 base64
const blobToBase64 = (blob) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = typeof reader.result === 'string' ? reader.result : ''
      resolve(dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl)
    }
    reader.onerror = () => reject(new Error('blob 转 base64 失败'))
    reader.readAsDataURL(blob)
  })
}

// 保存后同步更新校验图缓存
const applyVerifyImageCacheFromBase64 = (fileName, base64) => {
  const key = normalizeVerifyImageName(fileName)
  if (!key || !base64) return
  const entry = localVerifyImageMap.value[key]
  if (!entry) return

  // 从 base64 重建 File 和 Object URL
  const binaryStr = atob(base64)
  const bytes = new Uint8Array(binaryStr.length)
  for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i)
  const newBlob = new Blob([bytes], { type: 'image/png' })
  const newFile = new File([newBlob], key, { type: 'image/png' })

  localVerifyImageMap.value[key] = {
    ...entry,
    file: newFile,
    url: URL.createObjectURL(newFile),
    base64,
  }
  console.log(`[cache] 缓存已更新: key=${key}, base64.length=${base64.length}`)
}

// 核心保存函数：优先使用 showSaveFilePicker，降级为 <a download>
const saveBlobToFile = async (blob, defaultName) => {
  const fileName = defaultName.endsWith('.png') ? defaultName : defaultName + '.png'

  // 先把 blob 转成 base64（blob 被 write 消费后就不可读了）
  const base64 = await blobToBase64(blob)

  // 尝试使用 File System Access API
  if (typeof window.showSaveFilePicker === 'function') {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: fileName,
        types: [{
          description: 'PNG Image',
          accept: { 'image/png': ['.png'] },
        }],
      })
      const writable = await handle.createWritable()
      await writable.write(blob)
      await writable.close()
      applyVerifyImageCacheFromBase64(fileName, base64)
      return
    } catch (err) {
      // 用户取消或 API 不可用，降级
      if (err.name === 'AbortError') return
      console.warn('showSaveFilePicker 失败，降级为直接下载:', err)
    }
  }

  // 降级方案：创建下载链接
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  applyVerifyImageCacheFromBase64(fileName, base64)
}
// ===== 截图保存功能结束 =====

// 预览校验图片
// 把单张/多张校验图预览统一成"列表 + 当前 index"模型。
// imageName 可以是单个文件名或逗号分隔的多张。
const previewVerifyImage = (imageName) => {
  if (!imageName || imageName === 'nan') return

  const candidates = String(imageName)
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => s.split(/[/\\]/).pop())

  if (candidates.length === 0) return

  // 单张：保持老逻辑（包括 fallback 到选文件夹）
  if (candidates.length === 1) {
    if (applyVerifyImagePreview(candidates[0])) return
    triggerVerifyImageFolderPicker({ mode: 'preview', imageName: candidates[0] })
    return
  }

  // 多张：构造列表（包括 missing 项），modal 里有切换按钮
  const previewList = candidates.map((name) => {
    const matched = getLocalVerifyImageEntry(name)
    return {
      name,
      url: matched?.url || '',
      relativePath: matched?.relativePath || matched?.name || name,
      missing: !matched,
    }
  })

  // 默认定位到第一张能找到的图
  const firstFoundIndex = previewList.findIndex((item) => !item.missing)
  const activeIndex = firstFoundIndex >= 0 ? firstFoundIndex : 0

  verifyImagePreviewList.value = previewList
  verifyImagePreviewActiveIndex.value = activeIndex
  applyMultiVerifyPreview(previewList[activeIndex])

  // 如果一张都找不到且用户没选过文件夹，引导一次
  if (firstFoundIndex < 0 && !verifyImageFolderName.value) {
    triggerVerifyImageFolderPicker({ mode: 'preview', imageName: candidates[0] })
    return
  }

  showVerifyImageModal.value = true
}

const applyMultiVerifyPreview = (item) => {
  if (!item) return
  verifyImagePreviewName.value = item.relativePath || item.name
  verifyImageUrl.value = item.url || ''
}

const switchVerifyImagePreview = (index) => {
  const list = verifyImagePreviewList.value
  if (!Array.isArray(list) || index < 0 || index >= list.length) return
  verifyImagePreviewActiveIndex.value = index
  applyMultiVerifyPreview(list[index])
}

const closeVerifyImagePreviewModal = () => {
  showVerifyImageModal.value = false
  verifyImagePreviewList.value = []
  verifyImagePreviewActiveIndex.value = 0
}

// 切换单行选择
const toggleSelectRow = (rowIndex) => {
  const index = selectedRows.value.indexOf(rowIndex)
  if (index > -1) {
    selectedRows.value.splice(index, 1)
  } else {
    selectedRows.value.push(rowIndex)
  }
  selectedRows.value = Array.from(new Set(selectedRows.value)).sort((a, b) => a - b)
}

// 全选/取消全选
const toggleSelectAll = () => {
  const pageIds = pagedRows.value.map(x => x.idx)
  const allSelected = pageIds.every(id => selectedRows.value.includes(id))
  if (allSelected) {
    selectedRows.value = selectedRows.value.filter(id => !pageIds.includes(id))
  } else {
    selectedRows.value = Array.from(new Set([...selectedRows.value, ...pageIds])).sort((a, b) => a - b)
  }
}

// 批量执行选中的行
const executeSelectedRows = async () => {
  if (enableVerification.value && !verifyImageFolderName.value) {
    const action = await showVerifyFolderAlert()
    if (action === 'select') return
  }
  await executeBatchRows(selectedRows.value, t('excelExecution.selectedCasesLabel'))
}

const executeAllRows = async () => {
  if (enableVerification.value && !verifyImageFolderName.value) {
    const action = await showVerifyFolderAlert()
    if (action === 'select') return
  }
  await executeBatchRows(allRowIndexes.value, t('excelExecution.allCasesLabel'))
}

const executeBatchRows = async (rowIndexes, label) => {
  const ordered = Array.from(new Set(rowIndexes)).sort((a, b) => a - b)
  if (ordered.length === 0) {
    return
  }

  const isListLoop = executionMode.value === 'loop_list'
  const isFiniteLoop = loopType.value === 'finite'
  const totalRounds = isListLoop ? (isFiniteLoop ? Math.max(1, Math.floor(loopCount.value || 1)) : Infinity) : 1

  batchExecutionState.active = true
  batchExecutionState.status = 'running'
  batchExecutionState.label = label
  batchExecutionState.total = ordered.length
  batchExecutionState.completed = 0
  batchExecutionState.currentRowIndex = ordered[0]
  batchExecutionState.currentCaseTitle = getBatchExecutionCaseTitle(ordered[0])
  executionResults.value = []
  isBatchExecuting.value = true

  if (isListLoop) {
    executionResults.value.push({
      status: 'info',
      message: isFiniteLoop
        ? (t('excelExecution.listLoopStartFinite', { label, count: ordered.length, rounds: totalRounds }) || `开始列表循环：${label}，${ordered.length} 条用例，共 ${totalRounds} 轮`)
        : (t('excelExecution.listLoopStartInfinite', { label, count: ordered.length }) || `开始列表无限循环：${label}，${ordered.length} 条用例`)
    })
  } else {
    executionResults.value.push({
      status: 'info',
      message: t('excelExecution.alerts.batchStart', { label, count: ordered.length })
    })
  }

  let completedAll = false
  let currentRound = 0
  try {
    while (currentRound < totalRounds) {
      if (!isBatchExecuting.value) break
      currentRound++

      if (isListLoop) {
        const roundMsg = isFiniteLoop
          ? (t('excelExecution.listLoopRoundWithTotal', { current: currentRound, total: totalRounds }) || `第 ${currentRound}/${totalRounds} 轮列表循环...`)
          : (t('excelExecution.listLoopRound', { current: currentRound }) || `第 ${currentRound} 轮列表循环（无限模式）...`)
        executionResults.value.push({ status: 'info', message: roundMsg })
      }

      for (const [offset, rowIndex] of ordered.entries()) {
        if (!isBatchExecuting.value) break

        batchExecutionState.currentRowIndex = rowIndex
        batchExecutionState.currentCaseTitle = getBatchExecutionCaseTitle(rowIndex)
        await runSingleExecutionOnce(rowIndex)
        batchExecutionState.completed = Math.min(offset + 1, ordered.length)
        if (!isBatchExecuting.value) break

        if (offset < ordered.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000))
        }
      }

      if (!isBatchExecuting.value) break

      // 列表循环轮次间隔
      if (isListLoop && currentRound < totalRounds) {
        await new Promise(resolve => setTimeout(resolve, 1000))
      }
    }
    completedAll = isBatchExecuting.value
  } finally {
    isBatchExecuting.value = false
    batchExecutionState.active = false
    batchExecutionState.currentRowIndex = null
    batchExecutionState.currentCaseTitle = ''
    if (completedAll) {
      batchExecutionState.completed = ordered.length
      batchExecutionState.status = 'completed'
      if (isListLoop) {
        executionResults.value.push({
          status: 'success',
          message: t('excelExecution.listLoopComplete', { rounds: currentRound }) || `列表循环完成，共 ${currentRound} 轮`
        })
      } else {
        executionResults.value.push({
          status: 'success',
          message: t('excelExecution.alerts.batchComplete', { label, count: ordered.length })
        })
      }
      if (!isListLoop) {
        await createExcelBatchReport(ordered, label)
      }
    } else {
      batchExecutionState.status = 'stopped'
      if (isListLoop) {
        executionResults.value.push({
          status: 'info',
          message: t('excelExecution.listLoopStopped', { rounds: currentRound }) || `列表循环已停止，已完成 ${currentRound} 轮`
        })
      }
    }
  }
}

// 停止所有执行
const stopAllExecution = () => {
  isBatchExecuting.value = false

  // 为所有正在执行的行设置停止标志
  for (const rowIndex in executingRows.value) {
    if (executingRows.value[rowIndex]) {
      stopExecutionFlags.value[rowIndex] = true
      loopStopFlags.value[rowIndex] = true
      abortExecution(rowIndex)
    }
  }
  
  // 显示停止消息
  executionResults.value.push({
    status: 'info',
    message: t('excelExecution.alerts.allStopped')
  })
  rowExecutionProgress.value = {}
}

// 处理上一页点击
const handlePrevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    selectedRows.value = []
  }
}

// 处理下一页点击
const handleNextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    selectedRows.value = []
  }
}

// 处理跳转到指定页码
const handleJumpPage = () => {
  const page = parseInt(jumpPage.value)
  if (page && page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    selectedRows.value = []
  }
}

const executionStatusLabel = (status) => {
  if (status === 'success') {
    return t('common.success')
  }
  if (status === 'error') {
    return t('common.error')
  }
  return t('common.info')
}

const clearExecutionLogs = () => {
  executionResults.value = []
}

watch(() => executionResults.value.length, async (newLength, oldLength = 0) => {
  if (newLength === 0 || newLength <= oldLength) {
    return
  }

  await nextTick()
  const container = executionLogContainer.value
  if (container) {
    container.scrollTop = container.scrollHeight
  }
})

// 监听页码变化，更新跳转输入框
watch(currentPage, (newPage) => {
  jumpPage.value = newPage
})

watch(
  [selectedDevice, selectedFile, imageCompareBackendConfirmed, rowIndex, filterResult, searchKeyword, currentPage, jumpPage, pageSize, selectedRows, executionResults, rowScreenshots, rowResultMeta, verifyImageFolderName, verifyImageFileCount, matchThreshold, screenshotSource, executionMode, loopType, loopCount],
  () => {
    persistExecutionState()
  },
  { deep: true }
)

// 上传文件
const fileInput = ref(null)

const {
  uploadConfirmVisible,
  requestUpload: requestUploadExcelConfirm,
  confirmUpload,
  cancelUpload,
} = useUploadExcelConfirm()

const handleUploadExcelClick = () => {
  requestUploadExcelConfirm(() => {
    fileInput.value?.click()
  })
}

const uploadFile = async (event) => {
  const file = event.target.files[0]
  if (!file) {
    return
  }
  
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    const response = await fetch('/api/excel/upload', {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      throw new Error(t('excelExecution.alerts.uploadFailed'))
    }
    
    const data = await response.json()
    alert(t('excelExecution.alerts.uploadSuccess', { filename: data.filename }))
    // 刷新文件列表
    await loadExcelFiles()
    // 选择上传的文件
    selectFile(data.filename)
  } catch (error) {
    console.error('上传文件失败:', error)
    alert(t('excelExecution.alerts.uploadFailedWithDetail', { detail: error.message }))
  } finally {
    // 重置文件输入
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

// 删除文件
const executing = ref(false)
const deleteFile = async (file) => {
  if (confirm(t('excelExecution.alerts.deleteConfirm', { file }))) {
    executing.value = true
    try {
      const response = await fetch(`/api/excel/delete?file_name=${encodeURIComponent(file)}`, {
        method: 'DELETE'
      })
      
      if (!response.ok) {
        throw new Error(t('excelExecution.alerts.deleteFailed'))
      }
      
      const data = await response.json()
      alert(data.message || t('excelExecution.alerts.deleteSuccess', { file }))
      
      // 刷新文件列表
      await loadExcelFiles()
      
      // 如果删除的是当前选中的文件，清除选中状态
      if (selectedFile.value === file) {
        selectedFile.value = ''
        excelAnalysis.value = null
        validationResult.value = null
        rowExecutionProgress.value = {}
        showValidationResultModal.value = false
        executionResults.value = []
        rowScreenshots.value = {}
        rowResultMeta.value = {}
        selectedRows.value = []
      }
    } catch (error) {
      console.error('删除文件失败:', error)
      alert(t('excelExecution.alerts.deleteFailedWithDetail', { detail: error.message }))
    } finally {
      executing.value = false
    }
  }
}
</script>

<style scoped>
.excel-edit-modal-body {
  /* 给左右两列同时使用 min-h-0 + overflow-y-auto，保证 grid 子项不会撑破父容器 */
}
.excel-edit-modal-left {
  scrollbar-width: thin;
}
.excel-edit-modal-left::-webkit-scrollbar {
  width: 6px;
}
.excel-edit-modal-left::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.45);
  border-radius: 9999px;
}
.excel-edit-modal-right {
  position: sticky;
  top: 0;
  overflow-y: auto;
  scrollbar-width: thin;
}
.excel-edit-modal-right::-webkit-scrollbar {
  width: 6px;
}
.excel-edit-modal-right::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.45);
  border-radius: 9999px;
}

.excel-device-preview-frame {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  max-height: 60vh;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(15, 23, 42, 0.04);
  overflow: hidden;
  user-select: none;
}
.excel-device-preview-frame--fill {
  /* 不再 flex:1 撑高（会让画面被纵向 letterbox 压扁），改成跟着右栏宽度按 16:9 推算高度。
     这样画面像素能直接贴满 frame，看起来比之前大一截。 */
  flex: 0 0 auto;
  width: 100%;
  aspect-ratio: 16 / 9;
  min-height: 240px;
  /* 保险：极矮屏幕下 frame 不要超过模态可视高度的 70% */
  max-height: 70vh;
}
.excel-device-preview-frame--selectable {
  cursor: crosshair;
  /* 桌面 + 触屏/触控笔环境下都需要禁用浏览器默认手势，否则 pointermove/pointerup 会被浏览器吃掉 */
  touch-action: none;
  user-select: none;
}
.excel-device-preview-frame--selecting {
  cursor: crosshair;
}
.excel-device-preview-image {
  display: block;
  max-width: 100%;
  max-height: 60vh;
  pointer-events: none;
  -webkit-user-drag: none;
}
.excel-device-preview-frame--fill .excel-device-preview-image {
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.excel-device-preview-state {
  font-size: 0.85rem;
  color: #6b7280;
  padding: 24px;
  text-align: center;
}
.excel-device-preview-selection-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.excel-device-preview-selection-box {
  position: absolute;
  border: 2px solid rgba(14, 165, 233, 0.85);
  background: rgba(14, 165, 233, 0.18);
  box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.18);
}
.form-input-sm {
  padding: 6px 10px;
  font-size: 0.85rem;
  border-radius: 12px;
}
.form-select-sm {
  padding: 6px 10px;
  font-size: 0.85rem;
  border-radius: 12px;
}

@media (max-width: 1023px) {
  .excel-edit-modal-left {
    overflow: visible;
  }
  .excel-edit-modal-right {
    position: static;
    overflow: visible;
  }
}

.excel-execution-page {
  flex: 1;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 18px 20px;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.excel-execution-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.9) rgba(226, 232, 240, 0.72);
}

.excel-file-panel,
.excel-section-card,
.excel-table-shell,
.excel-note-card {
  margin-bottom: 16px;
}

.excel-top-grid {
  display: grid;
  gap: 16px;
  align-items: stretch;
}

.excel-top-grid > * {
  height: 100%;
}

.excel-top-side-stack {
  display: grid;
  gap: 16px;
  min-height: 100%;
}

.excel-top-compact-card {
  padding: 14px 16px;
}

.excel-top-compact-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.excel-top-compact-title {
  margin: 6px 0 0;
  color: #111827;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.35;
  word-break: break-all;
}

.excel-top-compact-meta {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 0.82rem;
  line-height: 1.5;
}

.excel-file-item {
  padding: 0.75rem 0.875rem;
}

.excel-file-list {
  max-height: 240px;
  overflow-y: auto;
  padding-right: 4px;
}

.excel-section-card {
  padding: 16px;
  border-radius: 22px;
}

.excel-top-model-panel {
  min-height: 100%;
}

.excel-report-panel {
  min-height: 0;
}

.excel-report-list {
  display: grid;
  gap: 12px;
  max-height: 360px;
  overflow-y: auto;
  padding-right: 4px;
}

.excel-report-row {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.85);
  background: rgba(255, 255, 255, 0.82);
  padding: 14px;
}

.excel-report-main {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.excel-report-main strong {
  color: #111827;
  font-size: 0.98rem;
}

.excel-report-main p {
  margin: 0;
  color: #6b7280;
  font-size: 0.78rem;
  letter-spacing: 0.04em;
}

.excel-report-summary {
  display: grid;
  gap: 10px;
}

.excel-report-overview-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 0.82rem;
  font-weight: 600;
}

.excel-report-overview-pill-pass {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.excel-report-overview-pill-fail {
  background: rgba(248, 113, 113, 0.12);
  color: #b91c1c;
}

.excel-report-overview-pill-warning {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}

.excel-report-overview-pill-muted {
  background: rgba(148, 163, 184, 0.12);
  color: #475569;
}

.excel-report-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #64748b;
  font-size: 0.78rem;
}

.excel-report-metrics span {
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.96);
  border: 1px solid rgba(226, 232, 240, 0.92);
  padding: 5px 10px;
}

.excel-report-actions {
  display: flex;
  justify-content: flex-end;
}

.excel-log-list {
  margin-top: 12px;
  max-height: 17rem;
  padding: 0.75rem;
  border-radius: 18px;
}

.excel-log-row {
  gap: 0.625rem;
  padding: 0.625rem 0.75rem;
  border-radius: 14px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
}

.excel-step-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.excel-step-sequence-collapsed {
  position: relative;
  display: flex;
  max-width: 100%;
  flex-wrap: nowrap;
  gap: 0.5rem;
  overflow: hidden;
  padding-right: 2.5rem;
}

.excel-step-sequence-collapsed::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 2.75rem;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.98) 68%);
  pointer-events: none;
}

.excel-step-sequence-collapsed .excel-step-command {
  flex-shrink: 0;
}

.excel-step-command {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.7rem;
  border: 1px solid rgba(226, 232, 240, 0.92);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.96);
  color: #475569;
  line-height: 1.35;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.92);
  transition: transform 0.18s ease, border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease;
}

.excel-step-command-key {
  font-weight: 600;
  color: #0f172a;
}

.excel-step-command-meta {
  font-size: 0.72rem;
  color: #64748b;
  white-space: nowrap;
}

.excel-step-command-progress {
  border-radius: 999px;
  background: rgba(191, 219, 254, 0.95);
  padding: 0.15rem 0.45rem;
  font-size: 0.68rem;
  font-weight: 700;
  line-height: 1.1;
  color: #1d4ed8;
}

.excel-step-command-active {
  border-color: rgba(59, 130, 246, 0.34);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.18), rgba(14, 165, 233, 0.1));
  color: #0f172a;
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.08), 0 10px 24px rgba(59, 130, 246, 0.16);
  animation: excel-step-command-pulse 1.2s ease-in-out infinite;
}

.excel-step-command-active .excel-step-command-key {
  color: #1d4ed8;
}

.excel-step-command-active .excel-step-command-meta {
  color: #1e40af;
}

.excel-step-command-active .excel-step-command-progress {
  background: #2563eb;
  color: #fff;
}

.excel-row-actions {
  gap: 0.5rem;
}

@keyframes excel-step-command-pulse {
  0% {
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.08), 0 10px 24px rgba(59, 130, 246, 0.12);
  }

  50% {
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.16), 0 14px 30px rgba(59, 130, 246, 0.2);
  }

  100% {
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.08), 0 10px 24px rgba(59, 130, 246, 0.12);
  }
}

.excel-results-table th,
.excel-results-table td {
  padding: 0.65rem 0.75rem;
}

.excel-results-table .excel-row-actions .btn {
  min-width: 78px;
}

.excel-execution-page .btn {
  padding: 0.5rem 0.8rem;
  font-size: 0.875rem;
  line-height: 1.2;
}

.excel-execution-page .btn.btn-sm,
.excel-execution-page .btn-sm {
  padding: 0.375rem 0.7rem;
  font-size: 0.8125rem;
}

.excel-execution-page .form-input,
.excel-execution-page .form-select {
  min-height: 2.25rem;
  padding: 0.45rem 0.65rem;
  font-size: 0.875rem;
}

.excel-execution-page .form-label {
  margin-bottom: 0.25rem;
  font-size: 0.8125rem;
}

.excel-execution-scroll::-webkit-scrollbar {
  width: 10px;
}

.excel-execution-scroll::-webkit-scrollbar-track {
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.72);
}

.excel-execution-scroll::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.9);
  background-clip: padding-box;
}

@media (max-width: 768px) {
  .excel-execution-page {
    padding: 14px;
  }

  .excel-section-card {
    padding: 14px;
    border-radius: 18px;
  }

  .excel-results-table th,
  .excel-results-table td {
    padding: 0.55rem 0.6rem;
  }

  .excel-top-compact-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .excel-report-row {
    grid-template-columns: 1fr;
  }

  .excel-report-actions {
    justify-content: flex-start;
  }
}

@media (min-width: 1200px) {
  .excel-top-grid {
    grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  }
}

/* 置顶操作栏 */
.excel-sticky-bar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 16px;
  padding: 12px 16px;
  margin-bottom: 16px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

/* 校验文件夹提醒弹窗 */
.excel-vfa-card {
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  padding: 32px;
  width: 380px;
  max-width: 90vw;
  text-align: center;
}
.excel-vfa-icon {
  font-size: 40px;
  margin-bottom: 12px;
}
.excel-vfa-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
  line-height: 1.5;
}
.excel-vfa-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 24px;
  line-height: 1.6;
}
.excel-vfa-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.excel-vfa-actions .btn {
  flex: 1;
  max-width: 160px;
}

.vfa-fade-enter-active,
.vfa-fade-leave-active {
  transition: opacity 0.2s ease;
}
.vfa-fade-enter-active .excel-vfa-card,
.vfa-fade-leave-active .excel-vfa-card {
  transition: transform 0.2s ease;
}
.vfa-fade-enter-from,
.vfa-fade-leave-to {
  opacity: 0;
}
.vfa-fade-enter-from .excel-vfa-card {
  transform: scale(0.95);
}
.vfa-fade-leave-to .excel-vfa-card {
  transform: scale(0.95);
}
</style>
