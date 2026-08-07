<template>
  <div
    v-if="visible"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
    @click.self="$emit('cancel')"
  >
    <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
      <div class="flex items-start gap-3 mb-4">
        <div class="flex-shrink-0 mt-1">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
          </svg>
        </div>
        <div class="flex-1">
          <h3 class="text-base font-semibold text-slate-900 mb-2">
            {{ $t('common.uploadExcelConfirmTitle') }}
          </h3>
          <p class="text-sm text-slate-600 leading-relaxed whitespace-pre-line">
            {{ $t('common.uploadExcelConfirmBody') }}
          </p>
        </div>
      </div>

      <div class="flex justify-end gap-2">
        <button class="btn btn-secondary btn-sm" @click="$emit('cancel')">
          {{ $t('common.uploadExcelConfirmCancel') }}
        </button>
        <button class="btn btn-primary btn-sm" @click="onConfirm">
          {{ $t('common.uploadExcelConfirmContinue') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, required: true },
})

const emit = defineEmits(['confirm', 'cancel'])

const onConfirm = () => {
  emit('confirm')
}
</script>
