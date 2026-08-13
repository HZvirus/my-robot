import { streamSmartTtsWs } from '@/api/smartTtsWs'
import { setSmartTtsTransport, smartTtsApi } from './useSmartTts'

/**
 * 快速版播报入口：与 useSmartTts 共享同一套播放引擎与设置，
 * 但流式合成传输层切换为 WebSocket 直连讯飞超拟人接口，
 * 跳过服务端 SSE 转发，进一步降低合成首响延迟。
 *
 * 注意：传输层为模块级单例，导航离开本页面后请调用
 * useSmartTts()（SSE 版）恢复默认传输层。
 */
export function useSmartTtsWs() {
  setSmartTtsTransport(streamSmartTtsWs)
  return smartTtsApi
}
