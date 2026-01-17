# Nginx Proxy Manager Setup for MinIO (evillab.dev)

## Quick Setup Guide

### 1. Create Proxy Host in Nginx Proxy Manager

**Access your Nginx Proxy Manager** (usually at port 81):

- URL: `http://your-server-ip:81`
- Login with your credentials

**Add new Proxy Host** for MinIO:

#### Proxy Host Configuration

**Domain Names:**

```
fallout-media.evillab.dev
```

**Scheme:** `http`

**Forward Hostname/IP:** `minio` (or your MinIO container name)

**Forward Port:** `9000`

**Enable options:**

- ✅ Cache Assets
- ✅ Block Common Exploits
- ✅ Websockets Support (optional, but recommended)

#### SSL Tab

**SSL Certificate:**

- Select: "Request a new SSL Certificate"
- ✅ Force SSL
- ✅ HTTP/2 Support
- ✅ HSTS Enabled
- Email: `your-email@example.com`
- ✅ I Agree to the Let's Encrypt Terms of Service

Click **Save**

### 2. Add Custom Nginx Configuration for CORS

**In the Proxy Host you just created:**

1. Click on the three dots menu → **Edit**
2. Go to **Custom locations** tab
3. Add a new location:

**Location:** `/`

**Custom config:**

```nginx
# CORS Headers for browser access
add_header Access-Control-Allow-Origin * always;
add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
add_header Access-Control-Allow-Headers "Range, Content-Type" always;
add_header Access-Control-Max-Age 3600 always;

# Handle preflight requests
if ($request_method = 'OPTIONS') {
    return 204;
}

# Increase upload size for large media files
client_max_body_size 100M;

# Proxy settings
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_buffering off;
```

Or use the **Advanced** tab directly:

```nginx
location / {
    # CORS Headers
    add_header Access-Control-Allow-Origin * always;
    add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Range, Content-Type" always;
    add_header Access-Control-Max-Age 3600 always;

    # Handle preflight
    if ($request_method = 'OPTIONS') {
        return 204;
    }

    # Proxy to MinIO
    proxy_pass http://minio:9000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;

    # Large file support
    client_max_body_size 100M;
}
```

Click **Save**

### 3. Optional: MinIO Console Proxy (Admin UI)

If you want to access MinIO console at `https://fallout-media-console.evillab.dev`:

**Create another Proxy Host:**

**Domain Names:**

```
fallout-media-console.evillab.dev
```

**Scheme:** `http`

**Forward Hostname/IP:** `minio`

**Forward Port:** `9001`

**Enable SSL** (same as above)

### 4. Configure MinIO Buckets for Public Access

#### Option A: Using MinIO Console (GUI)

1. Access: `https://fallout-media-console.evillab.dev` (if you set it up)
2. Login:
    - Username: `ElderEvil`
    - Password: `password123`
3. Go to **Buckets**
4. For each bucket (`dweller-images`, `dweller-thumbnails`, `dweller-audio`, `chat-audio`, `outfit-images`,
   `weapon-images`):
    - Click on the bucket
    - Go to **Anonymous** tab
    - Click **Add Access Rule**
    - Prefix: leave empty (or `*`)
    - Access: **readonly** (download)
    - Click **Save**

#### Option B: Using MinIO Client (mc)

```bash
# Install MinIO Client
docker run -it --rm \
  --entrypoint /bin/sh \
  minio/mc

# Inside container
mc alias set myminio https://fallout-media.evillab.dev ElderEvil password123

# Set public read access for each bucket
mc anonymous set download myminio/dweller-images
mc anonymous set download myminio/dweller-thumbnails
mc anonymous set download myminio/dweller-audio
mc anonymous set download myminio/chat-audio
mc anonymous set download myminio/outfit-images
mc anonymous set download myminio/weapon-images
```

### 5. Restart Your Containers

After updating docker-compose.yml:

```bash
docker-compose down
docker-compose up -d
```

Or just restart the affected services:

```bash
docker-compose restart fastapi celery_worker celery_beat
```

### 6. Test Public Access

```bash
# Test if MinIO is accessible
curl -I https://fallout-media.evillab.dev/minio/health/live

# Should return: 200 OK

# Test if CORS headers are present
curl -I https://fallout-media.evillab.dev/dweller-images/test.png

# Should include:
# Access-Control-Allow-Origin: *
```

### 7. Verify in Application

1. Open your app: `https://fallout.evillab.dev`
2. Create or view a dweller with an image
3. Check browser console - images should load without CORS errors
4. Try playing audio - should work without errors

## Troubleshooting

### Images/Audio Still Not Loading

**Check MinIO logs:**

```bash
docker logs minio
```

**Check Nginx Proxy Manager logs:**

```bash
docker logs nginx-proxy-manager
```

**Verify bucket policy:**

```bash
docker exec -it minio mc anonymous list local/dweller-images
```

### CORS Errors in Browser

- Verify CORS headers are present: `curl -I https://fallout-media.evillab.dev/bucket/file`
- Check Nginx Proxy Manager custom config is saved
- Restart Nginx Proxy Manager container

### 403 Forbidden Errors

- Bucket doesn't exist (create it in MinIO console)
- Bucket policy not set to public (set to "download/readonly")
- Wrong credentials (check `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`)

### DNS Not Resolving

- Wait 5-10 minutes for DNS propagation
- Check DNS records in your domain registrar
- Use `nslookup fallout-media.evillab.dev` to verify

## Current Configuration Summary

Your current setup (docker-compose.yml):

```yaml
# Environment variables added:
- MINIO_PUBLIC_URL=https://fallout-media.evillab.dev

# Existing:
- Frontend: https://fallout.evillab.dev
- Backend API: https://fallout-api.evillab.dev
- MinIO Media: https://fallout-media.evillab.dev (NEW)
```

## Security Notes

1. **Public Buckets:** Only buckets in `MINIO_PUBLIC_BUCKET_WHITELIST` get public read access
2. **Write Access:** Only backend can write (not public)
3. **Private Data:** User data buckets remain private
4. **Rate Limiting:** Consider adding in Nginx Proxy Manager if needed

## Next Steps

After completing this setup:

1. ✅ Dweller images will load
2. ✅ Audio files will play
3. ✅ CORS errors resolved
4. ✅ HTTPS enforced
5. ✅ CDN-ready (optional: add Cloudflare in front)

---

**Last Updated:** 2026-01-17
