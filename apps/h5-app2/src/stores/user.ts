import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const nickname = ref('')

  function setNickname(name: string) {
    nickname.value = name
  }

  return { nickname, setNickname }
})
