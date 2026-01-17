# MinIO Public Access Setup Guide

## Overview

This guide explains how to configure MinIO for public access to media files (images and audio) in production.

## Problem

- MinIO runs on internal Docker network
- Frontend cannot access files via `http://localhost:9000` URLs
- Images and audio fail to load in production

## Solution

### 1. Create Public Subdomain

Create a subdomain pointing to your MinIO server:

```
Subdomain: media.yourdomain.com
Target: Your server IP
Ports: 9000 (API), 9001 (Console)
```

### 2. Configure Reverse Proxy (Nginx/Caddy/Traefik)

#### Option A: Nginx

```nginx
server {
    listen 80;
    server_name media.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name media.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/media.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/media.yourdomain.com/privkey.pem;

    # Increase max upload size for media files
    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS headers (if needed)
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS";
        add_header Access-Control-Allow-Headers "Range, Content-Type";
    }
}
```

#### Option B: Caddy (Simpler)

```caddyfile
media.yourdomain.com {
    reverse_proxy localhost:9000

    header {
        Access-Control-Allow-Origin *
        Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
        Access-Control-Allow-Headers "Range, Content-Type"
    }
}
```

### 3. SSL Certificate

#### Let's Encrypt (Recommended)

```bash
# Using Certbot
sudo certbot --nginx -d media.yourdomain.com

# Or with Caddy (automatic)
# Caddy handles SSL automatically
```

### 4. Update Environment Variables

Update your production `.env` or `.env.prod`:

```bash
# MinIO Configuration
MINIO_HOSTNAME=minio  # Internal Docker hostname
MINIO_PORT=9000
MINIO_ROOT_USER=your-secure-user
MINIO_ROOT_PASSWORD=your-secure-password-min-8-chars
MINIO_DEFAULT_BUCKET=fallout-bucket

# Public URL for file access (NEW)
MINIO_PUBLIC_URL=https://media.yourdomain.com
```

### 5. Configure MinIO CORS (Required for Browser Access)

#### Method 1: Using MinIO Client (mc)

```bash
# Install MinIO Client
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# Configure alias
mc alias set myminio https://media.yourdomain.com your-secure-user your-secure-password-min-8-chars

# Set CORS policy
mc anonymous set-json deployment/minio-cors-config.json myminio/dweller-images
mc anonymous set-json deployment/minio-cors-config.json myminio/dweller-thumbnails
mc anonymous set-json deployment/minio-cors-config.json myminio/dweller-audio
mc anonymous set-json deployment/minio-cors-config.json myminio/chat-audio
mc anonymous set-json deployment/minio-cors-config.json myminio/outfit-images
mc anonymous set-json deployment/minio-cors-config.json myminio/weapon-images
```

#### Method 2: Using MinIO Console (GUI)

1. Access MinIO Console: `https://media.yourdomain.com:9001`
2. Login with `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`
3. Go to **Buckets** → Select bucket (e.g., `dweller-images`)
4. Click **Anonymous** tab
5. Set policy to **download** (read-only public access)
6. Repeat for all public buckets

### 6. Test Public Access

```bash
# Test if files are publicly accessible
curl -I https://media.yourdomain.com/dweller-images/test.png

# Should return 200 OK with proper headers
```

## Security Considerations

### 1. Bucket Isolation

- Public buckets (images/audio) - read-only public access
- Private buckets (user data) - no public access

### 2. Rate Limiting

Consider adding rate limiting in your reverse proxy:

```nginx
# Nginx example
limit_req_zone $binary_remote_addr zone=media:10m rate=10r/s;

server {
    # ...
    location / {
        limit_req zone=media burst=20 nodelay;
        # ...
    }
}
```

### 3. CDN (Optional but Recommended)

For better performance, put a CDN in front of MinIO:

- Cloudflare
- AWS CloudFront
- Fastly

Update `MINIO_PUBLIC_URL` to CDN URL: `https://cdn.yourdomain.com`

## Troubleshooting

### Files not loading

1. Check MinIO is accessible: `curl https://media.yourdomain.com/minio/health/live`
2. Check bucket policy: Files should be publicly readable
3. Check CORS headers: `curl -I https://media.yourdomain.com/bucket/file.png`
4. Check firewall: Port 9000 should be accessible (or proxied)

### CORS errors in browser console

- Ensure CORS policy is set on buckets
- Check reverse proxy CORS headers
- Verify `Access-Control-Allow-Origin` header is present

### 403 Forbidden errors

- Bucket policy not set to public
- Check `MINIO_PUBLIC_BUCKET_WHITELIST` in backend config
- Verify bucket exists and has files

## Local Development

For local development, leave `MINIO_PUBLIC_URL` empty or set to `http://localhost:9000`:

```bash
# .env (local)
MINIO_HOSTNAME=localhost
MINIO_PORT=9000
MINIO_PUBLIC_URL=http://localhost:9000  # Optional, will fallback automatically
```

## Production Checklist

- [ ] Subdomain created and DNS configured
- [ ] Reverse proxy configured (Nginx/Caddy/Traefik)
- [ ] SSL certificate installed and valid
- [ ] `MINIO_PUBLIC_URL` set in production environment
- [ ] CORS policy configured on all public buckets
- [ ] Test file access from frontend application
- [ ] (Optional) CDN configured for better performance
- [ ] Monitoring and logging enabled

## Useful Commands

```bash
# List all buckets
mc ls myminio

# List bucket policy
mc anonymous list myminio/dweller-images

# Set bucket to public read-only
mc anonymous set download myminio/dweller-images

# Remove public access
mc anonymous set none myminio/private-bucket

# Check MinIO server info
mc admin info myminio
```

## Additional Resources

- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [MinIO Client Guide](https://min.io/docs/minio/linux/reference/minio-mc.html)
- [CORS Configuration](https://min.io/docs/minio/linux/administration/console/security-and-access.html#id2)
