export function truncate(text: string, max = 20): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}
