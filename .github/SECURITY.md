# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | ✅ Active support  |
| < 1.0   | ❌ No longer supported |

## Reporting a Vulnerability

### 🔒 Private Disclosure (Preferred)

**Do NOT create a public GitHub issue for security vulnerabilities.**

Report security issues through one of these channels:

| Method         | Details                              |
|----------------|--------------------------------------|
| **Email**      | security@valorcyber.com              |
| **GitHub**     | Security tab → "Report a vulnerability" |

### 📋 What to Include

When reporting a vulnerability, please provide:

1. **Description**: Clear description of the vulnerability
2. **Impact**: Severity assessment and potential impact
3. **Steps to Reproduce**: Detailed reproduction steps
4. **Affected Versions**: Which versions are affected
5. **Proof of Concept**: If available (sanitized)
6. **Suggested Fix**: If you have recommendations

### ⏱️ Response Timeline

| Phase                  | Timeline        |
|------------------------|-----------------|
| Initial response       | Within 48 hours |
| Vulnerability triage   | Within 7 days   |
| Fix development        | Within 30 days  |
| Security advisory      | After fix release |
| Public disclosure      | Coordinated with reporter |

### 🎁 Recognition

We appreciate security researchers:

- Credit in security advisories (with permission)
- Acknowledgment in SECURITY.md
- Consideration for bug bounty (if applicable)

## Security Features

This project includes built-in security features:

| Feature                | Description                                    |
|------------------------|------------------------------------------------|
| **Fail-Open Design**   | System failures forward all logs (no data loss) |
| **Compliance Bypass**  | Regulated logs bypass AI filtering             |
| **Rate Limiting**      | API protection against abuse                   |
| **Circuit Breaker**    | Cascade failure prevention                     |
| **Audit Trail**        | All classification decisions logged            |
| **Input Validation**   | Pydantic models for all inputs                 |

## Automated Security Scanning

| Scan Type                 | Tool       | Schedule          |
|---------------------------|------------|-------------------|
| Dependency Vulnerabilities | pip-audit  | Weekly + PRs      |
| Container Scanning        | Trivy      | Weekly + PRs      |
| Secret Detection          | Gitleaks   | Weekly + PRs      |
| Static Analysis           | CodeQL     | Weekly + PRs      |
| Dependency Review         | GitHub     | Pull Requests     |

## Secure Development

### Branch Protection

The `main` branch is protected:

- ✅ Signed commits required
- ✅ PR reviews required
- ✅ CI checks must pass
- ✅ No force pushes

See [Branch Protection Rules](docs/guides/BRANCH_PROTECTION.md) for details.

### Security in CI/CD

All changes are scanned before merge:

```yaml
# Security workflow runs on:
- Every pull request
- Push to main branch
- Weekly scheduled scan
```

### Dependabot

Automated dependency updates:

- Weekly checks for Python dependencies
- Weekly checks for Docker base images
- Weekly checks for GitHub Actions
- Immediate security updates

## Compliance

This project supports compliance with:

| Framework   | Features                                    |
|-------------|---------------------------------------------|
| PCI-DSS     | Payment log bypass, 365-day retention       |
| HIPAA       | PHI bypass, 6-year retention                |
| SOX         | Financial log bypass, 7-year retention      |
| GDPR        | PII bypass, configurable retention          |

## Security Contacts

| Role              | Contact                    |
|-------------------|----------------------------|
| Security Team     | security@valorcyber.com    |
| Maintainer        | @Jacob-Valor               |

---

Thank you for helping keep this project secure! 🛡️
