import XCTest
@testable import FaceRecognitionAttendance

final class KeychainTests: XCTestCase {
    let testKey = "test_auth_token_key"
    
    override func setUp() {
        super.setUp()
        KeychainHelper.shared.delete(key: testKey)
    }
    
    override func tearDown() {
        KeychainHelper.shared.delete(key: testKey)
        super.tearDown()
    }
    
    func testSaveAndReadString() {
        let token = "jwt-secret-token-xyz-987"
        let saved = KeychainHelper.shared.saveString(key: testKey, value: token)
        XCTAssertTrue(saved, "Saving token to Keychain should succeed")
        
        let retrieved = KeychainHelper.shared.readString(key: testKey)
        XCTAssertEqual(retrieved, token, "Retrieved token must match the saved token")
    }
    
    func testOverwriteExistingKey() {
        KeychainHelper.shared.saveString(key: testKey, value: "initial-token")
        let updated = KeychainHelper.shared.saveString(key: testKey, value: "refreshed-token")
        XCTAssertTrue(updated, "Overwriting existing key in Keychain should succeed")
        
        let retrieved = KeychainHelper.shared.readString(key: testKey)
        XCTAssertEqual(retrieved, "refreshed-token", "Retrieved token must reflect updated value")
    }
    
    func testDeleteKey() {
        KeychainHelper.shared.saveString(key: testKey, value: "to-be-deleted")
        let deleted = KeychainHelper.shared.delete(key: testKey)
        XCTAssertTrue(deleted, "Deleting existing key should return true")
        
        let retrieved = KeychainHelper.shared.readString(key: testKey)
        XCTAssertNil(retrieved, "Deleted key should return nil")
    }
    
    func testReadNonExistentKey() {
        let nonExistent = KeychainHelper.shared.readString(key: "non_existent_random_key_123")
        XCTAssertNil(nonExistent, "Non-existent key must return nil")
    }
}

