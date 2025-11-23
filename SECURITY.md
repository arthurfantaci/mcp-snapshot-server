# Security Considerations

This document outlines security considerations and best practices for the MCP Snapshot Server.

## Table of Contents
- [Overview](#overview)
- [Authentication & Authorization](#authentication--authorization)
- [Data Security](#data-security)
- [Input Validation](#input-validation)
- [API Security](#api-security)
- [Network Security](#network-security)
- [Logging & Monitoring](#logging--monitoring)
- [Dependency Management](#dependency-management)
- [Incident Response](#incident-response)

## Overview

### Security Model

The MCP Snapshot Server handles potentially sensitive customer data including:
- Meeting transcripts
- Customer information (names, companies, contacts)
- Financial metrics
- Business strategies

**Security Priorities:**
1. Protect API keys and credentials
2. Validate all input data
3. Prevent data leakage in logs
4. Secure data in transit and at rest
5. Monitor for suspicious activity

### Threat Model

**Threats Addressed:**
- ✅ API key exposure
- ✅ Malicious file uploads
- ✅ Data injection attacks
- ✅ Information disclosure via logs
- ✅ Dependency vulnerabilities

**Out of Scope:**
- Network-level attacks (handled by infrastructure)
- Physical security
- Social engineering

## Authentication & Authorization

### API Key Management

**DO:**
- ✅ Store API keys in environment variables
- ✅ Use secrets management systems (AWS Secrets Manager, HashiCorp Vault)
- ✅ Rotate API keys regularly
- ✅ Use different keys for dev/staging/prod

**DON'T:**
- ❌ Hard-code API keys in source code
- ❌ Commit API keys to version control
- ❌ Share API keys in chat/email
- ❌ Log API keys

**Example - Secure API Key Loading:**
```python
# Good
api_key = os.getenv("LLM_ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("API key not found")

# Bad
api_key = "sk-ant-1234567890"  # Never do this!
```

### Environment Variable Security

```bash
# Set restrictive permissions on .env file
chmod 600 .env

# Verify no keys in git
git secrets --scan

# Use encrypted environment variables in CI/CD
# GitHub: Use encrypted secrets
# GitLab: Use masked variables
```

### Access Control

**Claude Desktop Integration:**
- Server runs with user's permissions
- No additional authentication needed
- Access controlled by Claude Desktop login

**Standalone Deployment:**
- Implement authentication layer if exposing API
- Use API keys or OAuth for client authentication
- Implement role-based access control (RBAC) if needed

## Data Security

### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| API Keys | Secret | Environment variables only |
| Transcripts | Confidential | Encrypt in transit, don't persist |
| Generated Snapshots | Confidential | Encrypt in transit, temporary storage |
| Logs | Internal | Sanitize PII, encrypt at rest |
| Configuration | Internal | Version control (no secrets) |

### Data Encryption

**In Transit:**
```python
# All API calls use HTTPS
client = Anthropic(api_key=api_key)  # Uses HTTPS by default

# MCP uses stdio (local) or encrypted transport
```

**At Rest:**
```bash
# If persisting snapshots to disk
# Encrypt the storage volume
# Linux: LUKS
# macOS: FileVault
# Cloud: AWS EBS encryption, Azure Disk Encryption
```

### Data Retention

**Recommended Policy:**
- Transcripts: Don't persist (process and discard)
- Snapshots: Temporary storage (clear after session)
- Logs: Rotate after 30 days
- Backups: Encrypt and retain per compliance requirements

**Implementation:**
```python
# Clear snapshots after session
def cleanup_snapshots():
    """Remove old snapshots from memory."""
    cutoff = datetime.now() - timedelta(hours=24)
    for snapshot_id in list(self.snapshots.keys()):
        if self.snapshots[snapshot_id]['created_at'] < cutoff:
            del self.snapshots[snapshot_id]
```

### PII Handling

**Transcript Analysis:**
- Customer names, emails, phone numbers detected
- Financial figures, company information extracted
- **Do not** send to third-party analytics
- **Do not** log complete transcript text

**Sanitization:**
```python
def sanitize_for_logging(data):
    """Remove PII from data before logging."""
    if 'email' in data:
        data['email'] = '[REDACTED]'
    if 'phone' in data:
        data['phone'] = '[REDACTED]'
    # Truncate long text
    if 'transcript' in data:
        data['transcript'] = data['transcript'][:100] + '...'
    return data
```

## Input Validation

### File Upload Validation

**VTT File Validation:**
```python
def validate_vtt_file(file_path: str):
    """Validate VTT file before processing."""

    # 1. Check file exists
    if not os.path.exists(file_path):
        raise ValueError("File not found")

    # 2. Check file extension
    if not file_path.lower().endswith('.vtt'):
        raise ValueError("Invalid file type")

    # 3. Check file size (prevent DoS)
    max_size = 10 * 1024 * 1024  # 10MB
    if os.path.getsize(file_path) > max_size:
        raise ValueError("File too large")

    # 4. Check it's a file, not directory
    if os.path.isdir(file_path):
        raise ValueError("Path is a directory")

    # 5. Validate VTT format
    try:
        webvtt.read(file_path)
    except webvtt.errors.MalformedFileError:
        raise ValueError("Invalid VTT format")
```

**Path Traversal Prevention:**
```python
# Resolve and validate paths
def safe_path(user_input):
    """Ensure path doesn't escape intended directory."""
    base_dir = Path("/allowed/directory")
    requested_path = Path(user_input).resolve()

    # Check if path is within allowed directory
    if not str(requested_path).startswith(str(base_dir)):
        raise SecurityError("Path traversal attempt detected")

    return requested_path
```

### Content Validation

**Prompt Injection Prevention:**
```python
def sanitize_user_input(text: str) -> str:
    """Sanitize user input to prevent prompt injection."""

    # Remove control characters
    text = ''.join(char for char in text if char.isprintable())

    # Limit length
    max_length = 10000
    if len(text) > max_length:
        text = text[:max_length]

    # Check for suspicious patterns
    suspicious_patterns = [
        r'ignore previous instructions',
        r'system:',
        r'<script>',
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"Suspicious input detected: {pattern}")
            # Either reject or sanitize

    return text
```

## API Security

### Rate Limiting

**Anthropic API:**
```python
# Implement exponential backoff
@retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
async def sample_llm(...):
    # Automatic retry with increasing delays
    pass

# Track API usage
api_calls_per_minute = 0
last_reset = time.time()

def check_rate_limit():
    global api_calls_per_minute, last_reset

    if time.time() - last_reset > 60:
        api_calls_per_minute = 0
        last_reset = time.time()

    if api_calls_per_minute >= 50:  # Anthropic limit
        raise RateLimitError("API rate limit exceeded")

    api_calls_per_minute += 1
```

### Error Handling

**Secure Error Messages:**
```python
# Good - Generic error message
try:
    result = process_snapshot(file)
except Exception as e:
    logger.error(f"Snapshot generation failed: {type(e).__name__}")
    return {"error": "Processing failed. Please try again."}

# Bad - Exposes internal details
try:
    result = process_snapshot(file)
except Exception as e:
    return {"error": str(e)}  # May expose paths, keys, etc.
```

### API Key Validation

```python
def validate_api_key(key: str):
    """Validate API key format before use."""

    # Check format
    if not key.startswith('sk-ant-'):
        raise ValueError("Invalid API key format")

    # Check length
    if len(key) < 40:
        raise ValueError("API key too short")

    # Test with simple API call
    try:
        client = Anthropic(api_key=key)
        # Make minimal test call
    except Exception:
        raise ValueError("API key validation failed")
```

## Network Security

### HTTPS/TLS

**All external communication uses TLS:**
- Anthropic API: HTTPS by default
- Claude Desktop: stdio (local communication)
- Custom deployments: Enforce HTTPS

**Certificate Validation:**
```python
# Anthropic SDK handles this
# Don't disable certificate verification!

# Bad
requests.get(url, verify=False)  # Never do this

# Good
requests.get(url, verify=True)  # Default, always use
```

### Firewall Rules

**For Standalone Deployment:**
```bash
# Allow only necessary ports
# Block all except:
# - 443 (HTTPS outbound to Anthropic)
# - Custom port for your app (if needed)

# Example iptables rules
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A OUTPUT -p tcp -j DROP
```

## Logging & Monitoring

### Secure Logging

**What to Log:**
- ✅ Snapshot generation start/complete
- ✅ Validation failures
- ✅ API errors (without keys)
- ✅ Configuration changes
- ✅ Authentication attempts

**What NOT to Log:**
- ❌ API keys
- ❌ Complete transcripts
- ❌ Personal information (emails, phones)
- ❌ Passwords or credentials

**Example:**
```python
# Good
logger.info("Snapshot generated", extra={
    "snapshot_id": "acme-2024",
    "sections": 11,
    "avg_confidence": 0.85
})

# Bad
logger.info(f"Generated snapshot with key {api_key}")  # Never!
logger.debug(f"Transcript: {full_transcript}")  # Too much data
```

### Security Monitoring

**Monitor For:**
1. Repeated authentication failures
2. Unusual API usage patterns
3. Large file upload attempts
4. Suspicious file paths (traversal attempts)
5. Unexpected error rates

**Example Alert:**
```python
def check_security_alerts():
    """Monitor for security events."""

    # Track failed validations
    if failed_validations > 5:
        alert("Multiple validation failures detected")

    # Monitor API errors
    if api_errors > 10:
        alert("High API error rate - possible attack")

    # Check file sizes
    if avg_file_size > 20_000_000:  # 20MB
        alert("Unusually large files being processed")
```

## Dependency Management

### Regular Updates

```bash
# Check for updates weekly
uv pip list --outdated

# Update dependencies
uv sync --upgrade

# Run security audit
pip-audit  # or use uv's future security features
```

### Vulnerability Scanning

**GitHub Dependabot:**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
```

**Manual Scanning:**
```bash
# Install safety
pip install safety

# Scan for known vulnerabilities
safety check

# Or use pip-audit
pip install pip-audit
pip-audit
```

### Pinned Dependencies

```toml
# pyproject.toml - pin major versions
dependencies = [
    "anthropic>=0.34.0,<1.0",
    "mcp>=0.9.0,<1.0",
    "pydantic>=2.0.0,<3.0",
]
```

## Incident Response

### Security Incident Plan

**1. Detection**
- Monitor logs for suspicious activity
- Set up alerts for security events
- Regular security reviews

**2. Containment**
- Revoke compromised API keys immediately
- Disable affected services
- Isolate affected systems

**3. Investigation**
- Review logs for scope of breach
- Identify attack vector
- Document findings

**4. Recovery**
- Rotate all credentials
- Apply security patches
- Update security controls

**5. Post-Mortem**
- Document incident
- Update security procedures
- Implement preventive measures

### Emergency Contacts

```yaml
# security-contacts.yml
security_team:
  email: security@yourorg.com
  slack: #security-incidents
  phone: "+1-555-0100"

anthropic_support:
  email: support@anthropic.com
  docs: https://docs.anthropic.com/security
```

### Key Rotation Procedure

```bash
# 1. Generate new API key
# (Via Anthropic Console)

# 2. Update environment variables
# Update .env or secrets manager

# 3. Restart services
sudo systemctl restart mcp-snapshot-server

# 4. Verify new key works
uv run pytest tests/test_server.py -k api

# 5. Revoke old key
# (Via Anthropic Console)

# 6. Monitor for errors
journalctl -u mcp-snapshot-server -f
```

## Security Checklist

### Deployment Checklist

- [ ] API keys stored in environment variables
- [ ] .env file has 600 permissions
- [ ] No secrets in git history
- [ ] Input validation enabled
- [ ] File size limits configured
- [ ] Rate limiting implemented
- [ ] HTTPS enforced for all external calls
- [ ] Logging sanitizes PII
- [ ] Dependencies up to date
- [ ] Security monitoring configured
- [ ] Backup encryption enabled
- [ ] Incident response plan documented
- [ ] Team trained on security procedures

### Audit Questions

**Monthly Security Review:**
1. Have any API keys been exposed?
2. Are dependencies up to date?
3. Have there been unusual error patterns?
4. Are logs being reviewed?
5. Is PII being properly sanitized?
6. Are backups encrypted?
7. Have security tests been run?

## Compliance

### Data Protection Regulations

**GDPR (European Users):**
- Obtain consent for data processing
- Provide data access/deletion capabilities
- Document data processing activities
- Implement data minimization

**CCPA (California Users):**
- Disclose data collection practices
- Honor opt-out requests
- Provide data access rights

**Implementation:**
```python
def handle_data_deletion_request(user_id):
    """Delete all user data per GDPR/CCPA."""

    # Remove snapshots
    for snapshot_id in list(self.snapshots.keys()):
        if self.snapshots[snapshot_id]['user_id'] == user_id:
            del self.snapshots[snapshot_id]

    # Purge from logs (if persisted)
    # Notify user of completion
```

## Additional Resources

- [Anthropic Security Best Practices](https://docs.anthropic.com/security)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [MCP Security Guidelines](https://modelcontextprotocol.io/security)
- [Python Security Guide](https://python.readthedocs.io/en/latest/library/security_warnings.html)

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public GitHub issue
2. Email: security@yourorg.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours.
