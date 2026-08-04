import { onMounted, onUnmounted, ref } from 'vue'

export function useResponsive(breakpoint = 768) {
  const isPortrait = ref(false)
  const width = ref(0)

  const update = () => {
    width.value = window.innerWidth
    isPortrait.value = window.innerHeight > window.innerWidth
  }

  onMounted(() => {
    update()
    window.addEventListener('resize', update)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', update)
  })

  return {
    width,
    isPortrait,
    isSmall: () => width.value < breakpoint,
  }
}
