# Section 23 — Complete Module Diagram

## 23.1 Module Dependency Diagram (Mermaid)

```mermaid
flowchart TB
    subgraph UI["PRESENTATION"]
        DASH["dashboard/app.py"]
        P1["01_Dashboard"]
        P2["02_Employees"]
        P3["03_Enroll"]
        P4["04_Live"]
        P5["05_Attendance"]
        P6["06_Unknown"]
        P7["07_Analytics"]
        P8["08_Settings"]
        P9["09_Health"]
        P10["10_About"]
        FB["dashboard/frame_buffer.py"]
        CO["dashboard/camera_owner.py"]
        LL["dashboard/latency_logger.py"]
    end

    subgraph API["API LAYER"]
        FAST["api/main.py"]
        JQ["api/job_queue.py"]
        WS["api/websocket_manager.py"]
        RC["api/redis_client.py"]
        BO["api/bulk_operations.py"]
        ATTAPI["api/attendance_service.py"]
        AUDA["api/audit_service.py"]
    end

    subgraph SVC["SERVICE LAYER"]
        RS["services/recognition_service.py"]
        AS["services/attendance_service.py"]
        ES["services/employee_service.py"]
        UFS["services/unknown_face_service.py"]
        AUD["services/audit_service.py"]
        BFP["services/brute_force_protection.py"]
        MFA["services/mfa_service.py"]
        OIDC["services/oidc_service.py"]
    end

    subgraph AI["AI PIPELINE"]
        AMFR["app/amfr_engine.py"]
        FD["app/face_detector.py"]
        REC["app/recognizer.py"]
        ENR["app/enrollment.py"]
        FQ["app/face_quality.py"]
        LD["app/liveness_detector.py"]
        DL["app/deep_liveness.py"]
        TRK["app/tracking.py"]
        AT["app/attendance.py"]
        LDET["app/live_detection.py"]
        ALG["recognition/alignment.py"]
    end

    subgraph CAM["CAMERA LAYER"]
        CB["camera/base.py"]
        CW["camera/webcam.py"]
        CP["camera/phone.py"]
        CS["camera/selector.py"]
        CD["camera/discovery.py"]
        CF["camera/fake.py"]
    end

    subgraph DB["DATA LAYER"]
        DBX["database/database.py"]
        MOD["database/models.py"]
        REP["database/repository.py"]
        ALE["alembic/*"]
        FA["FAISS index + metadata.json"]
        CSV["attendance/ CSV files"]
    end

    subgraph CFG["CONFIG"]
        CC["config/config.py"]
        YML["config/settings.yaml"]
        UT["utils/upload_security.py"]
        UI2["utils/image.py"]
    end

    %% UI → services
    P1 --> AS
    P1 --> ES
    P1 --> UFS
    P1 --> REP
    P2 --> ES
    P2 --> AS
    P3 --> ENR
    P3 --> REC
    P3 --> ES
    P4 --> RS
    P4 --> AS
    P4 --> CO
    P4 --> FB
    P4 --> LL
    P4 --> CS
    P4 --> CD
    P5 --> LDET
    P5 --> AS
    P5 --> CS
    P6 --> UFS
    P7 --> REP
    P8 --> CC
    P8 --> CS
    P9 --> CC
    P9 --> CS
    DASH --> P1

    %% Dashboard infra
    CO --> FB
    P4 --> CO

    %% Services → AI / DB
    RS --> AMFR
    RS --> FD
    RS --> REC
    RS --> ENR
    RS --> AS
    RS --> AUD
    RS --> REP
    AS --> AT
    AS --> REP
    AS --> AUD
    ES --> REP
    ES --> AUD
    ES -.-> ENR   %% FAISS rename/delete sync
    UFS --> REP
    UFS --> AUD
    UFS -.-> REC  %% convert: embedding
    UFS -.-> ENR  %% convert: FAISS add
    AUD --> REP
    BFP --> REP
    MFA --> DBX
    OIDC --> DBX

    %% AI internal
    AMFR --> FQ
    AMFR --> LD
    AMFR --> TRK
    LD --> DL
    LDET --> AMFR
    LDET --> FD
    LDET --> REC
    LDET --> ENR
    LDET --> AT
    LDET --> CS
    LDET --> REP
    REC --> ALG

    %% Camera factory
    CS --> CW
    CS --> CP
    CS --> CF
    CW --> CB
    CP --> CB
    CD --> CB

    %% API → services/db
    FAST --> RS
    FAST --> ES
    FAST --> AS
    FAST --> BFP
    FAST --> MFA
    FAST --> OIDC
    FAST --> JQ
    FAST --> WS
    FAST --> RC
    FAST --> BO
    FAST --> REP
    FAST --> UT
    JQ --> DBX
    BO --> DBX

    %% Config
    FD --> CC
    REC --> CC
    ENR --> CC
    FQ --> CC
    LD --> CC
    DL --> CC
    AMFR --> CC
    AT --> CC
    CC --> YML
    UI2 --> UT

    %% Data layer
    REP --> MOD
    REP --> DBX
    MOD --> DBX
    DBX --> ALE
    ENR --> FA
    AS --> CSV
    RC --> REDIS["Redis"]
    DBX --> SQL[(SQLite/PostgreSQL)]
```

## 23.2 Dependency Rules (architecture constraints)

| Rule | Enforced by |
|------|-------------|
| UI/API never touch AI modules directly | `services/recognition_service.py` is the only sanctioned entry |
| Only `camera/webcam.py` + `camera/phone.py` own `cv2.VideoCapture` | documented convention + `CameraOwner` singleton |
| Repositories are the only SQL layer | services call repos; pages use services/repos via cached helpers |
| Config is centralized | every module imports `config.config` constants |
| FAISS ↔ DB consistency | `EmployeeService` rename/delete sync |
| One active camera pipeline | `CameraOwner.acquire()` |

## 23.3 Layer Dependency Matrix (who depends on whom)

| Layer | Depends on |
|-------|-----------|
| Presentation (dashboard/) | services/, database/repository, camera/, config/, app/ (via services) |
| API (api/) | services/, database/, utils/, api/* helpers |
| Services (services/) | database/, app/ (sparingly), config/ |
| AI pipeline (app/) | config/, camera/ (only live_detection), database/ (only live_detection + recognition_service) |
| Camera (camera/) | config/ (via consumers), base |
| Data (database/) | config/, alembic |
| Config (config/) | nothing internal |

## 23.4 Circular Dependency Note

`app/live_detection.py` imports from `database/` and `services/`, while
`services/recognition_service.py` imports from `app/`. This creates a
soft cycle at import time; it works because imports are deferred inside
functions/methods where needed (e.g. `_log_attendance_db` imports
`get_session` inside the method) and Python's module cache handles the
order. Documented here for maintainers: prefer services→app one-way imports
going forward (the dashboard path already does this correctly via
`RecognitionService`).

---

*References: import statements across `app/*`, `services/*`, `api/*`,
`dashboard/*`, `camera/*`, `database/*`*
