"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Fingerprint, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export default function MfaPage() {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { setToken, setUser } = useAppStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const mfaToken = localStorage.getItem("mfa_token");
    if (!mfaToken) {
      setError("No MFA token found. Please sign in again.");
      setLoading(false);
      return;
    }

    try {
      const result = await api.verifyMfa(code, mfaToken);
      localStorage.removeItem("mfa_token");

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
      setError(err instanceof Error ? err.message : "MFA verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen relative overflow-hidden text-white">
      <div className="absolute inset-0 grid-fade opacity-40" />
      <div className="absolute left-10 top-12 h-72 w-72 rounded-full bg-amber-400/15 blur-3xl" />

      <div className="relative mx-auto grid min-h-screen max-w-6xl items-center gap-8 px-4 py-6 lg:grid-cols-[0.95fr_1.05fr] lg:px-8">
        <section className="glass-panel rounded-[2rem] p-8 sm:p-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-200">
            <ShieldCheck className="h-3.5 w-3.5" />
            MFA verification
          </div>

          <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-5xl">
            Enter your 6-digit
            <span className="mt-2 block bg-gradient-to-r from-white to-amber-100 bg-clip-text text-transparent">
              authentication code.
            </span>
          </h1>

          <p className="mt-5 max-w-xl text-base leading-7 text-slate-300 sm:text-lg">
            Use the code from your authenticator app or a backup code if your
            administrator enabled one for your account.
          </p>

          <div className="mt-8 rounded-2xl border border-white/10 bg-slate-950/30 p-4">
            <p className="text-sm font-medium text-white">Need to go back?</p>
            <p className="mt-1 text-sm text-slate-400">
              Return to the login page and sign in again if your MFA token expired.
            </p>
            <Link
              href="/auth/login"
              className="mt-4 inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/10"
            >
              Back to login
            </Link>
          </div>
        </section>

        <section className="flex items-center justify-center">
          <div className="glass-panel w-full max-w-md rounded-[2rem] p-6 sm:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Verification step</p>
                <h2 className="mt-2 text-3xl font-semibold">Two-factor check</h2>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-amber-200">
                <Fingerprint className="h-6 w-6" />
              </div>
            </div>

            {error && (
              <div className="mb-5 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-200">Verification code</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\s+/g, ""))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/30 px-4 py-4 text-center text-3xl tracking-[0.45em] text-white outline-none transition placeholder:text-slate-500 focus:border-amber-400/50 focus:ring-4 focus:ring-amber-400/10"
                  placeholder="000000"
                  maxLength={6}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading || code.length < 6}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-400 px-4 py-3.5 font-semibold text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Verifying..." : "Verify code"}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>

            <p className="mt-6 text-sm text-slate-400">
              Protecting access to attendance and admin tools.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
