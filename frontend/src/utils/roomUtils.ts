import type { Room } from '@/types/room.types';

export interface RoomConfig {
  category: Room['category'];
  label: string;
  description: string;
  requiredDwellers: number;
  cost: number;
  size: number;
}

export const isVaultDoor = (room: Room) => room.category === 'misc.';
