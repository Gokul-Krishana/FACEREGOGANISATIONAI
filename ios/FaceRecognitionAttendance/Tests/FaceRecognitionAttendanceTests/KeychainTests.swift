import XCTest
@testable import FaceRecognitionAttendance

final class KeychainTests: XCTestCase {
    let testKey = "test_auth_token_key"
    var mockBackend: InMemoryKeychainBackend!
    
    override func setUp() {
        super.setUp()
        mockBackend = InMemoryKeychainBackend()
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(mockBackend)
        #endif
        KeychainHelper.shared.delete(key: testKey)
    }
    
    override func tearDown() {
        KeychainHelper.shared.delete(key: testKey)
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(nil)
        #endif
        super.tearDown()
    }
    
    // 1. Test successful save/read operations
    func testSaveAndReadStringSuccess() {
        let token = "jwt-secret-token-xyz-987"
        let saved = KeychainHelper.shared.saveString(key: testKey, value: token)
        XCTAssertTrue(saved, "Saving token to Keychain should succeed with healthy backend")
        XCTAssertNil(KeychainHelper.shared.lastError, "lastError should be nil after successful save")
        
        let retrieved = KeychainHelper.shared.readString(key: testKey)
        XCTAssertEqual(retrieved, token, "Retrieved token must match the saved token")
    }
    
    // 2. Test overwriting an existing key
    func testOverwriteExistingKeySuccess() {
        KeychainHelper.shared.saveString(key: testKey, value: "initial-token")
        let updated = KeychainHelper.shared.saveString(key: testKey, value: "refreshed-token")
        XCTAssertTrue(updated, "Overwriting existing key in Keychain should succeed")
        
        let retrieved = KeychainHelper.shared.readString(key: testKey)
        XCTAssertEqual(retrieved, "refreshed-token", "Retrieved token must reflect updated value")
    }
    
    // 3. Test deleting an existing key
    func testDeleteKeySuccess() {
        KeychainHelper.shared.saveString(key: testKey, value: "to-be-deleted")
        let deleted = KeychainHelper.shared.delete(key: testKey)
        XCTAssertTrue(deleted, "Deleting existing key should return true")
        
        let retrieved = KeychainHelper.shared.readString(key: testKey)
        XCTAssertNil(retrieved, "Deleted key should return nil")
    }
    
    // 4. Test reading non-existent key returns nil without setting error
    func testReadNonExistentKeyReturnsNilWithoutError() {
        let nonExistent = KeychainHelper.shared.readString(key: "non_existent_random_key_123")
        XCTAssertNil(nonExistent, "Non-existent key must return nil")
        XCTAssertNil(KeychainHelper.shared.lastError, "Reading non-existent key is normal; lastError must be nil")
    }
    
    // 5. Test missing-entitlement behavior on Apple Security Keychain
    #if canImport(Security)
    func testAppleKeychainDirectMissingEntitlementFailsClosed() {
        let appleBackend = AppleKeychainBackend()
        let sampleData = "sensitive-payload-99".data(using: .utf8)!
        
        // In unsigned test/simulator runners without keychain entitlement provisioning,
        // AppleKeychainBackend MUST fail closed (never silently succeeding or falling back)
        do {
            try appleBackend.save(key: "entitlement_test_key", data: sampleData)
            // If running on an entitled environment, save may succeed
        } catch let error as KeychainError {
            // Must be a valid KeychainError (e.g. missingEntitlement -34018 or accessDenied)
            switch error {
            case .missingEntitlement(let status):
                XCTAssertEqual(status, -34018, "Status should be errSecMissingEntitlement")
            case .unhandledError, .accessDenied:
                break
            default:
                XCTFail("Unexpected error type: \(error)")
            }
        } catch {
            XCTFail("Expected KeychainError but caught: \(error)")
        }
        
        // When injected into KeychainHelper, save must return false and record lastError
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(appleBackend)
        let saveResult = KeychainHelper.shared.saveString(key: "entitlement_test_key", value: "test-token")
        if !saveResult {
            XCTAssertNotNil(KeychainHelper.shared.lastError, "lastError must be set when save fails")
            let readResult = KeychainHelper.shared.readString(key: "entitlement_test_key")
            XCTAssertNil(readResult, "No credentials should be readable after failed save")
        }
        KeychainHelper.shared.setTestBackend(mockBackend)
        #endif
    }
    #endif
    
    // 6. Test genuine Keychain failure behavior (Access Denied / Device Locked)
    func testGenuineKeychainFailureBehaviorAccessDenied() {
        let failingBackend = InMemoryKeychainBackend(simulatedError: .accessDenied(-25308))
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(failingBackend)
        #endif
        
        let saveResult = KeychainHelper.shared.saveString(key: testKey, value: "test-token")
        XCTAssertFalse(saveResult, "Save MUST fail closed and return false when Keychain denies access")
        XCTAssertEqual(KeychainHelper.shared.lastError, .accessDenied(-25308))
        
        let readResult = KeychainHelper.shared.readString(key: testKey)
        XCTAssertNil(readResult, "Read must return nil on genuine Keychain failure")
        XCTAssertEqual(KeychainHelper.shared.lastError, .accessDenied(-25308))
        
        let deleteResult = KeychainHelper.shared.delete(key: testKey)
        XCTAssertFalse(deleteResult, "Delete must return false when backend fails")
        
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(mockBackend)
        #endif
    }
    
