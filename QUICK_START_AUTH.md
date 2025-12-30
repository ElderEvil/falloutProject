# Quick Start - Authentication System

Get the email verification and password reset system running in 5 minutes.

## Prerequisites
- Docker/Podman installed
- `.env` file configured

## Step 1: Start Services (30 seconds)

```bash
# Start all services including MailHog
docker-compose up -d

# Or with Podman
podman-compose up -d
```

## Step 2: Run Migration (30 seconds)

```bash
# Option A: Auto-runs with docker-compose (already done!)
# The fastapi service runs migrations on startup

# Option B: Manual migration
docker-compose exec fastapi alembic upgrade head

# Or with Podman
podman-compose exec fastapi alembic upgrade head
```

## Step 3: Verify Services (30 seconds)

Open these URLs in your browser:

- ✅ **Backend API**: http://localhost:8000/docs
- ✅ **Frontend**: http://localhost:5173
- ✅ **MailHog (Email)**: http://localhost:8025

All should load successfully.

## Step 4: Test Email Verification (2 minutes)

### Register a New User
1. Go to http://localhost:5173/register
2. Fill in username, email, and password
3. Click "Register"

### Check Verification Email
1. Go to http://localhost:8025
2. You should see a "Verify Your Email" email
3. Click the "Verify Email Address" button
4. You'll be redirected and see "Email Verified!"

### Resend Verification (Optional)
1. If you didn't verify, login to the app
2. You'll see a yellow banner: "Please verify your email"
3. Click "Resend Email"
4. Check http://localhost:8025 for the new email

## Step 5: Test Password Reset (2 minutes)

### Request Reset
1. Go to http://localhost:5173/login
2. Click "Forgot Password?"
3. Enter your email
4. Click "Send Reset Link"

### Reset Password
1. Go to http://localhost:8025
2. Open the "Password Reset Request" email
3. Click "Reset Password"
4. Enter new password (min 8 characters)
5. Confirm password
6. Click "Reset Password"

### Verify Confirmation Email
1. Go to http://localhost:8025
2. You should see "Password Changed Successfully" email
3. Login with your new password!

## Step 6: Test Automatic Token Refresh (Optional)

This happens automatically in the background. To observe:

1. Login to the app
2. Open browser DevTools (F12)
3. Go to Network tab
4. Use the app normally
5. Watch for automatic `/refresh-token` calls before token expires

---

## Common Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Just backend
docker-compose logs -f fastapi

# Just MailHog
docker-compose logs -f mailhog
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart backend only
docker-compose restart fastapi
```

### Stop Services
```bash
docker-compose stop
```

### Full Reset (Delete All Data)
```bash
docker-compose down -v
docker-compose up -d
# Then re-run migrations if needed
```

---

## Troubleshooting

### "Migration failed" error
```bash
# Check if database is ready
docker-compose logs db

# Manually run migration
docker-compose exec fastapi alembic upgrade head
```

### "Can't connect to SMTP server"
```bash
# Verify MailHog is running
docker-compose ps | grep mailhog

# Check .env has:
# SMTP_HOST=localhost
# SMTP_PORT=1025

# Restart backend
docker-compose restart fastapi
```

### "Email not showing in MailHog"
```bash
# Check backend logs for email errors
docker-compose logs fastapi | grep -i email

# Verify MailHog is accessible
curl http://localhost:8025
```

### "Frontend can't reach backend"
```bash
# Verify backend is running
curl http://localhost:8000/docs

# Check VITE_API_BASE_URL in frontend/.env
# Should be: http://localhost:8000
```

---

## What's Next?

✅ **For Development**: You're all set! The system uses MailHog for testing.

⚠️ **For Production**: Update `.env` with real SMTP credentials:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_TLS=True
FRONTEND_URL=https://your-production-domain.com
```

---

## Success Checklist

- [x] Services started (`docker-compose up -d`)
- [x] Migration completed (auto or manual)
- [x] Can access backend (http://localhost:8000/docs)
- [x] Can access frontend (http://localhost:5173)
- [x] Can access MailHog (http://localhost:8025)
- [x] Registration sends verification email
- [x] Password reset flow works
- [x] Confirmation emails received

---

**You're ready to go!** 🚀

Need more details? Check:
- `AUTH_SYSTEM_SUMMARY.md` - Complete system overview
- `MAILHOG_SETUP.md` - MailHog configuration details
- `MIGRATION_INSTRUCTIONS.md` - Migration troubleshooting
