# Changelog API Empty Response Bug

## Description
The changelog frontend service is receiving an empty array `[]` from the backend API, despite the backend endpoint working correctly when called directly via curl.

## Current Behavior
- **Backend API** (`curl http://localhost:8000/api/v1/system/changelog`) ✅ Works correctly
  - Returns JSON array with version 2.7.5 entries
- Proper structure with `version`, `date`, `date_display`, `changes` fields

- **Frontend Service** (`apiGet('/api/v1/system/changelog')`) ❌ Returns empty array `[]`
  - `axios.get()` call completes without throwing errors
- `console.log()` shows correct URL being called
- Returns `[]` instead of expected data array

## Root Cause Analysis
The issue appears to be in the frontend `apiGet()` function or axios configuration:
1. **Network/CORS Issue** - Frontend axios calls failing silently
2. **Base URL Configuration** - Incorrect base URL in frontend
3. **Axios Interceptors** - Error handling masking actual API responses
4. **Async/Await Issue** - Promise resolution not working correctly

## Test Steps to Reproduce
1. Open ChangelogModal in frontend
2. Check browser console for logs:
   - `Fetching changelog from: /api/v1/system/changelog`
   - `Making axios GET request...`
   - `changelog length: 0` (❌ should be > 0)
   - No error messages in console

## Expected Behavior
- Frontend should receive same changelog data as direct curl call
- Modal should display version 2.7.5 entries
- `hasNewVersions` should be `true` when comparing with older versions

## Current Status
- ✅ Backend endpoint working correctly
- ✅ Frontend service logic correct
- ❌ API call returning empty data
- ❌ Modal shows "All caught up!" instead of new versions

## Next Steps
1. Debug axios configuration and base URLs
2. Add error handling for silent API failures
3. Create unit tests for changelog service
4. Verify network connectivity and CORS settings
5. Add integration tests for modal component

## Files Involved
- `frontend/src/modules/profile/services/changelogService.ts`
- `frontend/src/modules/profile/components/ChangelogModal.vue`
- `frontend/src/core/utils/api.ts`
- `backend/app/api/v1/endpoints/system.py`
