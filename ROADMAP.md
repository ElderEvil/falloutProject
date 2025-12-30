Here’s a task list to implement the features you outlined:

### **Task List**

1. **Dweller View Grid/List Switcher**
    - **Design UI Toggle:** Create a toggle button in the Dwellers section to switch between grid and list views.
    - **Implement Grid View:** Layout dwellers in a grid format with larger thumbnails and essential stats visible.
    - **Implement List View:** Layout dwellers in a list format, showing more details in a compact vertical layout.
    - **Persist View Preference:** Store the user’s preference (grid/list) in local storage or Vuex so that it persists
      across sessions.

2. **Dweller Filter/Sort**
    - **Design Filter/Sort UI:** Add dropdowns or buttons to filter dwellers by status (e.g., idle, working, on a quest)
      and sort by attributes (e.g., level, name, stats).
    - **Implement Filtering Logic:** Write methods to filter the displayed dwellers based on selected criteria.
    - **Implement Sorting Logic:** Write methods to sort the dwellers in ascending/descending order based on selected
      attributes.
    - **Integrate with View:** Ensure filtering and sorting are responsive to changes and interact smoothly with the
      grid/list view.

3. **Dweller Status** ✅ **(Backend Complete - Frontend Pending)**
    - ✅ **Backend Implementation Complete:**
        - Added `DwellerStatusEnum` with statuses: IDLE, WORKING, EXPLORING, TRAINING, RESTING, DEAD
        - Implemented status field in Dweller model with auto-updates on room assignment
        - Created filtering/sorting/search endpoints for dwellers by status
        - Added comprehensive test coverage (API + CRUD tests)
        - Integrated with admin panel
    - **Frontend Tasks:**
        - **Design Status Indicators:** Create visual indicators (e.g., icons or color codes) for each status
        - **Implement Status Display:** Add indicators to dweller cards in both grid and list views
        - **Update Status in Real-Time:** Ensure indicators update dynamically as statuses change
    - ✅ **Enhancement: Room-Type-Specific Status** **(Complete)**
        - **Context-Aware Status Logic:** Dwellers now receive appropriate status based on room type
        - **Production Rooms:** Dwellers get status WORKING (e.g., Power Plant, Diner, Water Treatment)
        - **Training Rooms:** Dwellers get status TRAINING (e.g., Gym, Armory, Classroom)
        - **Other Room Types:** Default to WORKING (CAPACITY, CRAFTING, MISC, QUESTS, THEME)
        - **Implementation:**
            - Updated `backend/app/crud/dweller.py:move_to_room()` to check room category (RoomTypeEnum)
            - Added logic: `room.category == RoomTypeEnum.TRAINING` → TRAINING status
            - Added logic: `room.category == RoomTypeEnum.PRODUCTION` → WORKING status
            - All other room types default to WORKING status
        - **Testing:** Added comprehensive tests:
            - `test_dweller_status_production_room` - Verifies WORKING status for production rooms
            - `test_dweller_status_training_room` - Verifies TRAINING status for training rooms
            - All existing tests continue to pass

4. **User Profile** ✅ **(Backend Complete - Frontend Pending)**
    - ✅ **Backend Implementation Complete:**
        - Created UserProfile model with bio, avatar_url, preferences (JSONB), and statistics tracking
        - Implemented profile CRUD operations with increment statistics methods
        - Created profile API endpoints (GET/PUT /api/v1/users/me/profile)
        - Auto-creates profile on user registration
        - Added comprehensive test coverage (API + CRUD tests)
        - Integrated with admin panel
    - **Frontend Tasks:**
        - **Design Profile UI:** Create a profile section where users can view and edit their profile information
        - **Implement Profile Editing:** Allow users to update bio, avatar_url, and preferences
        - **Profile Picture Upload:** Implement avatar upload feature
        - **Display Statistics:** Show read-only statistics (total_dwellers_created, total_caps_earned, etc.)
        - **Integrate with Authentication:** Ensure profile information is linked to authenticated user

5. **Vault Inventory**
    - **Design Inventory UI:** Create a categorized inventory view within the vault, showing all resources, items, and
      equipment.
    - **Implement Item Categorization:** Organize items into categories like weapons, outfits, and consumables.
    - **Display Item Details:** Allow users to click on an item to view detailed stats and possible actions (e.g.,
      equip, use, sell).
    - **Integrate with Vault View:** Ensure the inventory is easily accessible from the vault overview or through a
      dedicated button.

6. **User Flow Update - Vault is Main Tab, Button to Move to Vault List**
    - **Set Vault as Main Tab:** Update the navigation so that the vault overview is the default/main tab when users log
      in.
    - **Design Vault List Button:** Add a button or link within the vault overview that allows users to move to the
      vault list (to switch between different vaults).
    - **Update User Flow:** Ensure that the new flow is intuitive and the transition between vaults is smooth.

7. **User Refresh Token**
    - **Implement Token Refresh:** Set up an automatic token refresh mechanism to keep the user authenticated without
      requiring frequent logins.
    - **Backend Integration:** Ensure the backend provides a refresh token endpoint that the frontend can call
      periodically or when needed.
    - **Handle Token Expiration:** Implement logic to handle cases where the refresh token fails (e.g., prompt user to
      log in again).
    - **Security Considerations:** Make sure the refresh token is stored securely (e.g., in HttpOnly cookies) and that
      the refresh process is safe from CSRF attacks.

8. **Infrastructure & DevOps**
    - **Configuration Management:**
        - Split configuration into environment-specific files (dev/staging/prod)
        - Separate secrets management from application config
        - Consider using config hierarchy (base + environment overrides)
    - **CI/CD Pipeline:**
        - Set up automated testing on pull requests
        - Add test coverage requirements (minimum threshold)
        - Backend: pytest with coverage reports
        - Frontend: Vitest coverage tracking
        - Automated deployment to staging/production
    - **Frontend Performance & Quality:**
        - Integrate Lighthouse CI for performance audits
        - Set up automated accessibility checks
        - Monitor bundle size and performance metrics
        - Add performance budgets (Core Web Vitals)
    - **Monitoring & Observability:**
        - Health check endpoints for all services
        - Application performance monitoring (APM)
        - Error tracking and logging
        - Resource usage alerts

This task list should help you organize the development process and track the progress of each feature in your Vue.js 3
web game.
