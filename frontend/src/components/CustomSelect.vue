<template>
  <div
    ref="containerRef"
    class="custom-select"
    :class="{
      'custom-select--open': isOpen,
      'custom-select--disabled': disabled,
    }"
  >
    <button
      type="button"
      class="custom-select__trigger"
      :class="{ 'custom-select__trigger--placeholder': !selectedLabel }"
      :disabled="disabled"
      @click="toggleDropdown"
      @keydown.enter.prevent="toggleDropdown"
      @keydown.space.prevent="toggleDropdown"
      @keydown.escape="closeDropdown"
      @keydown.arrow-down.prevent="openAndFocusFirst"
      @keydown.arrow-up.prevent="openAndFocusLast"
    >
      <span class="custom-select__value">{{ selectedLabel || placeholder }}</span>
      <span class="custom-select__arrow">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
    </button>

    <Transition name="custom-select">
      <div
        v-if="isOpen"
        class="custom-select__dropdown"
        role="listbox"
        :aria-activedescendant="highlightedIndex >= 0 ? `option-${highlightedIndex}` : undefined"
      >
        <div
          v-for="(option, index) in normalizedOptions"
          :key="option.value"
          :id="`option-${index}`"
          class="custom-select__option"
          :class="{
            'custom-select__option--selected': option.value === modelValue,
            'custom-select__option--highlighted': index === highlightedIndex,
            'custom-select__option--disabled': option.disabled,
          }"
          role="option"
          :aria-selected="option.value === modelValue"
          @mousedown.prevent
          @click="handleOptionClick(option, $event)"
          @mouseenter="highlightedIndex = index"
        >
          <span class="custom-select__option-label">{{ option.label }}</span>
          <span v-if="option.value === modelValue" class="custom-select__option-check">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 7L6 10L11 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Number, Boolean, null],
    default: null,
  },
  options: {
    type: Array,
    default: () => [],
    validator: (value) => value.every((opt) => typeof opt === 'object' && 'value' in opt && 'label' in opt),
  },
  placeholder: {
    type: String,
    default: '',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'change'])

const containerRef = ref(null)
const isOpen = ref(false)
const highlightedIndex = ref(-1)
const justSelected = ref(false)

const normalizedOptions = computed(() => props.options)

const selectedLabel = computed(() => {
  const selected = normalizedOptions.value.find((opt) => opt.value === props.modelValue)
  return selected ? selected.label : ''
})

const toggleDropdown = () => {
  if (props.disabled) return
  if (justSelected.value) {
    justSelected.value = false
    return
  }
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    const selectedIndex = normalizedOptions.value.findIndex((opt) => opt.value === props.modelValue)
    highlightedIndex.value = selectedIndex >= 0 ? selectedIndex : 0
  }
}

const openAndFocusFirst = () => {
  if (!isOpen.value) {
    isOpen.value = true
    highlightedIndex.value = 0
  } else {
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, normalizedOptions.value.length - 1)
  }
}

const openAndFocusLast = () => {
  if (!isOpen.value) {
    isOpen.value = true
    highlightedIndex.value = normalizedOptions.value.length - 1
  } else {
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
  }
}

const closeDropdown = () => {
  isOpen.value = false
  highlightedIndex.value = -1
}

const selectOption = (option) => {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
  closeDropdown()
}

const handleOptionClick = (option, event) => {
  event.stopPropagation()
  justSelected.value = true
  selectOption(option)
  setTimeout(() => {
    justSelected.value = false
  }, 100)
}

const handleKeydown = (event) => {
  if (!isOpen.value) return

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      highlightedIndex.value = Math.min(highlightedIndex.value + 1, normalizedOptions.value.length - 1)
      break
    case 'ArrowUp':
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
      break
    case 'Enter':
    case ' ':
      event.preventDefault()
      if (highlightedIndex.value >= 0) {
        selectOption(normalizedOptions.value[highlightedIndex.value])
      }
      break
    case 'Escape':
      closeDropdown()
      break
    case 'Home':
      event.preventDefault()
      highlightedIndex.value = 0
      break
    case 'End':
      event.preventDefault()
      highlightedIndex.value = normalizedOptions.value.length - 1
      break
  }
}

const handleClickOutside = (event) => {
  if (containerRef.value && !containerRef.value.contains(event.target)) {
    closeDropdown()
  }
}

watch(isOpen, (value) => {
  if (value) {
    document.addEventListener('keydown', handleKeydown)
  } else {
    document.removeEventListener('keydown', handleKeydown)
  }
})

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.custom-select {
  position: relative;
  width: 100%;
}

.custom-select__trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.75rem 1rem;
  padding-right: 2.5rem;
  border-radius: 1.2rem;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.96), 0 10px 26px rgba(15, 23, 42, 0.05);
  transition: border-color 180ms ease, box-shadow 180ms ease;
  cursor: pointer;
  text-align: left;
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: #1d1d1f;
}

.custom-select__trigger:focus {
  outline: none;
  border-color: rgba(0, 113, 227, 0.38);
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12), 0 20px 40px rgba(15, 23, 42, 0.08);
}

.custom-select__trigger--placeholder {
  color: #9ca3af;
}

.custom-select--disabled .custom-select__trigger {
  opacity: 0.6;
  cursor: not-allowed;
  background-color: rgba(241, 245, 249, 0.8);
}

.custom-select__arrow {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: #6b7280;
  transition: transform 180ms ease;
  pointer-events: none;
}

.custom-select--open .custom-select__arrow {
  transform: translateY(-50%) rotate(180deg);
}

.custom-select__dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 50;
  max-height: 250px;
  overflow-y: auto;
  border-radius: 1rem;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: white;
  box-shadow: 0 10px 38px -10px rgba(22, 23, 24, 0.35), 0 10px 20px -15px rgba(22, 23, 24, 0.2);
  padding: 0.25rem;
}

.custom-select__option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.625rem 0.75rem;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: background-color 100ms ease;
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: #1d1d1f;
}

.custom-select__option:hover {
  background-color: rgba(0, 113, 227, 0.06);
}

.custom-select__option--highlighted {
  background-color: rgba(0, 113, 227, 0.1);
}

.custom-select__option--selected {
  color: #0071e3;
  font-weight: 500;
}

.custom-select__option--selected.custom-select__option--highlighted {
  background-color: rgba(0, 113, 227, 0.14);
}

.custom-select__option--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.custom-select__option-check {
  color: #0071e3;
  flex-shrink: 0;
}

/* Transition animations */
.custom-select-enter-active {
  transition: opacity 150ms ease, transform 150ms ease;
}

.custom-select-leave-active {
  transition: opacity 100ms ease, transform 100ms ease;
}

.custom-select-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}

.custom-select-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
