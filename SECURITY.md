# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.x.x   | ✅ Yes    |
| < 1.0   | ❌ No     |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

### 🔒 Private Disclosure

**Do NOT create a public GitHub issue for security vulnerabilities.**

Instead, please report security issues by emailing:

- **Email**: security@example.com (replace with your email)

### 📋 What to Include

When reporting a vulnerability, please include:

1. **Description**: Clear description of the vulnerability
2. **Impact**: Potential impact and severity assessment
3. **Steps to Reproduce**: Detailed steps to reproduce the issue
4. **Affected Versions**: Which versions are affected
5. **Suggested Fix**: If you have a suggested fix (optional)

### ⏱️ Response Timeline

| Action                     | Timeline        |
| -------------------------- | --------------- |
| Initial response           | Within 48 hours |
| Vulnerability confirmation | Within 7 days   |
| Fix development            | Within 30 days  |
| Public disclosure          | After fix       |

### 🎁 Recognition

We appreciate security researchers who help keep this project safe:

- Credit in release notes (with permission)
- Acknowledgment in SECURITY.md

## Security Considerations

This project handles security logs. Key security features:

- **Fail-Open Design**: System failures forward all logs (no data loss)
- **Compliance Bypass**: Regulated logs (PCI-DSS, HIPAA, SOX, GDPR) bypass AI
- **Audit Trail**: All classification decisions are logged
- **No Sensitive Data Logging**: PII/credentials are never logged

## Dependencies

We regularly update dependencies to address known vulnerabilities:

- Automated dependency scanning via GitHub Actions
- Regular security audits of third-party packages

---

Thank you for helping keep this project secure! 🛡️
