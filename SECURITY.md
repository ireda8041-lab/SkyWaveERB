# 🔐 Security Policy - Sky Wave ERP

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | ✅ Yes             |
| 1.2.x   | ⚠️ Security fixes only |
| < 1.2   | ❌ No              |

## Security Best Practices

### 🔑 Environment Variables

**Never commit sensitive data to version control!**

All sensitive configuration should be stored in environment variables:

```env
# .env file (never commit this!)
MONGO_URI=mongodb://user:password@host:port/db
GEMINI_API_KEY=your-api-key
DEFAULT_ADMIN_PASSWORD=secure-password
SECRET_KEY=random-secret-key
```

### 📁 Files to Keep Private

These files should **never** be committed to Git:

- `.env` - Environment variables
- `*.db` - Local database files
- `logs/*.log` - Log files
- `exports/*` - Exported data

### 🔒 Password Policy

- Minimum 8 characters
- Mix of uppercase, lowercase, numbers, and symbols
- Change default admin password immediately after installation
- Passwords are hashed using PBKDF2 with random salt

### 🌐 Network Security

- MongoDB connections should use authentication
- Use TLS/SSL for production MongoDB connections
- Restrict MongoDB access to specific IP addresses

## Reporting a Vulnerability

If you discover a security vulnerability:

1. **Do NOT** open a public issue
2. Email us at: skywaveads@gmail.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work on a fix.

## Security Checklist for Deployment

- [ ] Change default admin password
- [ ] Set strong SECRET_KEY
- [ ] Configure MongoDB authentication
- [ ] Enable MongoDB TLS/SSL
- [ ] Restrict database network access
- [ ] Review user permissions
- [ ] Enable logging
- [ ] Set up regular backups
- [ ] Keep dependencies updated

---

**Last Updated**: January 2026
