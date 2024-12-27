import type { DwellerShort } from '@/types/dweller.types';
import type { Vault } from '@/types/vault.types';
import type { Room } from '@/types/room.types';
import type { GridPosition } from '@/types/grid.types';

export function createRoomManager(
  getVault: () => Vault | null,
  unassignDweller: (dwellerId: string) => boolean
) {
  function startDigging(x: number, y: number) {
    const vault = getVault();
    if (!vault) return false;

    const cell = vault.grid[y][x];
    if (cell.status !== 'empty') return false;

    cell.status = 'digging';
    cell.progress = 0;
    return true;
  }

  function completeDigging(x: number, y: number) {
    const vault = getVault();
    if (!vault) return false;

    const cell = vault.grid[y][x];
    if (cell.status !== 'digging') return false;

    cell.status = 'ready';
    cell.progress = undefined;
    return true;
  }

  function startConstruction(x: number, y: number) {
    const vault = getVault();
    if (!vault) return false;

    const cell = vault.grid[y][x];
    if (cell.status !== 'ready') return false;

    cell.status = 'constructing';
    cell.progress = 0;
    return true;
  }

  function addRoom(category: Room['category'], position: GridPosition) {
    const vault = getVault();
    if (!vault) return false;

    const cell = vault.grid[position.y][position.x];
    if (cell.status !== 'constructing') return false;

    const newRoomId = Date.now().toString();

    // Create new single room if no merging possible
    const newRoom: Room = {
      id: newRoomId,
      category,
      tier: 1,
      capacity: 1,
      dwellers: [],
      coordinate_x: position.x,
      coordinate_y: position.y,
      size: 1
    };

    vault.grid[position.y][position.x].status = 'occupied';
    vault.grid[position.y][position.x].roomId = newRoom.id;
    vault.grid[position.y][position.x].progress = undefined;

    vault.rooms.push(newRoom);
    return true;
  }

  function destroyRoom(roomId: string) {
    const vault = getVault();
    if (!vault) return false;

    const roomIndex = vault.rooms.findIndex((r: Room) => r.id === roomId);
    if (roomIndex === -1) return false;

    const room = vault.rooms[roomIndex];

    // Unassign all dwellers from the room
    room.dwellers.forEach((dweller: DwellerShort) => {
      unassignDweller(dweller.id);
    });

    // Update all cells the room occupied
    for (let i = 0; i < room.size; i++) {
      const cell = vault.grid[room.coordinate_y][room.coordinate_x + i];
      cell.status = 'ready';
      cell.roomId = null;
    }

    // Remove the room
    vault.rooms.splice(roomIndex, 1);
    return true;
  }

  function getRoomById(roomId: string) {
    const vault = getVault();
    if (!vault) return null;
    return vault.rooms.find((r: Room) => r.id === roomId) || null;
  }

  return {
    startDigging,
    completeDigging,
    startConstruction,
    addRoom,
    getRoomById,
    destroyRoom
  };
}
