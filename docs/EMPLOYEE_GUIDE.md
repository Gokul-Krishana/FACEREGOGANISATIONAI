# Employee User Guide & Biometric Privacy Notice

**System:** Face Recognition AI Attendance System v2.1.0  
**Target Audience:** All enrolled employees, staff members, and students  
**Privacy Compliance:** GDPR (Regulation EU 2016/679), Illinois BIPA, California CCPA/CPRA  

---

## 1. Introduction to the Attendance System

Face Recognition AI provides automated, contactless attendance recording using state-of-the-art computer vision and anti-spoofing technology:

- **Contactless & Instant**: Attendance is recorded in under 1 second as you walk past authorized cameras at designated entry checkpoints.
- **Anti-Spoofing Security**: The system incorporates deep neural network liveness analysis (MiniFASNetV2) to prevent spoofing from printed photos, video replays, or phone screens.
- **Transparent Logging**: You can view your real-time attendance timestamps and verification history at any time.

---

## 2. Your Biometric Privacy Rights

Your biometric data is sensitive personal information. We treat it with the highest cryptographic and legal standards:

1. **Explicit Consent**:
   Biometric enrollment is strictly opt-in. Your facial images and vector representations are processed only with your active consent (`consent_given = True`).
2. **Encryption at Rest**:
   Your face embedding vector is encrypted at rest using industry-standard AES-256 authenticated encryption.
3. **No Third-Party Sharing**:
   Biometric vectors are never sold, leased, traded, or shared with third parties or external cloud services. All processing occurs on secure institutional infrastructure.
4. **Right to Withdraw Consent**:
   You may withdraw your biometric consent at any time without adverse employment consequence. Upon withdrawal, automated camera recognition is immediately disabled for your profile.
5. **Right to Permanent Deletion (Cryptographic Shredding)**:
   Pursuant to GDPR Article 17 ("Right to be Forgotten") and BIPA § 15(a), when you leave the institution or request biometric erasure, your facial photographs are permanently destroyed using multi-pass cryptographic file shredding (NIST SP 800-88 compliant), and your mathematical embeddings are deleted from the vector index.

---

## 3. How to Record Your Attendance

1. **Step into Camera View**: Approach the checkpoint camera at a normal walking pace (recommended distance: 1.0 to 2.5 meters).
2. **Look Toward the Camera**: Ensure your face is unobstructed by heavy scarves or dark sunglasses. Standard prescription glasses and religious headwear that does not cover the eyes/nose/mouth are fully supported.
3. **Visual Confirmation**: The display screen will show a green bounding box with your name and a confirmation chime indicating your attendance is logged.
4. **Cooldown Protection**: To prevent duplicate entries, the system enforces an automatic daily attendance confirmation with a 60-second cooldown per camera.

---

## 4. How to Request Biometric Deletion or Consent Withdrawal

If you wish to withdraw biometric consent or request the permanent destruction of your facial data:

1. **Self-Service / Administrator Request**:
   Contact your system administrator or Human Resources department with your Employee ID.
2. **Administrative Action**:
   The administrator navigates to **Dashboard > Employees > Delete / Shred Employee Biometrics** and selects:
   - **Shred Biometrics Only**: Destroys photos and vector embeddings, marks consent as withdrawn, and retains non-biometric employment attendance logs.
   - **Delete Employee & Shred Biometrics**: Completely removes the employee record and shreds all associated biometric artifacts.
3. **Audit Confirmation**:
   A tamper-evident audit record (`BIOMETRIC_SHREDDED`) is generated, confirming the exact timestamp of permanent file destruction.

