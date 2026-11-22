import XCTest
@testable import FaceRecognitionAttendance

final class APIServiceTests: XCTestCase {
    override func setUp() {
        super.setUp()
        #if DEBUG && (targetEnvironment(simulator) || !canImport(Security))
        KeychainHelper.shared.setTestBackend(InMemoryKeychainBackend())
        #endif
    }
    
    func testAPIServiceInitialState() {
        let service = AttendanceAPIService()
        service.logout()
        XCTAssertFalse(service.isAuthenticated, "Service should not be authenticated after logout")
        XCTAssertNil(service.currentSession, "Current session should be nil after logout")
    }
    
    func testBaseURLConfiguration() {
        let service = AttendanceAPIService()
        let customURL = URL(string: "https://attendance.company.com:8443")!
        service.baseURL = customURL
        XCTAssertEqual(service.baseURL.absoluteString, "https://attendance.company.com:8443")
    }
    
    func testUnauthenticatedAttendanceSubmissionThrows() async {
        let service = AttendanceAPIService()
        service.logout()
        
        do {
            _ = try await service.submitAttendance(studentId: 999)
            XCTFail("Submitting attendance without authentication must throw an error")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("Unauthenticated") || (error as NSError).code == 401)
        }
    }
}

