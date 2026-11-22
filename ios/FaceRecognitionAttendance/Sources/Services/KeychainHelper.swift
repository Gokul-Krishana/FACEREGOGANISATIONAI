import Foundation
#if canImport(Security)
import Security
#else
public typealias OSStatus = Int32
#endif

/// Strongly-typed error enum representing Keychain operation outcomes.
/// Strictly excludes sensitive credentials from all descriptions.
public enum KeychainError: Error, Equatable, CustomStringConvertible {
    case missingEntitlement(OSStatus)
    case itemNotFound
    case accessDenied(OSStatus)
    case unhandledError(status: OSStatus)
    case conversionFailed
    case failClosed(reason: String)
    
    public var description: String {
        switch self {
        case .missingEntitlement(let status):
            return "Keychain missing entitlement error (status: \(status)). Provisioning profile with Keychain Access Groups or Keychain entitlement required."
        case .itemNotFound:
            return "Keychain item not found."
        case .accessDenied(let status):
            return "Keychain access denied (status: \(status)). Device may be locked or passcode required."
        case .unhandledError(let status):
            return "Keychain operation failed with OSStatus \(status)."
        case .conversionFailed:
            return "Failed to convert Keychain payload."
        case .failClosed(let reason):
            return "Keychain operation failed closed: \(reason)"
        }
    }
}

/// Abstract backend interface for Keychain storage.
public protocol KeychainBackend: AnyObject {
    func save(key: String, data: Data) throws
    func read(key: String) throws -> Data?
    func delete(key: String) throws
}

#if canImport(Security)
/// Production Apple Security Framework Keychain implementation.
/// Fails closed on any error and NEVER silently uses in-memory fallbacks.
public final class AppleKeychainBackend: KeychainBackend {
    private let serviceName = "com.facerecognition.attendance"
    
    public init() {}
    
    public func save(key: String, data: Data) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]
        
        SecItemDelete(query as CFDictionary)
        let status = SecItemAdd(query as CFDictionary, nil)
        
        guard status == errSecSuccess else {
            throw mapOSStatus(status)
        }
    }
    
    public func read(key: String) throws -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var dataTypeRef: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &dataTypeRef)
        
        if status == errSecSuccess {
            guard let data = dataTypeRef as? Data else {
                throw KeychainError.conversionFailed
            }
            return data
        } else if status == errSecItemNotFound {
            return nil
        } else {
            throw mapOSStatus(status)
        }
    }
    
    public func delete(key: String) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        if status == errSecSuccess || status == errSecItemNotFound {
            return
        } else {
            throw mapOSStatus(status)
        }
    }
    
    private func mapOSStatus(_ status: OSStatus) -> KeychainError {
        if status == errSecItemNotFound {
            return .itemNotFound
        } else if status == -34018 {
            return .missingEntitlement(status)
        } else if status == errSecInteractionNotAllowed || status == -25308 || status == -25293 {
            return .accessDenied(status)
        } else {
            return .unhandledError(status: status)
        }
    }
}
#endif

/// In-memory Keychain backend for testing and non-Apple platforms (e.g., Linux CI).
/// Can also simulate genuine errors for test verification.
public final class InMemoryKeychainBackend: KeychainBackend {
    private var storage = [String: Data]()
    private let lock = NSLock()
    public var simulatedError: KeychainError?
    
    public init(simulatedError: KeychainError? = nil) {
        self.simulatedError = simulatedError
    }
    
    public func save(key: String, data: Data) throws {
        lock.lock()
        defer { lock.unlock() }
        if let error = simulatedError {
            throw error
        }
        storage[key] = data
    }
    
    public func read(key: String) throws -> Data? {
        lock.lock()
        defer { lock.unlock() }
        if let error = simulatedError {
            throw error
        }
        return storage[key]
    }
    
    public func delete(key: String) throws {
        lock.lock()
        defer { lock.unlock() }
        if let error = simulatedError {
            throw error
        }
        storage.removeValue(forKey: key)
    }
    
