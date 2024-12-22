import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Quest, Objective } from '@/types/quest'

export const useQuestStore = defineStore('quest', () => {
  const quests = ref<Quest[]>([
    {
      id: 1,
      title: 'VAULT EXPANSION',
      description: 'Expand your vault to accommodate more dwellers',
      status: 'active',
      objectives: [
        {
          id: 1,
          title: 'Build 3 new rooms',
          description: 'Construct any type of room',
          completed: false,
          progress: 0,
          total: 3
        },
        {
          id: 2,
          title: 'Assign 6 dwellers',
          description: 'Assign dwellers to new rooms',
          completed: false,
          progress: 0,
          total: 6
        }
      ],
      reward: {
        bottlecaps: 500
      }
    },
    {
      id: 2,
      title: 'RESOURCE MANAGEMENT',
      description: 'Maintain optimal resource levels',
      status: 'active',
      objectives: [
        {
          id: 3,
          title: 'Reach 90% power',
          description: 'Maintain power level above 90%',
          completed: false
        },
        {
          id: 4,
          title: 'Reach 80% water',
          description: 'Maintain water level above 80%',
          completed: false
        }
      ],
      reward: {
        bottlecaps: 300,
        items: ['Rare Weapon Box']
      }
    }
  ])

  const objectives = ref<Objective[]>([
    {
      id: 1,
      title: 'TRAIN 3 DWELLERS',
      description: 'Increase any SPECIAL stat',
      completed: false,
      progress: 0,
      total: 3
    },
    {
      id: 2,
      title: 'COLLECT 1000 CAPS',
      description: 'Earn bottlecaps from rooms',
      completed: false,
      progress: 0,
      total: 1000
    },
    {
      id: 3,
      title: 'REACH 100% HAPPINESS',
      description: 'Keep all dwellers happy',
      completed: false
    }
  ])

  return {
    quests,
    objectives
  }
})
