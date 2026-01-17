# 🔐 Security Guide

This guide explains the security features of the Fallout Shelter application, including rate limiting via `fastapi-guard`, authentication, and production security best practices.

---

## 📋 Overview

**fastapi-guard** provides enterprise-grade security middleware for FastAPI including:

- **Rate Limiting**: Limit requests per IP to prevent abuse
- **IP Whitelisting/Blacklisting**: Control access by IP address
- **Auto-banning**: Automatically ban IPs with suspicious activity
- **Geolocation**: Optional IP geolocation for advanced filtering
- **Redis Integration**: Distributed rate limiting for multi-server deployments

---

## ⚙️ Configuration

### Environment Variables

Add these to your `.env` or `.env.prod` file:

```bash
# Enable/disable rate limiting
ENABLE_RATE_LIMITING=True

# Rate limiting settings
RATE_LIMIT_REQUESTS=100  # Requests per window per IP
RATE_LIMIT_WINDOW=60     # Time window in seconds

# Auto-ban configuration
AUTO_BAN_THRESHOLD=10    # Blocked requests before auto-ban
AUTO_BAN_DURATION=3600   # Ban duration in seconds (1 hour)

# Optional: IPInfo API token for geolocation
IPINFO_TOKEN=

# Optional: IP access control (comma-separated)
SECURITY_WHITELIST_IPS=192.168.1.100,10.0.0.50
SECURITY_BLACKLIST_IPS=123.45.67.89,98.76.54.32
```

### Production Recommendations

For **production environments**, consider these settings:

```bash
# More lenient for legitimate users, strict for abuse
RATE_LIMIT_REQUESTS=200
RATE_LIMIT_WINDOW=60
AUTO_BAN_THRESHOLD=20
AUTO_BAN_DURATION=3600
```

For **development/testing**, you may want to disable or increase limits:

```bash
ENABLE_RATE_LIMITING=False  # Disable completely
# OR
RATE_LIMIT_REQUESTS=1000    # Very high limit
```

---

## 🚀 How It Works

### 1. Rate Limiting

Each IP address can make up to `RATE_LIMIT_REQUESTS` requests within `RATE_LIMIT_WINDOW` seconds.

**Example**: With `RATE_LIMIT_REQUESTS=100` and `RATE_LIMIT_WINDOW=60`:
- An IP can make 100 requests per minute
- On the 101st request within that minute, they'll receive a `429 Too Many Requests` error
- After 60 seconds, their counter resets

### 2. Auto-Banning

If an IP repeatedly triggers rate limits (or other security blocks), they're automatically banned.

**Example**: With `AUTO_BAN_THRESHOLD=10`:
- After 10 blocked requests, the IP is banned for `AUTO_BAN_DURATION` seconds
- While banned, ALL requests from that IP are rejected with `403 Forbidden`
- Ban automatically expires after the duration

### 3. IP Whitelisting

IPs in `SECURITY_WHITELIST_IPS` bypass ALL rate limiting and security checks.

**Use cases**:
- Your own monitoring services
- Admin IP addresses
- Trusted partner APIs
- Load balancer health checks

**Example**:
```bash
SECURITY_WHITELIST_IPS=192.168.1.100,10.0.0.50,203.0.113.25
```

### 4. IP Blacklisting

IPs in `SECURITY_BLACKLIST_IPS` are completely blocked from accessing the API.

**Use cases**:
- Known malicious IPs
- Blocked abusers
- Compromised sources

**Example**:
```bash
SECURITY_BLACKLIST_IPS=123.45.67.89,98.76.54.32
```

### 5. Redis Integration (Production)

In production (`ENVIRONMENT=production`), rate limiting state is stored in Redis for distributed tracking across multiple servers.

**Benefits**:
- Consistent rate limits across all backend instances
- Shared ban list
- Persistent state across restarts

**Configuration** (automatic in production):
```python
# Configured in app/middleware/security.py
enable_redis=True if ENVIRONMENT == "production"
redis_url=settings.redis_url
redis_prefix="fastapi_guard:"
```

---

## 📊 Monitoring & Logging

### Log Messages

Security events are logged at various levels:

