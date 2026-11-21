import SwiftUI

public struct AttendanceCameraView: View {
    @StateObject private var cameraService = AVCaptureService()
    @StateObject private var apiService = AttendanceAPIService.shared
    
    @State private var recognitionState: String = "Scanning Face..."
    @State private var isLiveDetected: Bool = false
    @State private var isAttendanceMarked: Bool = false
    
    public init() {}
    
    public var body: some View {
        VStack(spacing: 20) {
            ZStack {
                if let frame = cameraService.currentFrame {
                    Image(uiImage: frame)
                        .resizable()
                        .scaledToFill()
                        .frame(width: 320, height: 420)
                        .clipped()
                        .cornerRadius(16)
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(isLiveDetected ? Color.green : Color.yellow, lineWidth: 4)
                        )
                } else {
                    Rectangle()
                        .fill(Color.black.opacity(0.8))
                        .frame(width: 320, height: 420)
                        .cornerRadius(16)
                        .overlay(
                            Text("Initializing Camera...")
                                .foregroundColor(.white)
                        )
                }
            }
            
            VStack(spacing: 8) {
                Text(recognitionState)
                    .font(.headline)
                    .foregroundColor(isLiveDetected ? .green : .primary)
                
                if isAttendanceMarked {
                    Text("✅ Attendance Verified (1x Today)")
                        .font(.subheadline)
                        .foregroundColor(.green)
                }
            }
            .padding()
            
            HStack(spacing: 16) {
                Button(action: { cameraService.start() }) {
                    Label("Start Stream", systemImage: "play.fill")
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(10)
                }
                
                Button(action: { cameraService.stop() }) {
                    Label("Stop Stream", systemImage: "stop.fill")
                        .padding()
                        .background(Color.gray.opacity(0.2))
                        .foregroundColor(.primary)
                        .cornerRadius(10)
                }
            }
        }
        .onAppear {
            cameraService.start()
        }
        .onDisappear {
            cameraService.stop()
        }
    }
}

