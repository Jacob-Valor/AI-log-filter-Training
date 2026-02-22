# Pull Request

## 📋 Description

<!-- Provide a clear and concise description of your changes -->

Fixes # (issue)

## 🎯 Type of Change

<!-- Mark the relevant option with an 'x' -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Refactoring (no functional changes)
- [ ] 🧪 Test addition/update
- [ ] 🛡️ Security improvement

## 🧪 Testing

<!-- Describe the tests you ran to verify your changes -->

- [ ] Unit tests pass (`pytest tests/`)
- [ ] Linting passes (`ruff check src/ tests/`)
- [ ] Formatting is correct (`ruff format --check src/ tests/`)
- [ ] New tests added for new functionality
- [ ] All existing tests pass

### Test Results

```
Paste test output or summary here
```

## 📊 Performance Impact

<!-- If applicable, describe any performance implications -->

| Metric          | Before | After | Change |
|-----------------|--------|-------|--------|
| Latency (P95)   |        |       |        |
| Memory Usage    |        |       |        |
| Throughput      |        |       |        |

## 🔒 Security Considerations

<!-- Describe any security implications of this change -->

- [ ] No security implications
- [ ] Security review needed
- [ ] Changes affect authentication/authorization
- [ ] Changes affect data handling/compliance

## 📝 Checklist

<!-- Mark completed items with an 'x' -->

### Code Quality
- [ ] Code follows the project's style guidelines
- [ ] Self-review of code completed
- [ ] Code is properly commented
- [ ] Docstrings added/updated for public APIs
- [ ] No new warnings introduced

### Testing
- [ ] Unit tests added for new functionality
- [ ] Integration tests added if applicable
- [ ] All tests pass locally
- [ ] Test coverage maintained or improved

### Documentation
- [ ] README.md updated if needed
- [ ] API documentation updated if needed
- [ ] CHANGELOG.md updated (if applicable)
- [ ] Inline comments added for complex logic

### Compliance
- [ ] Changes maintain fail-open behavior
- [ ] Compliance bypass logic preserved (PCI/HIPAA/SOX/GDPR)
- [ ] Audit trail logging maintained

## 📸 Screenshots (if applicable)

<!-- Add screenshots for UI changes -->

## 🔗 Related Issues/PRs

<!-- List any related issues or pull requests -->

- Related to #
- Depends on #
- Blocks #

## 📋 Additional Notes

<!-- Add any additional information that reviewers should know -->

---

## 📌 For Reviewers

### Review Focus Areas
<!-- What should reviewers pay special attention to? -->

### Testing Instructions
<!-- How can reviewers test this change? -->

```bash
# Commands to test this PR
```

### Deployment Notes
<!-- Any special deployment considerations? -->

---

**By submitting this PR, I confirm that:**
- I have read the [CONTRIBUTING.md](CONTRIBUTING.md) guidelines
- I have tested my changes locally
- I am ready to address any feedback from reviewers
