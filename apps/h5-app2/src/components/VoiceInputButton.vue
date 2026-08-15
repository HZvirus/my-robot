<!--
  组件说明：语音输入按钮（VoiceInputButton）
  ------------------------------------------------------------
  功能：
  - 点击开始/停止语音识别（基于浏览器原生 Web Speech API）。
  - 实时把识别到的文本通过 update:modelValue 事件同步给父组件（v-model）。
  - 识别结束后通过 commit 事件提交最终文本，供父组件发送消息。
  - 收音中按钮显示呼吸光圈动画；识别出错时显示红色错误气泡（3 秒后消失）。
  边界：
  - 浏览器不支持 SpeechRecognition 时按钮禁用。
  - 单次收音最长 MAX_SPEECH_MS，超时自动停止并提交。
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";

// ---------------------------------------------------------------------------
// Web Speech API（语音识别）最小类型声明：
// TS 5.4 的 DOM lib 未包含 SpeechRecognition 接口，此处按标准行为自行声明；
// 结果相关类型也一并本地声明，避免依赖 DOM 全局类型。
// ---------------------------------------------------------------------------

/** 识别结果中的单条候选文本（maxAlternatives=1 时只用第 0 条） */
interface RecognitionAlternative {
  transcript: string;
}

/** 单次识别结果：isFinal 表示已确认（不再变化），未确认的为中间结果 */
interface RecognitionResult {
  isFinal: boolean;
  readonly length: number;
  item(index: number): RecognitionAlternative;
  [index: number]: RecognitionAlternative;
}

/** 本次语音的识别结果集合（结果数组） */
interface RecognitionResultList {
  readonly length: number;
  item(index: number): RecognitionResult;
  [index: number]: RecognitionResult;
}

/** onresult 回调的事件对象 */
interface RecognitionResultEvent {
  /** 本次新增结果的起始下标，用于只处理新到的部分 */
  resultIndex: number;
  /** 到目前为止的全部识别结果 */
  results: RecognitionResultList;
}

/** onerror 回调的事件对象 */
interface RecognitionErrorEvent {
  /** 错误码，如 no-speech / audio-capture / not-allowed / network / aborted */
  error: string;
}

/** 我们实际用到的 SpeechRecognition 实例最小接口（屏蔽各浏览器前缀差异） */
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (() => void) | null;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

/** 构造函数类型：new 出来的实例即为 SpeechRecognitionLike */
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

/** 单次语音输入的时长上限，超时自动停止并提交已识别内容 */
const MAX_SPEECH_MS = 15000;

/** 常见错误码到提示文案的映射 */
const ERROR_MESSAGES: Record<string, string> = {
  "no-speech": "未检测到语音，请重试",
  "audio-capture": "未检测到麦克风",
  "not-allowed": "麦克风权限被拒绝，请允许后重试",
  "service-not-allowed": "语音识别服务不可用",
  network: "网络异常，请重试",
  aborted: "已取消",
};

/** Props 定义：v-model 绑定值、识别语言、是否禁用 */
const props = withDefaults(
  defineProps<{
    /** v-model：当前已识别到的文本 */
    modelValue?: string;
    /** 语音识别语言，默认简体中文 */
    lang?: string;
    /** 是否禁用按钮 */
    disabled?: boolean;
  }>(),
  {
    modelValue: "",
    lang: "zh-CN",
    disabled: false,
  },
);

/** Emits 定义：update:modelValue 同步文本，commit 在识别结束时提交最终文本 */
const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "commit", text: string): void;
}>();

/** 当前浏览器是否支持 Web Speech API 语音识别 */
const supported = (() => {
  if (typeof window === "undefined") return false;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return (
    typeof w.SpeechRecognition === "function" ||
    typeof w.webkitSpeechRecognition === "function"
  );
})();

/** 是否正在收音 */
const listening = ref(false);
/** 语音识别错误提示（空字符串表示无错误） */
const errorMsg = ref("");

