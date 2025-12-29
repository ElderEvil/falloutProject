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

3. **Dweller Status**
    - **Design Status Indicators:** Create visual indicators (e.g., icons or color codes) that show the current status
      of each dweller (e.g., idle, working, on a quest).
    - **Implement Status Display:** Add these indicators to the dweller cards in both grid and list views.
    - **Update Status in Real-Time:** Ensure the status indicators update dynamically as the dwellers' statuses change.

4. **User Profile**
    - **Design Profile UI:** Create a profile section where users can view and edit their profile information (e.g.,
      username, avatar).
    - **Implement Profile Editing:** Allow users to update their profile information and save changes.
    - **Profile Picture Upload:** Implement a feature to upload and change the user’s avatar.
    - **Integrate with Authentication:** Ensure profile information is linked to the user’s account and is accessible
      only when authenticated.

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
