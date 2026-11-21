#if canImport(SwiftUI) && canImport(UIKit)
import SwiftUI

public struct ContentView: View {
    @EnvironmentObject private var apiService: AttendanceAPIService
    @State private var username: String = ""
    @State private var password: String = ""
    @State private var serverHost: String = "127.0.0.1:8000"
    @State private var isLoggingIn: Bool = false
    @State private var loginError: String?
    @State private var selectedTab: Int = 0
    
    public init() {}
    
    public var body: some View {
        Group {
            if apiService.isAuthenticated {
                authenticatedDashboardView
            } else {
                loginView
            }
        }
    }
    
    // MARK: - Login View
    private var loginView: some View {
        NavigationView {
            Form {
                Section(header: Text("Face Recognition AI — iOS Client")) {
                    Text("Secure Attendance & Anti-Spoofing Verification")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
                
                Section(header: Text("Authentication")) {
                    TextField("Username", text: $username)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    
                    SecureField("Password", text: $password)
                }
                
                Section(header: Text("Backend Server Configuration")) {
                    TextField("Host (IP:Port)", text: $serverHost)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }
                
                if let error = loginError {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                            .font(.caption)
                    }
                }
                
                Section {
                    Button(action: performLogin) {
                        if isLoggingIn {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle())
                        } else {
                            Text("Log In")
                                .bold()
                        }
                    }
                    .disabled(username.isEmpty || password.isEmpty || isLoggingIn)
                }
            }
            .navigationTitle("Employee Login")
        }
    }
    
    // MARK: - Authenticated Dashboard
    private var authenticatedDashboardView: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Live Attendance & Verification
            NavigationView {
                ScrollView {
                    VStack(spacing: 20) {
                        AttendanceCameraView()
                    }
                    .padding()
                }
                .navigationTitle("Live Attendance")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Logout") {
                            apiService.logout()
                        }
                    }
                }
            }
            .tabItem {
                Label("Attendance", systemImage: "person.crop.square.fill")
            }
            .tag(0)
            
            // Tab 2: Security & Session Status
            NavigationView {
                List {
                    Section(header: Text("Active Session")) {
                        HStack {
                            Text("User")
                            Spacer()
                            Text(apiService.currentSession?.username ?? "Unknown")
                                .foregroundColor(.secondary)
                        }
                        HStack {
                            Text("Role")
                            Spacer()
                            Text(apiService.currentSession?.role ?? "EMPLOYEE")
                                .foregroundColor(.secondary)
                        }
                        HStack {
                            Text("Keychain Storage")
                            Spacer()
                            Text("Encrypted (AES-GCM)")
                                .foregroundColor(.green)
                        }
                    }
                    
                    Section(header: Text("Security & Privacy Guarantees")) {
                        Label("No Biometric Embeddings on Device", systemImage: "checkmark.shield.fill")
                            .foregroundColor(.blue)
                        Label("Zero-Knowledge Local Storage", systemImage: "lock.fill")
                            .foregroundColor(.green)
                        Label("Anti-Spoofing MiniFASNetV2 Active", systemImage: "camera.metering.matrix")
                            .foregroundColor(.purple)
                    }
                }
                .navigationTitle("Security & Privacy")
            }
            .tabItem {
                Label("Security", systemImage: "shield.checkerboard")
            }
            .tag(1)
        }
    }
    
    private func performLogin() {
        guard !username.isEmpty, !password.isEmpty else { return }
        isLoggingIn = true
        loginError = nil
        
        if let customURL = URL(string: "http://\(serverHost)") {
            apiService.baseURL = customURL
        }
        
        Task {
            do {
                _ = try await apiService.login(username: username, password: password)
                await MainActor.run {
                    self.isLoggingIn = false
                }
            } catch {
                await MainActor.run {
                    self.loginError = error.localizedDescription
                    self.isLoggingIn = false
                }
            }
        }
    }
}
#endif
