export interface ThemeTokens {
  name: string
  displayName: string
  orientation: 'landscape' | 'portrait'
  colors: {
    primary: string
    primaryDark: string
    bg: string
    surface: string
    bubbleUser: string
    bubbleAssistant: string
    text: string
    textMuted: string
    action: string
    danger: string
    success: string
  }
  font: {
    base: string
    large: string
    title: string
  }
  radius: {
    sm: string
    md: string
    lg: string
  }
  layout: {
    maxWidth: string
    padding: string
    bubbleMaxWidth: string
  }
}