```python
# INFO: Successful security middleware initialization
logger.info("Security middleware enabled with rate limiting")

# WARNING: Rate limit exceeded
logger.warning(f"Rate limit exceeded for IP {client_ip}")

# WARNING: Auto-ban triggered
logger.warning(f"IP {client_ip} has been auto-banned for {duration}s")

# ERROR: Security configuration issues
logger.error("Failed to initialize IPInfo handler")
```

### Response Headers

When rate limited, responses include helpful headers:

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1673456789
Retry-After: 45
```

---

## 🔧 Advanced Features

### Geolocation (Optional)

Enable IP geolocation for advanced filtering (requires IPInfo token):

1. Sign up at https://ipinfo.io (free tier: 50k requests/month)
2. Get your API token
3. Add to `.env.prod`:
   ```bash
   IPINFO_TOKEN=your_token_here
   ```

**Use cases**:
- Block/allow specific countries
- Log geographic distribution of requests
- Detect VPN/proxy usage

### Cloud Provider Blocking (Optional)

Block requests from cloud provider IPs (AWS, GCP, Azure, etc.):

Edit `app/middleware/security.py`:
```python
config = SecurityConfig(
    # ... other settings ...
    block_cloud_providers=True,  # Enable cloud blocking
)
```

**Use case**: Prevent abuse from cloud-hosted bots/scrapers

### Blocked User Agent Filtering

Block specific user agents (bots, scrapers):

Edit `app/middleware/security.py`:
```python
config = SecurityConfig(
    # ... other settings ...
    blocked_user_agents=[
        "curl",
        "wget",
        "BadBot/1.0",
        "Scraper/2.0",
    ],
)
```

**Note**: User agent patterns are case-insensitive and support partial matches.

---

## 🛠️ Troubleshooting

### Issue: Legitimate users getting rate limited

**Solution**: Increase limits or whitelist their IPs
```bash
RATE_LIMIT_REQUESTS=200  # Increase from 100
# OR
SECURITY_WHITELIST_IPS=their.ip.address.here
```

### Issue: Rate limiting not working

**Check**:
1. Is `ENABLE_RATE_LIMITING=True`?
2. Is Redis running (for production)?
3. Check logs for initialization errors

### Issue: Can't access API (banned)

**Solution**: Clear Redis ban list or restart with fresh Redis:
```bash
# Connect to Redis
redis-cli

# List all keys
KEYS fastapi_guard:*

# Delete specific ban
DEL fastapi_guard:banned:192.168.1.100

# OR clear all (caution!)
FLUSHDB
```

### Issue: Redis connection errors

**Check**:
- Redis is running: `docker-compose ps redis`
- Redis URL is correct: `REDIS_HOST` and `REDIS_PORT` in `.env`
- Network connectivity between services

---

## 🧪 Testing Rate Limiting

### Manual Testing

Test rate limiting with curl:

```bash
# Send 110 requests (exceeds limit of 100)
for i in {1..110}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/healthcheck
  sleep 0.1
done

# Expected: First 100 return 200, next 10 return 429
```

### Load Testing

Use locust for realistic load testing:

```bash
cd backend
uv run locust -f locust/locustfile.py --host=http://localhost:8000
```

Monitor rate limiting behavior under load.

---

## 📚 API Error Responses

### 429 Too Many Requests

```json
{
  "detail": "Rate limit exceeded. Please try again later.",
  "status_code": 429
}
```

### 403 Forbidden (Banned IP)

```json
{
  "detail": "Access forbidden. Your IP has been blocked due to suspicious activity.",
  "status_code": 403
}
```

### 403 Forbidden (Blacklisted IP)

```json
{
  "detail": "Access denied. Your IP address is not allowed.",
  "status_code": 403
}
```

---

## 🔒 Security Best Practices

1. **Use Redis in production**: Ensures consistent rate limiting across servers
2. **Monitor logs**: Watch for unusual patterns (many bans, specific IPs)
3. **Adjust limits based on traffic**: Start conservative, increase as needed
4. **Whitelist trusted sources**: Monitoring, admin IPs, partner APIs
5. **Document banned IPs**: Keep notes on why IPs were blacklisted
6. **Regular review**: Periodically review and clear old bans
7. **Don't rely solely on rate limiting**: Use authentication, validation, etc.

---

## 📖 Resources

- **fastapi-guard Documentation**: https://rennf93.github.io/fastapi-guard/
- **GitHub Repository**: https://github.com/rennf93/fastapi-guard
- **IPInfo API**: https://ipinfo.io
- **Configuration File**: `backend/app/middleware/security.py`
- **Settings File**: `backend/app/core/config.py`

---

## 🆘 Support

For issues or questions:
1. Check fastapi-guard GitHub issues: https://github.com/rennf93/fastapi-guard/issues
2. Review application logs for security events
3. Adjust configuration in `backend/app/middleware/security.py`

---

## 🛡️ Additional Security Measures

### Authentication & Authorization

#### JWT Token Security
```bash
# Secret key rotation (recommended every 90 days)
SECRET_KEY=your-new-strong-secret-key

