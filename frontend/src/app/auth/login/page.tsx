"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BadgeCheck,
  Fingerprint,
  Lock,
  LogIn,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  SquareUserRound,
  Eye,
  EyeOff,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";

const quickFacts = [
  { label: "Offline-first", value: "Local AI stack" },
  { label: "Attendance", value: "Auto-mark ready" },
  { label: "Security", value: "MFA + lockout" },
];

const highlights = [
  "Live recognition with protected sessions",
  "MFA-ready sign-in for staff and admins",
  "Designed for college-scale attendance flows",
];

export default function LoginPage() {
  const [username, setUsername] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("remembered_username") || "";
  });
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(() => {
    if (typeof window === "undefined") return true;
    return Boolean(localStorage.getItem("remembered_username"));
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isMfaRequired, setIsMfaRequired] = useState(false);
  const router = useRouter();
  const { setToken, setUser } = useAppStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setIsMfaRequired(false);

    try {
      const result = await api.login(username, password);

      if (typeof window !== "undefined") {
        if (rememberMe) {
          localStorage.setItem("remembered_username", username);
        } else {
          localStorage.removeItem("remembered_username");
        }
      }

      if (result.requires_mfa && result.mfa_token) {
        localStorage.setItem("mfa_token", result.mfa_token);
        setIsMfaRequired(true);
        router.push("/auth/mfa");
        return;
      }

      if (result.access_token) {
        setToken(result.access_token);
        if (result.refresh_token) {
          localStorage.setItem("refresh_token", result.refresh_token);
        }
        const user = await api.getMe();
        setUser(user);
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen relative overflow-hidden text-white">
      <div className="absolute inset-0 grid-fade opacity-50" />
      <div className="absolute -top-32 -left-24 h-96 w-96 rounded-full bg-blue-500/20 blur-3xl" />
      <div className="absolute bottom-0 right-0 h-[28rem] w-[28rem] rounded-full bg-emerald-400/10 blur-3xl" />

      <div className="relative mx-auto grid min-h-screen max-w-7xl items-stretch gap-8 px-4 py-6 lg:grid-cols-[1.1fr_0.9fr] lg:px-8">
        <section className="glass-panel relative flex min-h-[320px] flex-col justify-between overflow-hidden rounded-[2rem] p-8 sm:p-10">
          <div className="max-w-xl">
            <div className="mb-8 inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500/20 text-blue-200">
                <Sparkles className="h-4 w-4" />
              </span>
              Secure access for attendance, analytics, and admin control
            </div>

            <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
              Face Recognition AI
              <span className="mt-3 block bg-gradient-to-r from-white via-blue-100 to-cyan-200 bg-clip-text text-transparent">
                Sign in to the college dashboard.
              </span>
            </h1>

            <p className="mt-6 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
              A modern login experience for staff, admins, and operators.
              Keep attendance, camera monitoring, and recognition controls behind
              one secure, MFA-ready gate.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {quickFacts.map((fact) => (
                <div key={fact.label} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="text-xs uppercase tracking-[0.24em] text-slate-400">{fact.label}</div>
                  <div className="mt-2 text-sm font-medium text-white">{fact.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-10 grid gap-4 lg:grid-cols-3">
            {highlights.map((item) => (
              <div key={item} className="rounded-2xl border border-white/10 bg-slate-950/30 p-4 text-sm text-slate-200">
                <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-blue-500/15 text-blue-200">
                  <BadgeCheck className="h-4 w-4" />
                </div>
                {item}
              </div>
            ))}
          </div>
        </section>

        <section className="flex items-center justify-center">
          <div className="glass-panel w-full max-w-lg rounded-[2rem] p-6 sm:p-8">
            <div className="mb-8 flex items-center justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-200">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Secure sign in
                </div>
                <h2 className="mt-4 text-3xl font-semibold tracking-tight">Welcome back</h2>
                <p className="mt-2 text-sm text-slate-400">
                  Enter your credentials to continue.
                </p>
              </div>
              <div className="hidden rounded-2xl border border-white/10 bg-white/5 p-3 text-slate-300 sm:block">
                <Fingerprint className="h-6 w-6" />
              </div>
            </div>

            {error && (
              <div className="mb-5 flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {isMfaRequired && (
              <div className="mb-5 rounded-2xl border border-blue-400/20 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">
                MFA is required. Redirecting you to verification now.
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-200">Username</label>
                <div className="relative">
                  <SquareUserRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/30 px-11 py-3.5 text-white placeholder:text-slate-500 outline-none transition focus:border-blue-400/50 focus:ring-4 focus:ring-blue-400/10"
                    placeholder="Enter your username"
                    autoComplete="username"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-200">Password</label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/30 px-11 py-3.5 pr-12 text-white placeholder:text-slate-500 outline-none transition focus:border-blue-400/50 focus:ring-4 focus:ring-blue-400/10"
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((value) => !value)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-xl p-2 text-slate-400 transition hover:bg-white/5 hover:text-white"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <label className="inline-flex items-center gap-2 text-slate-300">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-transparent text-blue-500 focus:ring-blue-500"
                  />
                  Remember username
                </label>

                <Link href="/auth/mfa" className="text-blue-300 transition hover:text-blue-200">
                  Use MFA code
                </Link>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="group inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-blue-500 to-cyan-400 px-4 py-3.5 font-semibold text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Signing in..." : "Sign In"}
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </button>
            </form>

            <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/30 p-4">
              <div className="flex items-start gap-3">
                <LogIn className="mt-0.5 h-4 w-4 text-blue-300" />
                <div>
                  <p className="text-sm font-medium text-white">Need access?</p>
                  <p className="mt-1 text-sm text-slate-400">
                    This dashboard is for authorized college staff. Contact your administrator if you do not have credentials.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-between text-xs text-slate-500">
              <span>Secure attendance workflow</span>
              <span>v2.0</span>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
