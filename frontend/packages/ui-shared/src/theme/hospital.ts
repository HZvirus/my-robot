import type { ThemeTokens } from './types'

export const hospitalTheme: ThemeTokens = {
  name: 'hospital',
  displayName: '医院 24寸 横屏',
  orientation: 'landscape',
  colors: {
    primary: '#1E63D6',
    primaryDark: '#16489C',
    bg: '#F2F6FC',
    surface: '#FFFFFF',
    bubbleUser: '#1E63D6',
    bubbleAssistant: '#FFFFFF',
    text: '#1A2433',
    textMuted: '#6B7785',
    action: '#0E9F6E',
    danger: '#E5484D',
    success: '#0E9F6E',
  },
  font: {
    base: '18px',
    large: '22px',
    title: '30px',
  },
  radius: {
    sm: '8px',
    md: '14px',
    lg: '20px',
  },
  layout: {
    maxWidth: '1600px',
    padding: '24px',
    bubbleMaxWidth: '70%',
  },
}
