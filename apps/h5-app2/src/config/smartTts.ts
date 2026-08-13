/**
 * 讯飞超拟人语音合成（WebSocket 直连）凭据。
 *
 * 浏览器在 WebSocket 握手时无法附加 `x-api-key` 头，因此直连必须使用
 * HMAC-SHA256 签名 URL（鉴权方式二）。此处凭据用于在浏览器端直接签名，
 * 已配置时不再请求后端 `/api/smart-tts/ws-url`。
 *
 * 注意：凭据会暴露给页面访问者，仅用于内网/演示环境。
 */
export const IFLYTEK_SMART_TTS = {
  appId: '52e4a842',
  apiKey: '0b93f27fe80262b9d6c1f17f38f18f27',
  apiSecret: 'ZTJiMDZmNGI0M2JkYWY2Nzk3NjhmYzFh',
  baseUrl: 'wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6'
}