    public func clear() {
        lock.lock()
        defer { lock.unlock() }
        storage.removeAll()
    }
}

/// Thread-safe helper for managing JWT tokens and credentials in the iOS Keychain.
/// Fails closed on any Keychain failure in production iOS device builds.
public final class KeychainHelper {
    public static let shared = KeychainHelper()
    private let lock = NSLock()
    private var backend: KeychainBackend
    public private(set) var lastError: KeychainError?
    
    private init() {
        #if os(iOS) && !targetEnvironment(simulator)
        // Physical iOS device builds ALWAYS use Apple Security Keychain exclusively.
        // It is compile-time impossible to use in-memory storage on a physical iOS device.
        self.backend = AppleKeychainBackend()
        #else
        // For Simulator, macOS development/tests, or Linux CI:
        #if canImport(Security)
        if ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil || NSClassFromString("XCTestCase") != nil {
            self.backend = InMemoryKeychainBackend()
        } else {
            self.backend = AppleKeychainBackend()
        }
        #else
        self.backend = InMemoryKeychainBackend()
        #endif
        #endif
    }
    
    #if DEBUG && (!os(iOS) || targetEnvironment(simulator))
    /// Test-only backend injection hook.
    /// Strictly stripped and uncompiled on physical iOS device builds (#if os(iOS) && !targetEnvironment(simulator)).
    public func setTestBackend(_ testBackend: KeychainBackend?) {
        lock.lock()
        defer { lock.unlock() }
        #if canImport(Security)
        self.backend = testBackend ?? AppleKeychainBackend()
        #else
        self.backend = testBackend ?? InMemoryKeychainBackend()
        #endif
        self.lastError = nil
    }
    #endif
    
    /// Save data to Keychain (throwing version)
    public func saveThrowing(key: String, data: Data) throws {
        lock.lock()
        defer { lock.unlock() }
        do {
            try backend.save(key: key, data: data)
            lastError = nil
        } catch let error as KeychainError {
            lastError = error
            throw error
        } catch {
            let wrapped = KeychainError.unhandledError(status: -1)
            lastError = wrapped
            throw wrapped
        }
    }
    
    /// Save data to Keychain (fails closed, returning false on failure)
    @discardableResult
    public func save(key: String, data: Data) -> Bool {
        do {
            try saveThrowing(key: key, data: data)
            return true
        } catch {
            return false
        }
    }
    
    /// Retrieve data from Keychain (throwing version)
    public func readThrowing(key: String) throws -> Data? {
        lock.lock()
        defer { lock.unlock() }
        do {
            let data = try backend.read(key: key)
            lastError = nil
            return data
        } catch let error as KeychainError {
            lastError = error
            throw error
        } catch {
            let wrapped = KeychainError.unhandledError(status: -1)
            lastError = wrapped
            throw wrapped
        }
    }
    
    /// Retrieve data from Keychain (nil on not found or error, sets lastError on error)
    public func read(key: String) -> Data? {
        do {
            return try readThrowing(key: key)
        } catch {
            return nil
        }
    }
    
    /// Delete key from Keychain (throwing version)
    public func deleteThrowing(key: String) throws {
        lock.lock()
        defer { lock.unlock() }
        do {
            try backend.delete(key: key)
            lastError = nil
        } catch let error as KeychainError {
            lastError = error
            throw error
        } catch {
            let wrapped = KeychainError.unhandledError(status: -1)
            lastError = wrapped
            throw wrapped
        }
    }
    
    /// Delete key from Keychain (fails closed, returning false on failure)
    @discardableResult
    public func delete(key: String) -> Bool {
        do {
            try deleteThrowing(key: key)
            return true
        } catch {
            return false
        }
    }
    
    /// Convenience helper for saving string
    @discardableResult
    public func saveString(key: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else {
            lock.lock()
            lastError = .conversionFailed
            lock.unlock()
            return false
        }
        return save(key: key, data: data)
    }
    
    /// Convenience helper for reading string
    public func readString(key: String) -> String? {
        guard let data = read(key: key) else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
