<template>
  <Teleport to="body">
    <div
      v-if="dialogState.visible"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-4"
      @click.self="dialogCancel()"
    >
      <div class="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <div class="flex items-start gap-3">
          <div
            v-if="dialogState.type !== 'alert' || dialogState.title"
            class="flex-shrink-0 mt-0.5"
          >
            <svg
              v-if="dialogState.type !== 'prompt'"
              xmlns="http://www.w3.org/2000/svg"
              class="h-6 w-6 text-blue-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <svg
              v-else
              xmlns="http://www.w3.org/2000/svg"
              class="h-6 w-6 text-blue-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
          </div>

          <div class="min-w-0 flex-1">
            <h3
              v-if="dialogState.title"
              class="mb-2 text-base font-semibold text-slate-900"
            >
              {{ dialogState.title }}
            </h3>
            <p
              v-if="dialogState.message"
              class="whitespace-pre-line text-sm leading-relaxed text-slate-600"
            >
              {{ dialogState.message }}
            </p>

            <input
              v-if="dialogState.type === 'prompt'"
              v-model="dialogState.inputValue"
              type="text"
              class="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              :placeholder="dialogState.placeholder"
              @keydown.enter="dialogOk()"
              @keydown.esc="dialogCancel()"
            >
          </div>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button
            v-if="dialogState.cancelText"
            class="btn btn-secondary btn-sm"
            @click="dialogCancel()"
          >
            {{ dialogState.cancelText }}
          </button>
          <button class="btn btn-primary btn-sm" @click="dialogOk()">
            {{ dialogState.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { dialogState, dialogOk, dialogCancel } from '../stores/dialogStore'
</script>
