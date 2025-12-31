# Frontend Refactoring - Phase 6: Dwellers View - Room Assignment Visibility

## Objective
Enhance the dwellers list view to show room assignments, making it easier to manage workforce allocation and understand where each dweller is working.

## Completed Tasks ✅

### 1. Fetch Room Data
**File**: `frontend/src/views/DwellersView.vue`

**Changes**:
- ✅ Import and use `useRoomStore`
- ✅ Fetch rooms on component mount
- ✅ Ensure room data is available before rendering dweller list

**Code**:
```typescript
import { useRoomStore } from '@/stores/room'

const roomStore = useRoomStore()

onMounted(async () => {
  await fetchDwellers()
  // Fetch rooms to show room assignments
  if (authStore.isAuthenticated && vaultId.value) {
    await roomStore.fetchRooms(vaultId.value, authStore.token as string)
  }
})
```

### 2. Room Lookup Helper
**Implementation**:
- ✅ Created computed function to get room by ID
- ✅ Handles null/undefined room_id gracefully
- ✅ Returns null for unassigned dwellers

**Code**:
```typescript
const getRoomForDweller = computed(() => (roomId: string | null | undefined) => {
  if (!roomId) return null
  return roomStore.rooms.find(room => room.id === roomId)
})
```

### 3. Room Assignment Badge
**Visual Design**:
- ✅ **Assigned dwellers**: Blue badge with room icon and name
- ✅ **Unassigned dwellers**: Gray badge with "Unassigned" label
- ✅ Terminal-style glow effects matching game aesthetic
- ✅ Responsive hover states

**Badge Types**:

**Assigned Badge:**
- Background: `bg-blue-900`
- Text: `text-blue-300`
- Border: `border-blue-500`
- Icon: `mdi:office-building`
- Interactive: Clickable, navigates to vault view
- Tooltip: Shows full room name

**Unassigned Badge:**
- Background: `bg-gray-700`
- Text: `text-gray-400`
- Border: `border-gray-600`
- Icon: `mdi:account-off`
- Static: Not clickable

### 4. Badge Placement
**Location**:
- Displayed inline with dweller name and status badge
- Positioned after the status badge
- Uses flex-wrap to handle long names gracefully

**Template Structure**:
```vue
<div class="flex items-center gap-2 mb-2 flex-wrap">
  <h3>{{ dweller.first_name }} {{ dweller.last_name }}</h3>
  <DwellerStatusBadge :status="dweller.status" />

  <!-- Room Badge -->
  <template v-if="getRoomForDweller(dweller.room_id)">
    <UTooltip :text="`Assigned to ${getRoomForDweller(dweller.room_id)?.name}`">
      <div class="room-badge" @click.stop="router.push(`/vault/${vaultId}`)">
        <Icon icon="mdi:office-building" />
        <span>{{ getRoomForDweller(dweller.room_id)?.name }}</span>
      </div>
    </UTooltip>
  </template>
  <template v-else>
    <div class="room-badge">
      <Icon icon="mdi:account-off" />
      <span>Unassigned</span>
    </div>
  </template>
</div>
```

### 5. Navigation Enhancement
**Click Behavior**:
- ✅ Clicking assigned room badge navigates to vault view
- ✅ Uses `@click.stop` to prevent expanding dweller details
- ✅ Navigates to: `/vault/{vaultId}`

**Future Enhancement**: Could navigate directly to specific room on vault grid

### 6. Styling
**CSS Implementation**:
```css
.room-badge {
  font-family: monospace;
  text-shadow: 0 0 4px rgba(59, 130, 246, 0.5);
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.3);
}

.room-badge:hover {
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.6);
}
```

**Features**:
- Terminal-style monospace font
- Blue glow effect for assigned rooms
- Enhanced glow on hover for clickable badges
- Consistent with game's terminal aesthetic

## Technical Implementation

### Component Integration
```
DwellersView
├── useRoomStore (fetch rooms)
├── getRoomForDweller (computed helper)
└── Room Badge (inline component)
    ├── Assigned: Blue, clickable, tooltip
    └── Unassigned: Gray, static, icon
```

### Data Flow
1. Component mounts
2. Fetch dwellers by vault
3. Fetch rooms for vault
4. For each dweller:
   - Check if `dweller.room_id` exists
   - Lookup room from `roomStore.rooms`
   - Display appropriate badge

### Performance Considerations
- Room lookup uses computed function for reactivity
- Single rooms fetch on mount (not per dweller)
- Efficient find operation (O(n) per dweller, where n = room count)

## User Experience Improvements

### Before:
- ❌ No visibility into dweller assignments
- ❌ Couldn't tell which dwellers were working
- ❌ Had to navigate to vault view to check assignments
- ❌ No quick way to identify unassigned dwellers

### After:
- ✅ Immediate visibility of room assignments
- ✅ Clear "Unassigned" indicator for idle dwellers
- ✅ Clickable badges for quick navigation
- ✅ Tooltip with full room name on hover
- ✅ Visual distinction between assigned/unassigned
- ✅ Maintains terminal aesthetic

## Accessibility

- **Keyboard Navigation**: Clickable badges are focusable
- **Visual Feedback**: Hover states for interactivity
- **Color Not Sole Indicator**: Icons + text labels
- **Tooltips**: Provide additional context

## Files Modified

1. **Updated**:
   - `frontend/src/views/DwellersView.vue`
     - Added `useRoomStore` import
     - Added room fetching on mount
     - Added `getRoomForDweller` computed helper
     - Added room badge inline component
     - Added CSS styling for badges

2. **Documented**:
   - `docs/FRONTEND_REFACTORING_PHASE6.md` - This file

## Success Criteria

- ✅ Room data fetched and available
- ✅ Room assignments displayed for all dwellers
- ✅ Unassigned dwellers clearly indicated
- ✅ Badges are visually distinct and clickable
- ✅ Navigation to vault view works correctly
- ✅ Maintains terminal aesthetic
- ✅ No console errors
- ✅ Responsive and accessible

## Future Enhancements

**Potential Improvements**:
1. Navigate directly to specific room instead of vault view
2. Show room type icon (power, food, water) instead of generic building icon
3. Add room capacity indicator (e.g., "2/4 dwellers")
4. Filter dwellers by room assignment
5. Highlight rooms with issues (low resources, no workers)
6. Drag-and-drop assignment from dwellers view
7. Show room efficiency/productivity metrics

**Technical Debt**:
- Consider caching room lookups if performance becomes an issue
- Could extract room badge into separate component if reused elsewhere

## Summary

Phase 6 successfully enhanced the dwellers view with clear visibility into room assignments. Dwellers now display their assigned room with a clickable badge, or show an "Unassigned" indicator if idle. This improves workforce management by providing immediate visibility into dweller allocation without needing to navigate to the vault view.

The implementation maintains the Fallout terminal aesthetic with blue glow effects, monospace fonts, and proper hover states. Navigation is smooth and intuitive - clicking a room badge takes you directly to the vault view to see the actual room.

This feature addresses a key UX gap by answering the question "Where is this dweller working?" at a glance, making vault management more efficient and enjoyable.
