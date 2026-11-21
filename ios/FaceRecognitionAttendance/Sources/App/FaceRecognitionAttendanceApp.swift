#if canImport(SwiftUI) && (!SWIFT_PACKAGE || APP_TARGET)
import SwiftUI

@main
public struct FaceRecognitionAttendanceApp: App {
    @StateObject private var apiService = AttendanceAPIService.shared
    
    public init() {}
    
    public var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(apiService)
        }
    }
}
#endif