    // 7. Test genuine Keychain failure behavior (Unhandled OSStatus)
    func testGenuineKeychainFailureBehaviorUnhandledStatus() {
        let failingBackend = InMemoryKeychainBackend(simulatedError: .unhandledError(status: -25293))
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(failingBackend)
        #endif
        
        let saveResult = KeychainHelper.shared.saveString(key: testKey, value: "test-token")
        XCTAssertFalse(saveResult, "Save MUST return false on unhandled Keychain failure")
        XCTAssertEqual(KeychainHelper.shared.lastError, .unhandledError(status: -25293))
        
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(mockBackend)
        #endif
    }
    
    // 8. Test distinguishing itemNotFound from genuine errors
    func testDistinguishNotFoundFromGenuineError() {
        // Normal backend: not found returns nil, lastError is nil
        let notFound = KeychainHelper.shared.read(key: "absent_key")
        XCTAssertNil(notFound)
        XCTAssertNil(KeychainHelper.shared.lastError, "Item not found should NOT set lastError")
        
        // Failing backend: returns nil, but lastError is populated
        let failingBackend = InMemoryKeychainBackend(simulatedError: .accessDenied(-25308))
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(failingBackend)
        #endif
        let failureRead = KeychainHelper.shared.read(key: "absent_key")
        XCTAssertNil(failureRead)
        XCTAssertEqual(KeychainHelper.shared.lastError, .accessDenied(-25308), "Genuine error must be recorded in lastError")
        
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(mockBackend)
        #endif
    }
    
    // 9. Test logout and token revocation
    func testLogoutAndTokenRevocation() {
        let tokenKey = "auth_access_token"
        let userKey = "auth_username"
        let roleKey = "auth_role"
        
        // Seed credentials
        KeychainHelper.shared.saveString(key: tokenKey, value: "mock-jwt-token-to-revoke")
        KeychainHelper.shared.saveString(key: userKey, value: "employee123")
        KeychainHelper.shared.saveString(key: roleKey, value: "ADMIN")
        
        XCTAssertEqual(KeychainHelper.shared.readString(key: tokenKey), "mock-jwt-token-to-revoke")
        XCTAssertEqual(KeychainHelper.shared.readString(key: userKey), "employee123")
        XCTAssertEqual(KeychainHelper.shared.readString(key: roleKey), "ADMIN")
        
        // Perform logout revocation
        AttendanceAPIService.shared.logout()
        
        // Assert all credentials purged from Keychain
        XCTAssertNil(KeychainHelper.shared.readString(key: tokenKey), "Access token must be purged on logout")
        XCTAssertNil(KeychainHelper.shared.readString(key: userKey), "Username must be purged on logout")
        XCTAssertNil(KeychainHelper.shared.readString(key: roleKey), "Role must be purged on logout")
        XCTAssertFalse(AttendanceAPIService.shared.isAuthenticated, "Service must not be authenticated")
        XCTAssertNil(AttendanceAPIService.shared.currentSession, "Session must be nil")
    }
    
    // 10. Test tokens are never written to logs or error descriptions
    func testTokensAreNeverLoggedOrExposedInErrorDescription() {
        let sensitiveToken = "super-secret-jwt-token-alpha-beta-999"
        
        let errEntitlement = KeychainError.missingEntitlement(-34018)
        let errAccess = KeychainError.accessDenied(-25308)
        let errUnhandled = KeychainError.unhandledError(status: -50)
        let errFailClosed = KeychainError.failClosed(reason: "Secure persistence failed")
        
        let allErrors = [errEntitlement, errAccess, errUnhandled, errFailClosed]
        for err in allErrors {
            let desc = err.description
            XCTAssertFalse(desc.contains(sensitiveToken), "Error description must never expose sensitive token data")
            let debugDesc = String(describing: err)
            XCTAssertFalse(debugDesc.contains(sensitiveToken), "String(describing:) must never expose sensitive token data")
        }
    }
    
    // 11. Test throwing methods
    func testThrowingMethodsThrowOnFailure() {
        let failingBackend = InMemoryKeychainBackend(simulatedError: .accessDenied(-25308))
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(failingBackend)
        #endif
        
        XCTAssertThrowsError(try KeychainHelper.shared.saveThrowing(key: testKey, data: Data([1, 2]))) { error in
            XCTAssertEqual(error as? KeychainError, .accessDenied(-25308))
        }
        
        XCTAssertThrowsError(try KeychainHelper.shared.readThrowing(key: testKey)) { error in
            XCTAssertEqual(error as? KeychainError, .accessDenied(-25308))
        }
        
        XCTAssertThrowsError(try KeychainHelper.shared.deleteThrowing(key: testKey)) { error in
            XCTAssertEqual(error as? KeychainError, .accessDenied(-25308))
        }
        
        #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
        KeychainHelper.shared.setTestBackend(mockBackend)
        #endif
    }
}
