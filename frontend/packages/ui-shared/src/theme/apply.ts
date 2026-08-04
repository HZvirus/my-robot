import type { ThemeTokens } from './theme/types'

export function applyTheme(theme: ThemeTokens): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  const c = theme.colors
  const map: Record<string, string> = {
    '--color-primary': c.primary,
    '--color-primary-dark': c.primaryDark,
    '--color-bg': c.bg,
    '--color-surface': c.surface,
    '--color-bubble-user': c.bubbleUser,
    '--color-text': c.text,
    '--color-text-muted': c.textMuted,
    '--color-action': c.action,
    '--color-danger': c.danger,
    '--color-success': c.success,
    '--font-base': theme.font.base,
    '--font-large': theme.font.large,
    '--font-title': theme.font.title,
    '--radius-sm': theme.radius.sm,
    '--radius-md': theme.radius.md,
    '--radius-lg': theme.radius.lg,
    '--layout-max-width': theme.layout.maxWidth,
    '--layout-padding': theme.layout.padding,
    '--bubble-max-width': theme.layout.bubbleMaxWidth,
  }
  for (const [k, v] of Object.entries(map)) {
    root.style.setProperty(k, v)
  }
  root.setAttribute('data-scene', theme.name)
  root.setAttribute('data-orientation', theme.orientation)
}
