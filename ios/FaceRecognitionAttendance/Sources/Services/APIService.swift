import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking

extension URLSession {
    public func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        try await withCheckedThrowingContinuation { continuation in
            let task = self.dataTask(with: request) { data, response, error in
                if let error = error {
                    continuation.resume(throwing: error)
                } else if let data = data, let response = response {
                    continuation.resume(returning: (data, response))
                } else {
                    continuation.resume(throwing: URLError(.badServerResponse))
                }
            }
            task.resume()
        }
    }
}
#endif
#if canImport(Combine)
import Combine
#endif
#if canImport(UIKit)
import UIKit
#endif

#if canImport(Combine)
public final class AttendanceAPIService: ObservableObject {
    public static let shared = AttendanceAPIService()
    
    private let tokenKey = "auth_access_token"
    private let userKey = "auth_username"
    private let roleKey = "auth_role"
    
    @Published public var isAuthenticated = false
    @Published public var currentSession: UserSession?
    @Published public var lastError: String?
    
    public var baseURL = URL(string: "http://127.0.0.1:8000")!
    
    public init() {
        restoreSessionFromKeychain()
    }
    
    /// Attempt to restore existing JWT session from secure iOS Keychain
    public func restoreSessionFromKeychain() {
        guard let token = KeychainHelper.shared.readString(key: tokenKey),
              let username = KeychainHelper.shared.readString(key: userKey) else {
            return
        }
        let role = KeychainHelper.shared.readString(key: roleKey)
        let session = UserSession(accessToken: token, tokenType: "bearer", username: username, role: role)
        self.currentSession = session
        self.isAuthenticated = true
    }
    
    /// Perform authentication and securely persist token to iOS Keychain
    public func login(username: String, password: String) async throws -> UserSession {
        let endpoint = baseURL.appendingPathComponent("/auth/login")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = ["username": username, "password": password]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        if httpResponse.statusCode == 200 {
            let session = try JSONDecoder().decode(UserSession.self, from: data)
            
            // Persist to iOS Keychain
            KeychainHelper.shared.saveString(key: tokenKey, value: session.accessToken)
            KeychainHelper.shared.saveString(key: userKey, value: session.username)
            if let role = session.role {
                KeychainHelper.shared.saveString(key: roleKey, value: role)
            }
            
            await MainActor.run {
                self.currentSession = session
                self.isAuthenticated = true
                self.lastError = nil
            }
            return session
        } else {
            let errorMsg = "Login failed with HTTP \(httpResponse.statusCode)"
            await MainActor.run { self.lastError = errorMsg }
            throw NSError(domain: "AttendanceAPI", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: errorMsg])
        }
    }
    
    /// Log out and purge tokens from iOS Keychain
    public func logout() {
        KeychainHelper.shared.delete(key: tokenKey)
        KeychainHelper.shared.delete(key: userKey)
        KeychainHelper.shared.delete(key: roleKey)
        
        DispatchQueue.main.async {
            self.currentSession = nil
            self.isAuthenticated = false
            self.lastError = nil
        }
    }
    
    /// Submit attendance to backend (backend enforces identity, timetable, liveness, duplicate prevention)
    public func submitAttendance(
        studentId: Int,
        confidence: Double = 0.98,
        method: String = "FACE_RECOGNITION_IOS",
        status: String = "PRESENT"
    ) async throws -> Bool {
        guard let token = currentSession?.accessToken else {
            throw NSError(domain: "AttendanceAPI", code: 401, userInfo: [NSLocalizedDescriptionKey: "Unauthenticated"])
        }
        
        let endpoint = baseURL.appendingPathComponent("/attendance")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let payload: [String: Any] = [
            "student_id": studentId,
            "confidence": confidence,
            "method": method,
            "status": status
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        return httpResponse.statusCode == 200 || httpResponse.statusCode == 201
    }
    
    #if canImport(UIKit)
    /// Verify captured frame and submit attendance via backend AI engine (MiniFASNetV2 + ArcFace)
    public func verifyFaceFrame(image: UIImage) async throws -> Data {
        guard let token = currentSession?.accessToken else {
            throw NSError(domain: "AttendanceAPI", code: 401, userInfo: [NSLocalizedDescriptionKey: "Unauthenticated"])
        }
        guard let imageData = image.jpegData(compressionQuality: 0.85) else {
            throw NSError(domain: "AttendanceAPI", code: 400, userInfo: [NSLocalizedDescriptionKey: "JPEG encoding failed"])
        }
        
        let boundary = "Boundary-\(UUID().uuidString)"
        let endpoint = baseURL.appendingPathComponent("/attendance/verify-frame")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"frame\"; filename=\"capture.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = body
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return data
    }
    #endif
}
#else
public final class AttendanceAPIService {
    public static let shared = AttendanceAPIService()
    
    private let tokenKey = "auth_access_token"
    private let userKey = "auth_username"
    private let roleKey = "auth_role"
    
    public var isAuthenticated = false
    public var currentSession: UserSession?
    public var lastError: String?
    
    public var baseURL = URL(string: "http://127.0.0.1:8000")!
    
    public init() {
        restoreSessionFromKeychain()
    }
    
    public func restoreSessionFromKeychain() {
        guard let token = KeychainHelper.shared.readString(key: tokenKey),
              let username = KeychainHelper.shared.readString(key: userKey) else {
            return
        }
        let role = KeychainHelper.shared.readString(key: roleKey)
        let session = UserSession(accessToken: token, tokenType: "bearer", username: username, role: role)
        self.currentSession = session
        self.isAuthenticated = true
    }
    
    public func login(username: String, password: String) async throws -> UserSession {
        let endpoint = baseURL.appendingPathComponent("/auth/login")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = ["username": username, "password": password]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        if httpResponse.statusCode == 200 {
            let session = try JSONDecoder().decode(UserSession.self, from: data)
            KeychainHelper.shared.saveString(key: tokenKey, value: session.accessToken)
            KeychainHelper.shared.saveString(key: userKey, value: session.username)
            if let role = session.role {
                KeychainHelper.shared.saveString(key: roleKey, value: role)
            }
            self.currentSession = session
            self.isAuthenticated = true
            self.lastError = nil
            return session
        } else {
            let errorMsg = "Login failed with HTTP \(httpResponse.statusCode)"
            self.lastError = errorMsg
            throw NSError(domain: "AttendanceAPI", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: errorMsg])
        }
    }
    
    public func logout() {
        KeychainHelper.shared.delete(key: tokenKey)
        KeychainHelper.shared.delete(key: userKey)
        KeychainHelper.shared.delete(key: roleKey)
        self.currentSession = nil
        self.isAuthenticated = false
        self.lastError = nil
    }
    
    public func submitAttendance(
        studentId: Int,
        confidence: Double = 0.98,
        method: String = "FACE_RECOGNITION_IOS",
        status: String = "PRESENT"
    ) async throws -> Bool {
        guard let token = currentSession?.accessToken else {
            throw NSError(domain: "AttendanceAPI", code: 401, userInfo: [NSLocalizedDescriptionKey: "Unauthenticated"])
        }
        
        let endpoint = baseURL.appendingPathComponent("/attendance")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let payload: [String: Any] = [
            "student_id": studentId,
            "confidence": confidence,
            "method": method,
            "status": status
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        return httpResponse.statusCode == 200 || httpResponse.statusCode == 201
    }
}
#endif
