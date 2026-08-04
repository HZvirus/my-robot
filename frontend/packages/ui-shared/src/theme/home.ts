import type { ThemeTokens } from './types'

export const homeTheme: ThemeTokens = {
  name: 'home',
  displayName: '家庭 7寸 竖屏',
  orientation: 'portrait',
  colors: {
    primary: '#F59E3C',
    primaryDark: '#D97E1C',
    bg: '#FFF7EE',
    surface: '#FFFFFF',
    bubbleUser: '#F59E3C',
    bubbleAssistant: '#FFFFFF',
    text: '#3A2A1A',
    textMuted: '#8A7563',
    action: '#4CAF86',
    danger: '#E5484D',
    success: '#4CAF86',
  },
  font: {
    base: '20px',
    large: '26px',
    title: '28px',
  },
  radius: {
    sm: '12px',
    md: '20px',
    lg: '28px',
  },
  layout: {
    maxWidth: '768px',
    padding: '20px',
    bubbleMaxWidth: '82%',
  },
}
