# Face Recognition Attendance — Native iOS Application

Native Apple iOS client for the Face Recognition Attendance System 2.0.

Built with **Swift 5.9**, **SwiftUI**, and **AVFoundation**, providing real-time mobile camera capture, JWT session management, and integration with the FastAPI backend.

---

## 1. Architecture Overview

```
ios/FaceRecognitionAttendance/
├── Package.swift               # Swift Package Manager definition
├── README.md                   # iOS documentation & build instructions
└── Sources/
    ├── Models/
    │   └── UserSession.swift   # Codable JWT & response models
    ├── Services/
    │   ├── APIService.swift    # Asynchronous REST communication via URLSession
    │   └── AVCaptureService.swift # AVFoundation 60 FPS front-camera session
    └── Views/
        └── CameraView.swift    # SwiftUI camera preview and visual overlay
```

---

## 2. Requirements

- **macOS:** macOS Sonoma (14.0+) or later.
- **Xcode:** Xcode 15.0 or later.
- **iOS Target:** iOS 16.0 minimum deployment target.
- **Device Support:** iPhone & iPad (requires front-facing camera).

---

## 3. Building in Xcode

1. Open Xcode on macOS:
   ```bash
   cd ios/FaceRecognitionAttendance
   open Package.swift
   ```
2. In Xcode, configure your **Signing & Capabilities** with your Apple Developer Team ID.
3. In `Info.plist`, ensure camera permissions are declared:
   ```xml
   <key>NSCameraUsageDescription</key>
   <string>Face Recognition Attendance requires camera access for live check-in.</string>
   ```
4. Configure the FastAPI backend endpoint in `APIService.swift`:
   ```swift
   AttendanceAPIService.shared.baseURL = URL(string: "http://<SERVER_IP>:8000")!
   ```
5. Select your connected iPhone as the deployment target and press **Cmd + R** to run.

---

## 4. Zero Regression Guarantee for Windows

- This iOS package is completely self-contained.
- It requires no Python packages, Swift bridges, or system modifications on the Windows host.
- The FastAPI backend serves both Windows desktop clients and iOS mobile clients via standardized REST endpoints.
