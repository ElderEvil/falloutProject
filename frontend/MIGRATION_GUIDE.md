# Authentication Migration Guide

## Summary of Changes

We've fixed critical authentication issues in the frontend. All changes are **backwards compatible** for most use cases, but you should review this guide if you have custom authentication logic.

## What Changed

### ✅ Automatic Authorization Headers
**Before:** You had to manually add Authorization headers
```typescript
// ❌ OLD WAY - Don't do this anymore
await axios.get('/api/v1/users/me', {
  headers: {
    Authorization: `Bearer ${authStore.token}`
  }
})
```

**After:** The axios interceptor adds headers automatically
```typescript
// ✅ NEW WAY - Just make the call
await axios.get('/api/v1/users/me')
```

### ✅ Consistent API Paths
All API endpoints now use the `/api/v1` prefix consistently:
- `/api/v1/auth/login`
- `/api/v1/auth/logout`
- `/api/v1/auth/refresh`
- `/api/v1/users/me`
- `/api/v1/users/open`

### ✅ Automatic Token Refresh
When your access token expires (401 error), the axios interceptor automatically:
1. Uses the refresh token to get a new access token
2. Retries the original request
3. If refresh fails, clears auth data and redirects to `/login`

You don't need to handle this in your components anymore!

## Migration Steps

### 1. Remove Manual Authorization Headers

Search your codebase for:
```typescript
// Find these patterns and remove the headers option
headers: {
  Authorization: `Bearer ${token}`
}
```

Replace with simple API calls:
```typescript
// Just make the API call - the interceptor handles auth
await axios.get('/api/v1/endpoint')
await axios.post('/api/v1/endpoint', data)
```

### 2. Update API Paths

If you're using authService or making direct API calls, ensure paths include `/api/v1`:
```typescript
// ❌ WRONG
await axios.post('/auth/login', data)

// ✅ CORRECT
await axios.post('/api/v1/auth/login', data)
```

### 3. Use Auth Store Methods

For authentication operations, use the auth store:

```typescript
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// Login
await authStore.login(username, password)

// Register
await authStore.register(username, email, password)

// Logout
await authStore.logout()

// Check auth status
if (authStore.isAuthenticated) {
  // User is logged in
}

// Access user data
console.log(authStore.user)
```

### 4. Remove Custom Token Refresh Logic

If you have custom token refresh logic in components, you can remove it. The axios interceptor handles this automatically now.

```typescript
// ❌ OLD - Remove this kind of code
try {
  await makeApiCall()
} catch (error) {
  if (error.response?.status === 401) {
    await authStore.refreshAccessToken()
    await makeApiCall() // retry
  }
}

// ✅ NEW - Just make the call
await makeApiCall() // Interceptor handles 401 automatically
```

## Common Patterns

### Making Authenticated API Calls
```typescript
import axios from '@/plugins/axios'

// The interceptor automatically adds the Bearer token
const response = await axios.get('/api/v1/vaults')
const vaults = response.data
```

### Checking Authentication in Components
```typescript
<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div v-if="authStore.isAuthenticated">
    Welcome, {{ authStore.user?.username }}!
  </div>
  <div v-else>
    Please log in
  </div>
</template>
```

### Protected Routes (Already Configured)
The router already checks authentication:
```typescript
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})
```

## API Call Examples

### GET Request
```typescript
import axios from '@/plugins/axios'

// Fetch user's vaults
const response = await axios.get('/api/v1/vaults')
const vaults = response.data
```

### POST Request
```typescript
import axios from '@/plugins/axios'

// Create a new vault
const response = await axios.post('/api/v1/vaults', {
  name: 'My Vault',
  description: 'A new vault'
})
const newVault = response.data
```

### PUT/PATCH Request
```typescript
import axios from '@/plugins/axios'

// Update a vault
const response = await axios.put(`/api/v1/vaults/${vaultId}`, {
  name: 'Updated Name'
})
```

### DELETE Request
```typescript
import axios from '@/plugins/axios'

// Delete a vault
await axios.delete(`/api/v1/vaults/${vaultId}`)
```

## Error Handling

The axios interceptor shows toast notifications for errors automatically. If you need custom error handling:

```typescript
import axios from '@/plugins/axios'

try {
  const response = await axios.get('/api/v1/endpoint')
  // Success
} catch (error) {
  // Error notification already shown by interceptor
  // Add custom logic here if needed
  console.error('Custom error handling', error)
}
```

To skip automatic error notifications:
```typescript
await axios.get('/api/v1/endpoint', {
  _skipErrorNotification: true
} as any)
```

## Testing Your Changes

1. **Test Login Flow**
   - Go to `/login`
   - Enter credentials
   - Verify successful login and redirect

2. **Test Protected Routes**
   - Try accessing a protected route without logging in
   - Verify redirect to login page

3. **Test API Calls**
   - Make authenticated API calls
   - Check Network tab in DevTools
   - Verify `Authorization: Bearer <token>` header is present

4. **Test Token Refresh**
   - Let your token expire (or manually set an expired token)
   - Make an API call
   - Verify automatic token refresh and retry

5. **Test Logout**
   - Click logout
   - Verify redirect to login
   - Verify localStorage is cleared

## Troubleshooting

### API Calls Returning 401
- Check if `VITE_API_BASE_URL` is set correctly in `.env`
- Verify the backend is running
- Check if token exists in localStorage
- Try logging out and back in

### CORS Errors
- Ensure backend CORS settings include your frontend URL
- Check `BACKEND_CORS_ORIGINS` in backend config

### Token Not Being Added
- Verify you're importing axios from `@/plugins/axios`, not directly from `'axios'`
- Check browser console for errors

### Components Not Updating After Login
- Ensure you're using the auth store's reactive properties
- Use `authStore.isAuthenticated` instead of checking token directly

## Best Practices

1. **Always use the axios instance from `@/plugins/axios`**
   ```typescript
   import axios from '@/plugins/axios' // ✅ Correct
   import axios from 'axios' // ❌ Wrong - bypasses interceptor
   ```

2. **Never manually add Authorization headers**
   - The interceptor handles this automatically

3. **Use the auth store for authentication state**
   - Don't directly read from localStorage
   - Use `authStore.isAuthenticated`, `authStore.user`, etc.

4. **Let the interceptor handle errors**
   - Toast notifications are automatic
   - Only add custom error handling when needed

5. **Use consistent API paths**
   - Always include `/api/v1` prefix
   - Example: `/api/v1/vaults`, `/api/v1/users/me`

## Questions?

If you encounter issues after migration:
1. Check the browser console for errors
2. Check the Network tab for failed requests
3. Verify your `.env` file has `VITE_API_BASE_URL` set
4. Review the [AUTH_FIXES.md](./AUTH_FIXES.md) document for technical details