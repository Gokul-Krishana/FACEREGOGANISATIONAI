import XCTest
@testable import FaceRecognitionAttendance

final class ModelTests: XCTestCase {
    func testUserSessionDecoding() throws {
        let json = """
        {
            "access_token": "mock-jwt-token-12345",
            "token_type": "bearer",
            "username": "admin",
            "role": "ADMIN"
        }
        """.data(using: .utf8)!
        
        let session = try JSONDecoder().decode(UserSession.self, from: json)
        XCTAssertEqual(session.accessToken, "mock-jwt-token-12345")
        XCTAssertEqual(session.tokenType, "bearer")
        XCTAssertEqual(session.username, "admin")
        XCTAssertEqual(session.role, "ADMIN")
    }
    
    func testAttendanceSubmissionResponseDecoding() throws {
        let json = """
        {
            "status": "SUCCESS",
            "employee_id": "EMP001",
            "employee_name": "Gokul",
            "message": "Attendance marked successfully",
            "timestamp": "2026-11-21T09:00:00Z"
        }
        """.data(using: .utf8)!
        
        let response = try JSONDecoder().decode(AttendanceSubmissionResponse.self, from: json)
        XCTAssertEqual(response.status, "SUCCESS")
        XCTAssertEqual(response.employeeId, "EMP001")
        XCTAssertEqual(response.employeeName, "Gokul")
    }
}
