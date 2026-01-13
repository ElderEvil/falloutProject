# Frontend Authentication Fixes

## Issues Identified and Fixed

### 1. **Circular Dependency Problem** ❌ → ✅

**Problem:**
- `axios.ts` imported and called `useAuthStore()` in the interceptor
- `auth.ts` imported the axios instance
- This created a circular dependency that could cause initialization issues and unpredictable behavior

**Solution:**
- Removed the `useAuthStore()` import from `axios.ts`
- Created helper functions to directly access localStorage without going through the Pinia store
- This breaks the circular dependency chain

### 2. **Duplicate Authorization Headers** ❌ → ✅

**Problem:**
- The auth store was manually adding `Authorization: Bearer ${token}` headers to every API call
- The axios interceptor was ALSO automatically adding the same header
- This caused redundancy and potential conflicts

**Solution:**
- Removed all manual `Authorization` header assignments from:
  - `auth.ts` store (in `fetchUser()` and `logout()` methods)
  - `authService.ts` (in `logout()` and `getCurrentUser()` methods)
- Now the axios request interceptor is the ONLY place that adds the Authorization header
- This ensures consistency across all API calls

### 3. **Inconsistent API Paths** ❌ → ✅

**Problem:**
- Auth store used: `/api/v1/auth/login`, `/api/v1/users/me`, etc.
- AuthService used: `/auth/login`, `/users/me`, etc. (missing `/api/v1` prefix)
- This would cause 404 errors when using authService

**Solution:**
- Standardized all API paths to include the `/api/v1` prefix:
  - `/auth/login` → `/api/v1/auth/login`
  - `/users/open` → `/api/v1/users/open`
  - `/auth/refresh` → `/api/v1/auth/refresh`
  - `/auth/logout` → `/api/v1/auth/logout`
  - `/users/me` → `/api/v1/users/me`

### 4. **Incorrect Token Refresh Implementation** ❌ → ✅

**Problem:**
- When refreshing token in the interceptor, it was setting:
  ```typescript
  axios.defaults.headers.common['Authorization'] = 'Bearer ' + authStore.token
  ```
- This modifies the global axios defaults instead of the specific `apiClient` instance
- Could cause issues with multiple axios instances

**Solution:**
- Token refresh now properly updates:
  - The token in localStorage directly
  - The current request's Authorization header
  - Returns the retried request with the new token
- On refresh failure, properly clears all auth data and redirects to login

### 5. **Token Refresh Race Conditions** ❌ → ✅

**Problem:**
- The axios interceptor imported the auth store which could trigger token refresh
- When token expired, multiple simultaneous requests could all try to refresh at once
- This could cause multiple refresh token calls

**Solution:**
- Simplified token refresh to happen only in the axios interceptor
- Uses the `_retry` flag to prevent infinite retry loops
- Single source of truth for token refresh logic

## Code Changes Summary

### `plugins/axios.ts`
- ✅ Removed `useAuthStore()` import (breaks circular dependency)
- ✅ Added helper functions to access localStorage directly:
  - `getStoredToken()`
  - `getStoredRefreshToken()`
  - `updateStoredToken()`
  - `clearAuthData()`
- ✅ Fixed token refresh to update the correct axios instance
- ✅ Added proper error handling and redirect on auth failure
- ✅ Improved token refresh with proper URLSearchParams format

### `stores/auth.ts`
- ✅ Removed manual `Authorization` headers from `fetchUser()`
- ✅ Removed manual `Authorization` headers from `logout()`
- ✅ Now relies on axios interceptor to add headers automatically
- ✅ Simplified API calls

### `services/authService.ts`
- ✅ Added `/api/v1` prefix to all API endpoints
- ✅ Removed manual `Authorization` headers
- ✅ Fixed `refreshToken()` to use URLSearchParams with correct content-type
- ✅ Removed `accessToken` parameter from `logout()` and `getCurrentUser()`

## How Authentication Works Now

### 1. **Login Flow**
```
User enters credentials
  ↓
auth.login() called
  ↓
POST /api/v1/auth/login
  ↓
Receive access_token & refresh_token
  ↓
Store in localStorage (via VueUse)
  ↓
Fetch user data with GET /api/v1/users/me
  ↓
Axios interceptor automatically adds Bearer token
```

### 2. **API Request Flow**
```
Make API call (e.g., axios.get('/api/v1/users/me'))
  ↓
Request interceptor adds Authorization header from localStorage
  ↓
Request sent to backend
  ↓
Response received
```

### 3. **Token Refresh Flow (on 401)**
```
API returns 401 Unauthorized
  ↓
Response interceptor catches error
  ↓
Get refresh_token from localStorage
  ↓
POST /api/v1/auth/refresh with refresh_token
  ↓
Receive new access_token
  ↓
Update localStorage with new token
  ↓
Retry original request with new token
  ↓
If refresh fails: Clear auth data & redirect to /login
```

### 4. **Logout Flow**
```
User clicks logout
  ↓
auth.logout() called
  ↓
POST /api/v1/auth/logout (with auto-added Bearer token)
  ↓
Clear token, refreshToken, and user from localStorage
  ↓
User redirected to login page
```

## Testing Checklist

- [ ] Test login with valid credentials
- [ ] Test login with invalid credentials
- [ ] Test registration
- [ ] Test that authenticated API calls work
- [ ] Test token refresh when token expires (backend returns 401)
- [ ] Test logout functionality
- [ ] Test that protected routes redirect to login when not authenticated
- [ ] Test that refresh token failure redirects to login
- [ ] Verify no circular dependency errors in console
- [ ] Verify Authorization headers are added correctly (check Network tab)
- [ ] Test multiple simultaneous API calls with expired token

## Environment Variables

Make sure your `.env` file has:
```env
VITE_API_BASE_URL=http://localhost:8000
```

Or in production:
```env
VITE_API_BASE_URL=https://your-backend-domain.com
```

## Benefits of These Fixes

1. **No More Circular Dependencies**: Clean, predictable initialization
2. **Single Source of Truth**: Axios interceptor is the only place managing auth headers
3. **Consistent API Paths**: All endpoints use the correct `/api/v1` prefix
4. **Robust Token Refresh**: Proper error handling and retry logic
5. **Better Error Handling**: Failed auth properly clears data and redirects
6. **Maintainable Code**: Clear separation of concerns

## Notes

- The axios interceptor now handles ALL authentication header logic
- Never manually add `Authorization` headers in your API calls
- The store simply manages the token state in localStorage
- VueUse's `useLocalStorage` provides reactive localStorage with proper serialization
- All auth-related API calls should go through the auth store or authService