/** 当前语音识别实例 */
let recognition: SpeechRecognitionLike | null = null;
/** 本次发音已确认（isFinal）的文本 */
let finalText = "";
/** 本次发音尚未确认的中间文本 */
let interimText = "";
/** 超时自动停止的定时器 */
let timerId: number | undefined;
/** 错误提示自动消失的定时器 */
let errorTimer: number | undefined;

function getCtor(): SpeechRecognitionCtor | null {
  // 返回当前浏览器可用的 SpeechRecognition 构造函数（优先标准实现，回退 webkit 前缀）
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** 显示错误气泡，3 秒后自动消失 */
function showError(message: string) {
  errorMsg.value = message;
  clearTimeout(errorTimer); // 重复报错时重置计时，避免提前消失
  errorTimer = window.setTimeout(() => {
    errorMsg.value = "";
  }, 3000);
}

/**
 * 处理识别结果事件：
 * 把 isFinal（已确认）部分累积到 finalText，
 * 把中间结果拼到 interimText，并实时把合并文本通过 v-model 同步给父组件。
 */
function handleResult(event: RecognitionResultEvent) {
  let final = finalText;
  let interim = "";
  // 只处理本次新到的结果（resultIndex 之后的部分）
  for (let i = event.resultIndex; i < event.results.length; i++) {
    const result = event.results[i];
    if (result.isFinal) final += result[0].transcript;
    else interim += result[0].transcript;
  }
  finalText = final;
  interimText = interim;
  const text = `${final} ${interim}`.trim();
  if (text) emit("update:modelValue", text);
}

/** 处理识别错误：aborted（主动取消）不提示，其余错误映射为中文文案 */
function handleError(event: RecognitionErrorEvent) {
  if (event.error === "aborted") return;
  showError(ERROR_MESSAGES[event.error] ?? "语音识别失败，请重试");
}

/** 识别结束（自然结束或手动 stop）后：清理状态并提交最终文本 */
function handleEnd(rec: SpeechRecognitionLike) {
  // 防止过期实例的 onend 干扰当前状态（stopListening(false) 时 recognition 已置空）
  if (recognition !== rec) return;
  recognition = null;
  clearTimeout(timerId);
  timerId = undefined;
  listening.value = false;
  const text = `${finalText} ${interimText}`.trim();
  finalText = "";
  interimText = "";
  if (text) {
    emit("update:modelValue", text);
    emit("commit", text);
  }
}

/** 开始语音识别 */
function startListening() {
  const Ctor = getCtor();
  if (!Ctor) return;
  stopListening(false); // 防抖：若正在识别，先强制中止上一次
  const rec = new Ctor();
  rec.lang = props.lang;
  rec.continuous = true; // 单段识别：一句话结束后自动结束
  rec.interimResults = true; // 打开中间结果，实现实时回显
  rec.maxAlternatives = 1; // 只需要最优候选
  rec.onstart = () => {
    listening.value = true;
  };
  rec.onresult = handleResult;
  rec.onerror = handleError;
  rec.onend = () => {
    console.log("recognition onend", rec);
    handleEnd(rec);
  };
  recognition = rec;
  finalText = "";
  interimText = "";
  errorMsg.value = "";
  clearTimeout(errorTimer);
  clearTimeout(timerId);
  // 超时保护：单次收音最多 MAX_SPEECH_MS，到点自动 stop（触发 onend → 提交文本）
  timerId = window.setTimeout(() => {
    if (listening.value) rec.stop();
  }, MAX_SPEECH_MS);
  try {
    rec.start();
  } catch {
    // 例如无权限时某些浏览器 start 会同步抛错，需回滚状态并提示
    recognition = null;
    listening.value = false;
    showError("语音输入启动失败，请重试");
  }
}

/**
 * 停止语音输入。
 * - commit=true：正常结束，onend 时提交已识别文本（供点击按钮停止使用）；
 * - commit=false：立即中止且不提交（供父组件发送/清空时调用）。
 */
function stopListening(commit = true) {
  const rec = recognition;
  if (!rec) return;
  clearTimeout(timerId);
  timerId = undefined;
  if (commit) {
    rec.stop(); // 优雅停止，等待 onend 回调统一收尾
    return;
  }
  // 不提交模式：直接置空状态并 abort，避免 onend 再提交文本
  recognition = null;
  listening.value = false;
  finalText = "";
  interimText = "";
  try {
    rec.abort();
  } catch {
    // already stopped
  }
}

/** 点击按钮：正在收听则停止并提交，否则开始收听 */
function toggle() {
  if (props.disabled || !supported) return;
  if (listening.value) stopListening();
  else startListening();
}

/** 按钮悬浮提示文案 */
const btnTitle = computed(() => {
  if (!supported) return "当前浏览器不支持语音输入";
  return listening.value ? "点击停止并发送" : "点击开始说话";
});

/** 无障碍标签（屏幕阅读器） */
const btnAriaLabel = computed(() => {
  if (!supported) return "语音输入（当前浏览器不支持）";
  return listening.value ? "停止语音输入" : "开始语音输入";
});

/** 暴露给父组件的方法：立即中止语音输入且不提交文本 */
defineExpose({ stop: () => stopListening(false) });

/** 组件卸载前清理：清除定时器并强制中止识别，避免内存泄漏 / 过期回调 */
onBeforeUnmount(() => {
  clearTimeout(timerId);
  clearTimeout(errorTimer);
  stopListening(false);
});
</script>

<template>
  <span class="voice-input">
    <!-- 麦克风按钮：收音中显示绿色呼吸光圈，出错时边框变红 -->
    <button
      type="button"
      class="mic-btn"
      :class="{ listening, error: !!errorMsg }"
      :disabled="disabled || !supported"
      :aria-pressed="listening"
      :aria-label="btnAriaLabel"
      :title="btnTitle"
      @click="toggle"
    >
      <!-- 内置的麦克风 SVG 图标（feather icons 风格） -->
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
    </button>
    <!-- 错误提示气泡：仅在有错误信息时显示，role="status" 供读屏播报 -->
    <span v-if="errorMsg" class="mic-error" role="status">
      {{ errorMsg }}
    </span>
  </span>
</template>

<style scoped>
/* 外层容器：相对定位，用于定位错误气泡 */
.voice-input {
  position: relative;
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

/* 麦克风按钮：圆形、白色背景、居中显示图标 */
.mic-btn {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #606266;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: all 0.2s;
}

/* 禁用态：半透明并禁用指针 */
.mic-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 收音中：绿色渐变背景 + 白色图标 */
.mic-btn.listening {
  border-color: #67c23a;
  background: linear-gradient(135deg, #67c23a, #3f9e4d);
  color: #fff;
}

/* 收音中的呼吸光圈：两个 ::before / ::after 伪元素依次扩散形成涟漪 */
.mic-btn.listening::before,
.mic-btn.listening::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid rgba(103, 194, 58, 0.5);
  animation: mic-ping 1.4s ease-out infinite;
}

/* 第二个光圈延迟半个周期，让动画交替出现 */
.mic-btn.listening::after {
  animation-delay: 0.7s;
}

/* 出错态：边框与图标变红 */
.mic-btn.error {
  border-color: #f56c6c;
  color: #f56c6c;
}

/* 错误气泡：悬浮在按钮正上方偏右 */
.mic-error {
  position: absolute;
  bottom: calc(100% + 8px);
  right: 0;
  background: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 8px;
  white-space: nowrap;
  z-index: 10;
}

/* 光圈扩散动画：由内向外放大并淡出 */
@keyframes mic-ping {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }

  100% {
    transform: scale(1.6);
    opacity: 0;
  }
}
</style>
