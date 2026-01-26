# Room Images Feature Documentation

**Version:** 2.5.0
**Date:** January 26, 2026
**Status:** ✅ Completed

## Overview

The Room Images feature adds visual representation to all rooms in the vault, displaying authentic Fallout Shelter sprites for every room type, tier, and size combination. Images render both in the vault overview grid and in the room detail modal.

## Features

### 1. Room Sprite Rendering

**Vault Overview Grid:**
- Rooms display their corresponding sprite images as backgrounds
- Images scale to fill the entire room cell using `object-fit: cover`
- Room info overlay (name, category, tier) appears at top with semi-transparent background
- Dweller avatars display at the bottom
- All elements properly layered with z-index for clear visibility

**Room Detail Modal:**
- Room preview section shows the room sprite
- Image maintains aspect ratio using `object-fit: contain`
- Maximum height of 300px to prevent oversized displays
- Dweller slots overlay at the bottom showing assigned dwellers

### 2. Image Assets

**Total Assets:** 220+ PNGs

**Coverage:**
- All room types (25+ different room types)
- All tiers (1-3 for most rooms)
- All size variants (1-cell, 2-cell, 3-cell segments)
- Special themed variants (Holiday, faction themes for certain rooms)

**File Naming Convention:**
```text
FOS {RoomType} {Tier}-{Segment}.png

Examples:
- FOS Power 1-1.png (Power Generator, Tier 1, 1 segment)
- FOS Living Quarters 2-2.png (Living Quarters, Tier 2, 2 segments)
- FOS Armory 3-3.png (Armory, Tier 3, 3 segments)
```

**Special Cases:**
- Vault Door: `Vault Door Adv.png`
- Elevator: `FOS Elevator icon.png`
- Workshops: `FOS {Workshop} {Tier}.png` (no segment number)

### 3. Intelligent Fallback System

When a specific tier-segment combination doesn't exist, the system automatically falls back:

1. **Try exact tier-segment**: e.g., Tier 2, Segment 1
2. **Try higher segments at same tier**: e.g., Tier 2, Segment 2 → Tier 2, Segment 3
3. **Try tier 1 with same segment**: e.g., Tier 1, Segment 1
4. **Try tier 1 with higher segments**: e.g., Tier 1, Segment 2 → Tier 1, Segment 3
5. **Return original path**: Allow frontend to handle missing image gracefully

**Example:**
```python
# Living Quarters Tier 1, Size 3 (segment 1) doesn't exist
# Falls back to: FOS Living Quarters 1-2.png (segment 2)
```

### 4. Room Capacity Enforcement

**Capacity Calculation:**
```text
Capacity = (Room Size / 3) * 2 dwellers

Examples:
- 3-cell room (1 segment) = 2 dwellers
- 6-cell room (2 segments) = 4 dwellers
- 9-cell room (3 segments) = 6 dwellers
```

**Validation:**
- Prevents assigning dwellers to full rooms
- Shows error message: "{RoomName} is full ({current}/{capacity})"
- Allows reordering dwellers within the same room
- Real-time capacity check on drag-and-drop

### 5. UI Improvements

**Compact Room Info Overlay:**
- Room name: 0.75em font size
- Category: 0.65em font size
- Tier: 0.6em font size
- Padding: 2px 6px (reduced from 6px 10px)
- Background: rgba(0, 0, 0, 0.85) with backdrop blur
- Positioned absolutely at top of room

**Layout:**
```text
┌──────────────────────────┐
│ [Room Info Overlay]      │ ← Top (z-index: 2)
│                          │
│   [Room Image]           │ ← Background (z-index: 0)
│                          │
│ [Dweller Avatars]        │ ← Bottom (z-index: 3)
└──────────────────────────┘
```

## Technical Implementation

### Backend

### 1. Database Migration
```python
# Migration: fc75e738a303_add_room_image_urls
# Populates image_url for all existing rooms
# Uses get_room_image_url() with fallback logic
```

**2. Image URL Generation**
```python
# backend/app/utils/room_assets.py
def get_room_image_url(room_name: str, tier: int = 1, size: int = 3) -> str | None:
    # Returns: /static/room_images/FOS {RoomType} {Tier}-{Segment}.png
```

**3. Automatic Population**
- New rooms: `image_url` set during `crud.room.build()`
- Room upgrades: `image_url` updated during `crud.room.upgrade()`
- Static data: `image_url` set when loading room templates

### 4. Static File Serving
```python
# backend/main.py
app.mount("/static", StaticFiles(directory="app/static"), name="static")
```

### Frontend