# Token expiration settings
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

#### Password Security
- **Bcrypt** hashing with salt rounds
- **Password complexity requirements**
- **Password reset tokens** with expiration
- **Multi-factor authentication** (planned feature)

### Data Protection

#### Sensitive Data Handling
- **PII encryption** at rest and in transit
- **API key encryption** in database
- **Session management** with secure cookies
- **CSRF protection** for state-changing operations

#### Database Security
```sql
-- Row-level security example
CREATE POLICY user_isolation ON users
    FOR ALL TO app_user
    USING (id = current_user_id());
```

### Infrastructure Security

#### Network Security
- **Firewall rules** restricting access to essential ports
- **VPN access** for administrative functions
- **Load balancer** with SSL termination
- **DDoS protection** via Cloudflare/AWS Shield

#### Container Security
```yaml
# Docker security context
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
```

### Monitoring & Auditing

#### Security Monitoring
```bash
# Failed login attempts monitoring
grep "failed login" /var/log/app.log | tail -100

# Rate limit violations
grep "rate limit exceeded" /var/log/app.log | tail -100

# Auto-ban events
grep "auto-banned" /var/log/app.log | tail -50
```

#### Audit Logging
- **User action logs** with timestamps
- **API access logs** with IP tracking
- **Database change logs** for sensitive tables
- **Security event logs** for investigation

### Compliance Checklist

#### OWASP Top 10 Compliance
- [ ] **A01: Broken Access Control** - RBAC implementation
- [ ] **A02: Cryptographic Failures** - Encryption at rest/transit
- [ ] **A03: Injection** - SQL injection prevention
- [ ] **A04: Insecure Design** - Security by design principles
- [ ] **A05: Security Misconfiguration** - Hardened configurations
- [ ] **A06: Vulnerable Components** - Dependency scanning
- [ ] **A07: Authentication Failures** - Strong auth mechanisms
- [ ] **A08: Software/Data Integrity** - Code signing, verification
- [ ] **A09: Logging/Monitoring** - Comprehensive security logging
- [ ] **A10: SSRF** - Request validation, allowlists

#### GDPR Compliance
- [ ] **Data Minimization** - Collect only necessary data
- [ ] **Consent Management** - Explicit user consent
- [ ] **Right to Erasure** - Data deletion capabilities
- [ ] **Data Portability** - Export user data
- [ ] **Breach Notification** - Incident response procedures

---

## 🔧 Security Scripts

### Generate Secure Secret Key
```bash
#!/bin/bash
# generate-secret.sh
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### Security Audit Script
```bash
#!/bin/bash
# security-audit.sh

echo "🔍 Running security audit..."

# Check for exposed secrets
grep -r "sk-" . --exclude-dir=node_modules --exclude-dir=.git
grep -r "password" . --exclude-dir=node_modules --exclude-dir=.git

# Check file permissions
find . -type f -name "*.env*" -ls

# Check SSL certificates
openssl x509 -in cert.pem -text -noout

# Run dependency vulnerability scan
cd backend && uv run safety check
cd ../frontend && pnpm audit

echo "✅ Security audit complete"
```

---

**Last Updated**: 2026-01-18
**Version**: v1.13.7 with comprehensive security features
