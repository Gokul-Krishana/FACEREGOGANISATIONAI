import Foundation

public final class AttendanceAPIService: ObservableObject {
    public static let shared = AttendanceAPIService()
    
    @Published public var isAuthenticated = false
    @Published public var currentSession: UserSession?
    @Published public var lastError: String?
    
    public var baseURL = URL(string: "http://127.0.0.1:8000")!
    
    public init() {}
    
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
            DispatchQueue.main.async {
                self.currentSession = session
                self.isAuthenticated = true
                self.lastError = nil
            }
            return session
        } else {
            let errorMsg = "Login failed with HTTP \(httpResponse.statusCode)"
            DispatchQueue.main.async { self.lastError = errorMsg }
            throw NSError(domain: "AttendanceAPI", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: errorMsg])
        }
    }
    
    public func submitAttendance(employeeCode: String, cameraLabel: String = "iOS-Mobile") async throws -> Bool {
        guard let token = currentSession?.accessToken else {
            throw NSError(domain: "AttendanceAPI", code: 401, userInfo: [NSLocalizedDescriptionKey: "Unauthenticated"])
        }
        
        let endpoint = baseURL.appendingPathComponent("/attendance")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let payload: [String: Any] = [
            "employee_id": employeeCode,
            "confidence": 0.98,
            "method": "FACE_RECOGNITION_IOS",
            "status": "PRESENT"
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        return httpResponse.statusCode == 200 || httpResponse.statusCode == 201
    }
}
