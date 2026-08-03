# Section 22 — Complete Class Diagram (UML)

UML class diagrams for the major subsystems, derived from source.

## 22.1 AI Pipeline Classes

```mermaid
classDiagram
    class FaceDetector {
        +model: YOLO
        +person_class_id: int
        +detect(frame, conf_threshold) List[dict]
        +crop_person(frame, bbox, padding) np.ndarray
        +get_largest_detection(detections) dict
    }

    class FaceRecognizer {
        +app: FaceAnalysis
        +model_name: str
        +extract_embedding(face_img) np.ndarray
        +detect_face(person_crop) dict
        +get_landmarks(face_img) np.ndarray
        +compute_similarity(emb1, emb2) float
        +embedding_dim() int
    }

    class FaceEnrollment {
        +index: faiss.Index
        +metadata: List[dict]
        +dimension: int
        +enroll(name, embedding) bool
        +search(embedding, k, threshold) List[dict]
        +remove_by_name(name) bool
        +rename(old_name, new_name) bool
        +clear() None
        +all_persons() List[str]
        +count() int
        +unique_count() int
        +status() dict
        -_create_index() faiss.Index
        -_save() None
    }

    class FaceQualityAssessment {
        +weights: dict
        +assess(face_img, det_score, face_bbox, img_shape, landmarks) dict
    }

    class LivenessResult {
        +is_live: bool
        +liveness_score: float
        +texture_score: float
        +blink_score: float
        +motion_score: float
        +screen_score: float
        +dl_score: float
        +dl_time_ms: float
        +blink_detected: bool
        +reasons: List[str]
    }

    class LivenessDetector {
        -_deep_liveness: DeepLivenessDetector
        -_ear_history: Deque
        -_blink_count: int
        -_prev_gray: np.ndarray
        +analyze_frame(face_img, landmarks) LivenessResult
        +reset() None
        +register_blink() None
        +deep_liveness_available: bool
    }

    class DeepLivenessDetector {
        -_session: InferenceSession
        -_model_available: bool
        -_fallback_active: bool
        +predict(face_img, landmarks) DeepLivenessResult
        +available: bool
        +using_fallback: bool
        +reload() bool
        -_predict_onnx() DeepLivenessResult
        -_predict_fallback() DeepLivenessResult
    }

    class TrackState {
        +track_id: str
        +first_seen: float
        +last_seen: float
        +total_frames: int
        +consistent_frames: int
        +identity: str
        +identity_confidence: float
        +arcface_distances: List
        +liveness_scores: List
        +quality_scores: List
        +attendance_marked: bool
        +spoof_frame_count: int
        +avg_arcface_distance: float
        +identity_stability: float
    }

    class MultiFrameTracker {
        -_tracks: Dict[str, TrackState]
        -_disappeared: Dict[str, int]
        +update(detections, frame_shape) List[TrackState]
        +reset() None
        +get_track(track_id) TrackState
        +_iou(box_a, box_b) float
    }

    class AMFRDecision {
        <<enum>>
        ACCEPT
        BORDERLINE
        LOW_CONFIDENCE
        REJECT_SPOOF
        PENDING
    }

    class AMFREngine {
        +quality: FaceQualityAssessment
        +tracker: MultiFrameTracker
        -_liveness_instances: Dict[str, LivenessDetector]
        +process_frame(frame, detections, embeddings, faiss_results, face_data) List[dict]
        +reset() None
        +get_all_tracks() List[TrackState]
        +status() dict
        -_evaluate_person(frame, det, embedding, faiss, face, track_id) dict
        -_decide(arcface_distance, liveness_score, quality_score, is_live, faiss_confidence) tuple
    }

    class AttendanceTracker {
        +log_dir: Path
        +mark(name, confidence) bool
        +today() List[dict]
        +by_date(date) List[dict]
        +all_records() dict
        +statistics() dict
    }

    AMFREngine --> FaceQualityAssessment
    AMFREngine --> MultiFrameTracker
    AMFREngine --> LivenessDetector : per-track instances
    AMFREngine --> AMFRDecision
    LivenessDetector --> LivenessResult
    LivenessDetector --> DeepLivenessDetector
    MultiFrameTracker --> TrackState
    FaceDetector ..> FaceRecognizer : crop feeds
    FaceRecognizer ..> FaceEnrollment : embedding queries
```

## 22.2 Camera Classes

```mermaid
classDiagram
    class CameraSource {
        <<abstract>>
        +name: str
        +source_type: str
        +open() bool*
        +release() None*
        +read() (bool, np.ndarray)*
        +is_opened() bool*
        +set_resolution(w, h) None*
        +get_resolution() (int, int)*
        +info() dict*
    }

    class WebcamSource
    class USBAnySource
    class AndroidWiFiSource
    class AndroidUSBSource
    class iPhoneWiFiSource
    class iPhoneUSBSource
    class IPCameraSource
    class FakeCameraSource

    CameraSource <|-- WebcamSource
    CameraSource <|-- USBAnySource
    CameraSource <|-- AndroidWiFiSource
    CameraSource <|-- AndroidUSBSource
    CameraSource <|-- iPhoneWiFiSource
    CameraSource <|-- iPhoneUSBSource
    CameraSource <|-- IPCameraSource
    CameraSource <|-- FakeCameraSource
```

## 22.3 Service & Dashboard Classes

