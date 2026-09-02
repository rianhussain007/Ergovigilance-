# DATA PROCESSING AGREEMENT

## Between:
**ErgoVigilance Systems** ("Processor")
Address: [Insert Address]
Contact: privacy@ergovigilance.com

## And:
**[Customer Name]** ("Controller")
Address: [Insert Address]
Contact: [Insert Contact]

## Effective Date: [Insert Date]

---

## 1. Purpose

This Data Processing Agreement ("DPA") governs the processing of personal data by ErgoVigilance Systems on behalf of the Customer in connection with the ErgoVigilance ergonomic monitoring platform.

## 2. Definitions

- **Personal Data**: Any information relating to an identified or identifiable natural person ("Data Subject"), including worker pose data, risk scores, and identification information.
- **Processing**: Any operation performed on personal data, including collection, recording, analysis, storage, and deletion.
- **Data Subject**: An identified or identifiable natural person whose personal data is processed (i.e., factory workers).
- **Supervisory Authority**: The data protection authority responsible for the Customer's jurisdiction.

## 3. Scope of Processing

### 3.1 Data Categories
- Worker identification (employee ID, name, department)
- Body pose keypoints (2D, 33 points per frame)
- Posture risk scores (calculated from pose angles)
- Session metadata (timestamps, duration, camera ID)
- Consent records (status, date, expiry)

### 3.2 Purpose
Processing is limited to:
- Ergonomic risk assessment for workplace safety
- Regulatory compliance reporting (OSHA, local safety regulations)
- Worker health and wellness analytics (with consent)

### 3.3 Data Subjects
- Factory workers monitored by the ErgoVigilance system
- Supervisors and safety managers accessing the platform

## 4. Obligations of the Processor

### 4.1 Processing Instructions
Processor shall only process Personal Data in accordance with Controller's documented instructions, except where required by law.

### 4.2 Confidentiality
Processor shall ensure that all personnel authorized to process Personal Data are bound by confidentiality obligations.

### 4.3 Security Measures
Processor shall implement appropriate technical and organizational measures, including:
- Encryption at rest (AES-256) and in transit (TLS 1.3)
- Access controls with role-based permissions
- Audit logging with tamper detection
- Regular security assessments
- Incident response procedures

### 4.4 Sub-processing
Processor shall not engage another processor without prior written consent of Controller. Any approved sub-processor must be bound by equivalent data protection obligations.

### 4.5 Data Subject Rights
Processor shall assist Controller in responding to Data Subject requests, including:
- Right of access (Article 15 GDPR)
- Right to rectification (Article 16 GDPR)
- Right to erasure (Article 17 GDPR)
- Right to data portability (Article 20 GDPR)

### 4.6 Data Breach Notification
Processor shall notify Controller within 48 hours of becoming aware of a personal data breach, providing:
- Nature of the breach
- Categories and approximate number of Data Subjects affected
- Likely consequences
- Measures taken or proposed to address the breach

### 4.7 Data Protection Impact Assessment
Processor shall assist Controller in conducting Data Protection Impact Assessments where required.

### 4.8 Return and Deletion
Upon termination of the Agreement, Processor shall:
- Return all Personal Data to Controller in a structured, commonly used format
- Delete all copies within 30 days, unless retention is required by law

## 5. Obligations of the Controller

### 5.1 Lawful Processing
Controller warrants that it has a lawful basis for processing Personal Data, including:
- Obtaining informed consent from Data Subjects
- Ensuring processing is necessary for the stated purpose
- Complying with applicable data protection laws

### 5.2 Data Subject Consent
Controller shall obtain and document informed consent from all Data Subjects prior to monitoring, including:
- Purpose of processing
- Categories of data processed
- Data retention period
- Rights of Data Subjects
- Contact details for questions

### 5.3 Instructions
Controller shall provide documented processing instructions to Processor and promptly notify of any changes.

## 6. Technical and Organizational Measures

### 6.1 Measures Implemented
- Role-based access control (RBAC)
- Multi-factor authentication (MFA/TOTP)
- Encryption at rest and in transit
- Audit logging with HMAC chain integrity
- Automated data retention and deletion
- Network segmentation and firewall rules
- Regular security updates and patches

### 6.2 Measures Available
- Kubernetes network policies
- Pod security contexts
- Secret management (Kubernetes secrets, environment variables)
- Monitoring and alerting (Prometheus, Grafana)
- Backup and recovery procedures

## 7. Cross-Border Data Transfers

### 7.1 Location
All Personal Data is processed within [Customer's jurisdiction] unless otherwise agreed.

### 7.2 Safeguards
Any cross-border transfers shall comply with GDPR Chapter V, including:
- Standard Contractual Clauses (SCCs)
- Adequacy decisions
- Binding Corporate Rules (BCRs)

## 8. Liability and Indemnification

### 8.1 Liability
Each party shall be liable for damages caused by breach of this DPA, subject to applicable law.

### 8.2 Indemnification
Processor shall indemnify Controller against claims arising from Processor's breach of this DPA.

## 9. Term and Termination

### 9.1 Term
This DPA shall remain in effect for the duration of the main service agreement.

### 9.2 Termination
Either party may terminate this DPA with 30 days written notice.

### 9.3 Survival
Sections 4 (Obligations of Processor), 7 (Cross-Border Transfers), and 8 (Liability) shall survive termination.

## 10. Governing Law

This DPA shall be governed by the laws of [Insert Jurisdiction].

---

## Signatures

**For ErgoVigilance Systems:**

Name: _______________________
Title: _______________________
Date: _______________________

**For [Customer Name]:**

Name: _______________________
Title: _______________________
Date: _______________________
