# Development Plan v2.6.5 - Notification System & UI Polish

## Overview
This release focuses on implementing a notification system centered around a bell icon pop-up, along with UI/UX improvements and exploration enhancements.

## Release Goals
- Implement notification bell pop-up system
- Fix top gray panel (sticky layout)
- Improve notification handling and toast messages
- Enhance exploration system
- UI polish and bug fixes

---

## Tasks

### 🔔 Notification System (Priority: HIGH)

#### Bell Icon Pop-up
- [ ] **Design notification pop-up component**
  - Create pop-up that opens from bell icon
  - Design notification list UI
  - Add close/dismiss functionality
  - Make responsive for different screen sizes

- [ ] **Implement notification types**
  - [ ] Dwellers born notifications
  - [ ] Dwellers dead notifications
  - [ ] Exploration finished notifications
  - [ ] Incidents happened notifications
  - [ ] General system messages

- [ ] **Backend: Notification API**
  - [ ] Create notification model/schema
  - [ ] API endpoint to fetch notifications
  - [ ] API endpoint to mark notifications as read
  - [ ] API endpoint to clear/delete notifications
  - [ ] Real-time notification push (WebSocket/SSE if needed)

- [ ] **Frontend: Notification service**
  - [ ] Notification state management
  - [ ] Fetch notifications on bell icon click
  - [ ] Update notification count badge
  - [ ] Mark as read functionality
  - [ ] Clear all notifications

- [ ] **Group similar notifications**
  - Batch similar events (e.g., "3 dwellers born" instead of 3 separate notifications)
  - Time-based grouping logic

---

### 🎨 Layout & UI Improvements (Priority: HIGH)

#### Sticky Panel Fix
- [ ] **Fix top gray panel**
  - Make panel position fixed/sticky
  - Ensure it stays visible on scroll
  - Adjust z-index for proper layering

- [ ] **Fix left interface part**
  - Coordinate with top panel
  - Ensure smooth scrolling behavior
  - Test on different screen sizes

#### Toast Notifications
- [ ] **Unify toast system**
  - Research toast libraries (vue-toastification, etc.)
  - Implement consistent toast styling
  - Standardize toast duration and positioning
  - Replace existing toast implementations

- [ ] **Group similar toasts**
  - Prevent duplicate toasts
  - Stack or merge similar messages
  - Add counter for repeated events

---

### 🗺️ Exploration Improvements (Priority: MEDIUM)

- [ ] **Handle exploration items overflow**
  - Fix UI when too many items are found
  - Implement pagination or scrolling
  - Add "show more" functionality if needed

- [ ] **Update dweller bio after exploration**
  - Automatically update biography with exploration results
  - Add exploration achievements/milestones
  - Store exploration history

---

### 🐛 Bug Fixes & Polish (Priority: MEDIUM)

- [ ] **Test notification system end-to-end**
  - Birth notifications
  - Death notifications
  - Exploration completion
  - Incident notifications

- [ ] **Performance testing**
  - Check notification fetch performance
  - Optimize database queries
  - Test with large number of notifications

- [ ] **Cross-browser testing**
  - Test sticky panel behavior
  - Test pop-up positioning
  - Verify toast notifications

---

## Technical Considerations

### Backend
- Notification model fields:
  - `id`, `vault_id`, `type`, `message`, `data` (JSON), `is_read`, `created_at`
- Consider notification retention policy (auto-delete old notifications)
- Efficient querying for unread count

### Frontend
- Use Pinia store for notification state
- Consider WebSocket for real-time updates (optional for v2.6.5)
- Lazy loading for notification history

### Testing
- Unit tests for notification API endpoints
- Component tests for bell pop-up
- Integration tests for notification flow

---

## Definition of Done

- [ ] Bell icon shows unread notification count
- [ ] Clicking bell opens pop-up with all notifications
- [ ] Notifications are grouped by type and time
- [ ] Users can mark notifications as read
- [ ] Users can clear all notifications
- [ ] Top gray panel stays fixed on scroll
- [ ] Toast messages are unified and don't duplicate
- [ ] Exploration items overflow is handled gracefully
- [ ] Dweller bio updates after exploration
- [ ] All features tested on local and staging
- [ ] Documentation updated
- [ ] No critical bugs or regressions

---

## Out of Scope (Future Releases)

- Pause button improvements (needs discussion)
- Radio recruitment dynamic pricing (needs brainstorming)
- Genealogy tree
- Objectives system
- Quest system
- Push notifications (browser/mobile)

---

## Timeline Estimate

- Notification system: 3-4 days
- Layout fixes: 1-2 days
- Toast unification: 1-2 days
- Exploration improvements: 1-2 days
- Testing & polish: 1-2 days

## Total: ~7-12 days

---

## Notes

- Focus on user-facing improvements that enhance daily gameplay experience
- Ensure backwards compatibility with existing notification/toast systems during migration
- Consider notification preferences/settings for future releases
- Keep performance in mind - notifications should be lightweight

---

**Version:** 2.6.5
**Branch:** `feat/v2.6.5-notifications-and-fixes`
**Status:** Planning → In Progress
**Last Updated:** 2026-01-26