```mermaid
classDiagram
    class RecognitionService {
        +detector: FaceDetector
        +recognizer: FaceRecognizer
        +enrollment: FaceEnrollment
        +amfr: AMFREngine
        -_marked_this_session: set
        +process_frame(frame) np.ndarray
        +process_frame_detailed(frame) tuple
        +with_shared_models(models) RecognitionService
        +reset_tracking() None
        +status() dict
        -_maybe_mark_attendance(name, employee_id, confidence) bool
        -_log_recognition(...) None
        -_handle_unknown_face(face_img) None
    }

    class AttendanceService {
        +mark(employee_id, confidence, camera_id, operator, employee_name) bool
        +get_today() List
        +get_by_date(date) List
        +get_by_employee(id) List
        +get_statistics() dict
        +to_dict(record) dict
    }

    class EmployeeService {
        +create(...) Employee
        +get_by_name(name) Employee
        +update(employee_id, name, department) Employee
        +delete(employee_id) bool
        +remove_faiss_embedding(name, fallback) bool
        +count() int
    }

    class UnknownFaceService {
        +get_statistics() dict
        +get_filtered(...) List
        +convert_to_employee(face_id, employee_id, name, department) bool
        +delete_all() int
        +auto_cleanup(days) int
    }

    class AuditService {
        +log(action, description, operator, employee_id) None
        +get_recent(limit) list
        +get_by_action(action) list
    }

    class BruteForceProtection {
        +is_locked_out(username, ip) tuple
        +record_failed_attempt(...) None
        +record_successful_login(...) None
        +get_lockout_info(username) dict
        +cleanup_old_attempts() int
    }

    class MFAService {
        +generate_secret(email) tuple
        +verify_totp(secret, code) bool
        +generate_backup_codes() tuple
        +verify_backup_code(hashes, code) tuple
        +enroll_user(user) tuple
        +requires_mfa(user) bool
    }

    class OIDCService {
        +enabled: bool
        +get_login_url(request, state) str
        +handle_callback(code, state, expected) OIDCUserInfo
        +sync_user(user_info) User
    }

    class LiveRecognitionPipeline {
        +source_type: str
        -_cam: CameraSource
        -_service: RecognitionService
        -_threads: list
        -_verified_at: dict
        +start() bool
        +stop() None
        +fps: float
        +ai_fps: float
        +pipeline_latency: float
        +people_count: int
        +status: str
        +latency_stats() dict
        -_capture_loop() None
        -_recognition_worker() None
        -_latency_loop() None
    }

    class SharedModelResources {
        +service: RecognitionService
        +load() SharedModelResources
    }

    class CameraOwner {
        -_instance: CameraOwner
        +get() CameraOwner
        +can_acquire() bool
        +acquire(camera, pipeline) bool
        +release() None
        +is_owned() bool
        +get_status() dict
    }

    class FrameBuffer {
        +put(frame) int
        +get() np.ndarray
        +get_with_meta() tuple
        +close() None
        +has_frame() bool
    }

    class LatencyLogger {
        +record(ms) None
        +stats() dict
        +p50() float
        +p95() float
    }

    LiveRecognitionPipeline --> RecognitionService
    LiveRecognitionPipeline --> CameraSource
    LiveRecognitionPipeline --> LatencyLogger
    LiveRecognitionPipeline --> SharedModelResources
    LiveRecognitionPipeline --> FrameBuffer
    CameraOwner --> LiveRecognitionPipeline : owns
```

## 22.4 ORM Models (summary — full schema in §8)

```mermaid
classDiagram
    class User {
        +id, username, email, password_hash
        +oidc_sub, oidc_provider, auth_method
        +is_mfa_enabled, mfa_totp_secret, mfa_backup_codes
        +is_active, last_login_at, created_at, updated_at
    }
    class Role { +id, name, description }
    class Permission { +id, resource, action }
    class RefreshToken { +id, user_id, token_hash, expires_at, revoked_at }
    class Student { +id, student_id, name, department_id, is_active }
    class Staff { +id, employee_id, name, department_id }
    class Employee { +id, employee_id, name, department, faiss_id }
    class Department { +id, institution_id, name, code, head_id }
    class Course { +id, department_id, code, name, credits }
    class Section { +id, course_id, section_name, semester, year }
    class Enrollment { +id, student_id, section_id, status }
    class Timetable { +id, section_id, classroom_id, day_of_week, start_time, end_time }
    class Classroom { +id, institution_id, building, room_number }
    class Camera { +id, camera_id, stream_url, status, is_active }
    class Attendance { +id, student_id, employee_id, timestamp, confidence, status }
    class RecognitionLog { +id, is_known, confidence, is_spoof, timestamp }
    class UnknownFace { +id, image_path, reviewed, converted_to_employee }
    class AuditLog { +id, action, actor, timestamp, severity }

    User "1" --> "0..*" RefreshToken
    User "1" --> "0..*" Attendance : marked_by
    User "1" --> "0..*" UnknownFace : reviewed
    User "1" --> "0..*" Role : user_roles
    Role "1" --> "0..*" Permission : role_permissions
    Department "1" --> "0..*" Course
    Course "1" --> "0..*" Section
    Section "1" --> "0..*" Timetable
    Classroom "1" --> "0..*" Timetable
    Student "1" --> "0..*" Enrollment
    Section "1" --> "0..*" Enrollment
    Student "1" --> "0..*" Attendance
    Camera "1" --> "0..*" Attendance
    Employee "1" --> "0..*" Attendance
    Employee "1" --> "0..*" RecognitionLog
    Camera "1" --> "0..*" UnknownFace
```

---

*References: class definitions in `app/*`, `camera/*`, `services/*`,
`dashboard/*`, `database/models.py`*
