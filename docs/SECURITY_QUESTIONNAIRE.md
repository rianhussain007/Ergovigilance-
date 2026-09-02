# ErgoVigilance Security Questionnaire

## 1. Data Privacy & Protection

### 1.1 What data does ErgoVigilance collect?
- **Worker pose data**: 2D body keypoints (33 points per frame) — NOT video/images
- **Risk scores**: Calculated from pose angles (RULA/REBA-derived)
- **Session metadata**: Timestamps, duration, camera ID
- **Worker identification**: Employee ID, name, department (opt-in only)

### 1.2 Where is data stored?
- **On-Premise**: All data stays on customer hardware. No cloud upload required.
- **Cloud Tier**: Encrypted at rest (AES-256) and in transit (TLS 1.3)
- **Database**: PostgreSQL (production) or SQLite (development)
- **Recordings**: Local filesystem with configurable retention (default 90 days)

### 1.3 Is video stored?
- **No by default**: System processes frames in real-time and discards them
- **Optional recording**: Session recordings stored locally, auto-deleted after retention period
- **Privacy setting**: Can be disabled entirely in Settings

### 1.4 GDPR/CCPA Compliance
- **Consent management**: Built-in consent tracking with grant/deny/withdraw
- **Data export**: Article 20 portability — export all worker data as JSON/CSV
- **Right to erasure**: One-click data deletion with audit trail
- **Data Processing Agreement**: Available upon request
- **DPO contact**: [Insert DPO email]

## 2. Infrastructure Security

### 2.1 Authentication
- **JWT tokens**: HS256 signing with configurable secret
- **Password hashing**: bcrypt with salt
- **MFA/TOTP**: Time-based one-time passwords for admin accounts
- **Backup codes**: 10 single-use recovery codes per user
- **Session management**: Token expiry, automatic logout

### 2.2 Authorization
- **Role-based access control (RBAC)**: 4 roles
  - Operator: View own data, acknowledge alerts
  - Supervisor: View all workers, manage alerts
  - Safety Manager: Full analytics, reports, audit trail
  - Admin: System configuration, user management, deployment
- **Route protection**: Frontend and backend enforce role permissions
- **API endpoints**: Each endpoint requires specific role

### 2.3 Network Security
- **HTTPS/TLS**: Required in production (HSTS enabled)
- **Security headers**: HSTS, CSP, X-Frame-Options, Referrer-Policy
- **CORS**: Configurable allowed origins
- **Rate limiting**: Per-IP and per-role with configurable limits

### 2.4 Infrastructure
- **Docker**: Non-root user, minimal base image (python:3.12-slim)
- **Kubernetes**: Network policies, pod isolation, HPA auto-scaling
- **Secrets**: Environment variables, Kubernetes secrets, never in code
- **Logging**: Structured JSON logs for ELK/Datadog/Splunk integration

## 3. Application Security

### 3.1 Input Validation
- **SQL injection**: Parameterized queries, input sanitization
- **XSS prevention**: Content Security Policy, input escaping
- **Path traversal**: Directory validation, restricted file access
- **Request validation**: Pydantic models with strict type checking

### 3.2 Audit Trail
- **SOC2 compliant**: Immutable append-only log with HMAC chain integrity
- **Events logged**: Login, logout, data access, configuration changes, alert actions
- **Tamper detection**: HMAC-SHA256 chain verification
- **Export**: JSON/CSV export for compliance review

### 3.3 Vulnerability Management
- **Dependency scanning**: npm audit (frontend), pip-audit (backend)
- **Container scanning**: Trivy in CI pipeline
- **Security updates**: Regular dependency updates
- **Responsible disclosure**: Security contact provided

## 4. Operational Security

### 4.1 Backup & Recovery
- **Automated backups**: Daily database backups with configurable retention
- **Backup script**: `deploy/backup.sh` with dry-run mode
- **Restore procedure**: `deploy/restore.sh` with verification
- **RPO**: 24 hours (configurable)
- **RTO**: 30 minutes

### 4.2 Monitoring
- **Health checks**: `/healthz` (liveness), `/readyz` (readiness)
- **Metrics**: Prometheus `/metrics` endpoint
- **Alerting**: Configurable alert rules (email, Slack, webhook)
- **SLA monitoring**: Real-time availability tracking

### 4.3 Incident Response
- **Response time**: 4-hour response for critical issues (Enterprise tier)
- **Escalation**: Defined escalation path
- **Communication**: Status page at `/status`
- **Post-incident review**: Root cause analysis for all incidents

## 5. Compliance & Certifications

### 5.1 Standards
- **SOC 2 Type II**: Audit trail, access controls, monitoring
- **GDPR**: Consent management, data portability, right to erasure
- **CCPA**: Consumer rights, data disclosure
- **ISO 27001**: Security management (planned)

### 5.2 Certifications
- **In progress**: SOC 2 Type II audit
- **Planned**: ISO 27001 certification
- **Required**: Customer-specific compliance requirements

## 6. Contact Information

- **Security Contact**: security@ergovigilance.com
- **Privacy Officer**: privacy@ergovigilance.com
- **Support**: support@ergovigilance.com
- **Emergency**: +1-XXX-XXX-XXXX (24/7 for Enterprise tier)