**1. Vite Proxy Configuration**
```typescript
// frontend/vite.config.ts
server: {
  proxy: {
    '/static': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    }
  }
}
```

**2. Room Grid Component**
```vue
<!-- frontend/src/modules/rooms/components/RoomGrid.vue -->
<img
  v-if="getRoomImageUrl(room)"
  :src="getRoomImageUrl(room)"
  :alt="room.name"
  class="room-background-image"
/>
```

**3. Room Detail Modal**
```vue
<!-- frontend/src/modules/rooms/components/RoomDetailModal.vue -->
<img
  v-if="props.room?.image_url"
  :src="props.room.image_url"
  :alt="props.room.name"
  class="room-image"
/>
```

**4. Image Loading Handlers**
- `@load`: Console log success
- `@error`: Console log failure with room name and URL
- Graceful fallback: Display placeholder if image fails to load

## Files Changed

### Backend
- `backend/app/alembic/versions/2026_01_26_1313-fc75e738a303_add_room_image_urls.py` (new)
- `backend/app/crud/room.py` (modified)
- `backend/app/utils/room_assets.py` (modified)
- `backend/app/utils/static_data.py` (modified)
- `backend/app/static/room_images/*.png` (220+ new files)

### Frontend
- `frontend/src/modules/rooms/components/RoomGrid.vue` (modified)
- `frontend/src/modules/rooms/components/RoomDetailModal.vue` (modified)
- `frontend/vite.config.ts` (modified)
- `frontend/public/test-image.html` (new - for testing)

## Usage

### For Developers

**Testing Image Loading:**
1. Navigate to `http://localhost:5173/test-image.html`
2. Verify images load through both direct backend URL and Vite proxy
3. Check console for success/failure messages

**Adding New Room Images:**
1. Place image in `backend/app/static/room_images/`
2. Follow naming convention: `FOS {RoomType} {Tier}-{Segment}.png`
3. Update `ROOM_NAME_TO_ASSET_KEY` mapping if needed
4. No database changes required - URLs generated automatically

**Debugging:**
```javascript
// Check console for room image logs:
// "🖼️ Room Image: {RoomName}"
// "✅ Final URL: /static/room_images/..."
```

### For Players

**In Vault Overview:**
- Room sprites display automatically for all built rooms
- Hover over rooms to see details
- Click rooms to open detail modal with larger preview

**Room Capacity:**
- Drag dwellers to rooms as usual
- Error message appears if room is full
- Check room detail modal to see current capacity usage

## Testing

**Manual Testing Checklist:**
- [x] Room images display in vault grid
- [x] Room images display in detail modal
- [x] Images load through Vite proxy
- [x] Fallback system works for missing images
- [x] Capacity enforcement prevents over-assignment
- [x] Error messages display correctly
- [x] Room info overlay is readable
- [x] Dweller avatars display at bottom
- [x] All z-index layers work correctly
- [x] Image URLs generated on room build
- [x] Image URLs updated on room upgrade

**Test Rooms:**
- ✅ Power Generator (all tiers)
- ✅ Living Quarters (with fallback to segment 2)
- ✅ Vault Door (special case)
- ✅ Elevator (special case)
- ✅ Storage Room
- ✅ Radio Studio
- ✅ Armory

## Known Issues

**None** - All features working as expected

## Future Enhancements

1. **Animated Sprites**: Add animated versions for active rooms
2. **Themed Variants**: Allow players to select holiday/faction themes
3. **Custom Room Skins**: Premium feature for custom room appearances
4. **Room Preview in Build Menu**: Show sprite before building
5. **Sprite Optimization**: Compress images for faster loading
6. **WebP Format**: Convert to WebP for better compression

## References

- Original sprites: Fallout Shelter game assets
- Image count: 220+ PNG files
- Total size: ~40MB (after removing large files)
- Supported formats: PNG
- Resolution: Variable (optimized for web display)

## Migration Guide

**For Existing Deployments:**

1. **Run Migration:**
```bash
cd backend
uv run alembic upgrade head
```

2. **Verify Images Populated:**
```bash
uv run python check_rooms.py
# Should show image_url for all rooms
```

3. **Restart Frontend:**
```bash
cd frontend
pnpm run dev
```

4. **Test:**
- Open vault overview
- Verify room images display
- Check browser console for any errors

## Support

For issues or questions:
- Check console logs for image loading errors
- Verify `/static` proxy is configured in Vite
- Ensure migration has run successfully
- Check `backend/app/static/room_images/` contains images

---

**Status:** ✅ Feature complete and deployed
**Impact:** High - Significantly improves visual experience
**Stability:** Stable - No known issues
