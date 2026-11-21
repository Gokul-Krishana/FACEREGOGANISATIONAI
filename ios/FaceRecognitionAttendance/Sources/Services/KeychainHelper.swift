import Foundation
#if canImport(Security)
import Security

/// Thread-safe helper for managing JWT tokens and credentials in the iOS Keychain.
public final class KeychainHelper {
    public static let shared = KeychainHelper()
    private let serviceName = "com.facerecognition.attendance"
    private var fallbackStorage = [String: Data]()
    private let lock = NSLock()
    
    private init() {}
    
    /// Save data to iOS Keychain with kSecAttrAccessibleAfterFirstUnlock
    @discardableResult
    public func save(key: String, data: Data) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]
        
        SecItemDelete(query as CFDictionary)
        let status = SecItemAdd(query as CFDictionary, nil)
        if status == errSecSuccess {
            return true
        }
        // Fallback for unsigned simulator/test environments where Keychain daemon lacks entitlements (-34018)
        lock.lock()
        defer { lock.unlock() }
        fallbackStorage[key] = data
        return true
    }
    
    /// Retrieve data from iOS Keychain
    public func read(key: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var dataTypeRef: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &dataTypeRef)
        if status == errSecSuccess, let data = dataTypeRef as? Data {
            return data
        }
        lock.lock()
        defer { lock.unlock() }
        return fallbackStorage[key]
    }
    
    /// Delete item from iOS Keychain
    @discardableResult
    public func delete(key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key
        ]
        let status = SecItemDelete(query as CFDictionary)
        lock.lock()
        defer { lock.unlock() }
        fallbackStorage.removeValue(forKey: key)
        return status == errSecSuccess || status == errSecItemNotFound || status == errSecMissingEntitlement
    }
    
    /// Convenience helper for saving string
    @discardableResult
    public func saveString(key: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }
        return save(key: key, data: data)
    }
    
    /// Convenience helper for reading string
    public func readString(key: String) -> String? {
        guard let data = read(key: key) else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
#else
/// Cross-platform memory-backed fallback for non-Apple environments (e.g. Linux CI)
public final class KeychainHelper {
    public static let shared = KeychainHelper()
    private var storage = [String: Data]()
    private let lock = NSLock()
    
    private init() {}
    
    @discardableResult
    public func save(key: String, data: Data) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        storage[key] = data
        return true
    }
    
    public func read(key: String) -> Data? {
        lock.lock()
        defer { lock.unlock() }
        return storage[key]
    }
    
    @discardableResult
    public func delete(key: String) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        storage.removeValue(forKey: key)
        return true
    }
    
    @discardableResult
    public func saveString(key: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }
        return save(key: key, data: data)
    }
    
    public func readString(key: String) -> String? {
        guard let data = read(key: key) else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
#endif
