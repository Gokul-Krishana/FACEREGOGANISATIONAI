import Foundation

public struct UserSession: Codable {
    public let accessToken: String
    public let tokenType: String
    public let username: String
    public let role: String?
    
    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case username
        case role
    }
    
    public init(accessToken: String, tokenType: String = "bearer", username: String, role: String? = nil) {
        self.accessToken = accessToken
        self.tokenType = tokenType
        self.username = username
        self.role = role
    }
}

public struct AttendanceSubmissionResponse: Codable {
    public let status: String
    public let employeeId: String?
    public let employeeName: String?
    public let message: String
    public let timestamp: String?
    
    enum CodingKeys: String, CodingKey {
        case status
        case employeeId = "employee_id"
        case employeeName = "employee_name"
        case message
        case timestamp
    }
}
