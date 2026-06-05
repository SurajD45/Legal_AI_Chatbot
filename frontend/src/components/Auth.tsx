import { useState } from "react";
import { signInWithEmail, signUpWithEmail } from "../services/auth";
import { Scale, Mail, Lock, Eye, EyeOff, CheckCircle2, Terminal } from "lucide-react";

export default function Auth() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"login" | "signup">("login");

  async function handleSubmit() {
    if (!email.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    try {
      setLoading(true);
      setError(null);

      if (mode === "login") {
        await signInWithEmail(email, password);
        window.location.reload();
      } else {
        await signUpWithEmail(email, password);
        alert("Signup successful! Please check your email to verify your account.");
        setMode("login");
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex flex-col md:flex-row bg-navy-black text-text-primary font-sans">
      {/* LEFT PANEL (Desktop Storytelling / Hero) */}
      <div className="w-full md:w-1/2 bg-navy-black flex flex-col justify-between p-8 md:p-16 border-b md:border-b-0 md:border-r border-dark-border relative overflow-hidden">
        {/* Subtle background gradient glow */}
        <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gold/5 rounded-full blur-[100px] pointer-events-none" />

        {/* Top Header */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="w-10 h-10 rounded-xl bg-gold/10 border border-gold/30 flex items-center justify-center">
            <Scale className="w-5 h-5 text-gold" />
          </div>
          <span className="text-2xl font-bold font-display tracking-tight text-gold">
            Lex<span className="text-text-primary">AI</span>
          </span>
        </div>

        {/* Center Content / Vitals */}
        <div className="my-auto py-12 md:py-0 relative z-10 max-w-lg">
          <h1 className="text-4xl md:text-5xl font-extrabold font-display leading-tight tracking-tight mb-4">
            Legal Research, <br />
            <span className="text-gold">Reimagined</span>
          </h1>
          <p className="text-text-secondary text-base md:text-lg mb-8 leading-relaxed">
            AI-powered analysis of the Indian Penal Code (IPC). Get precise citations, related provisions, and reasoning in seconds.
          </p>

          {/* Feature Pills */}
          <div className="space-y-4">
            <div className="flex items-start gap-3 bg-dark-surface/50 border border-dark-border/50 p-3.5 rounded-xl transition-all duration-300 hover:border-gold/20">
              <CheckCircle2 className="w-5 h-5 text-gold mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-text-primary text-sm">548 IPC Sections Indexed</h4>
                <p className="text-text-secondary text-xs mt-0.5">Every provision, explanation, and illustration completely mapped.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 bg-dark-surface/50 border border-dark-border/50 p-3.5 rounded-xl transition-all duration-300 hover:border-gold/20">
              <CheckCircle2 className="w-5 h-5 text-gold mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-text-primary text-sm">Hybrid RAG Retrieval</h4>
                <p className="text-text-secondary text-xs mt-0.5">Combining BM25 keyword matching with dense neural vector search.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 bg-dark-surface/50 border border-dark-border/50 p-3.5 rounded-xl transition-all duration-300 hover:border-gold/20">
              <CheckCircle2 className="w-5 h-5 text-gold mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-text-primary text-sm">Conversational Context & Memory</h4>
                <p className="text-text-secondary text-xs mt-0.5">Remembers previous turns for seamless query condensation.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Metadata Badge */}
        <div className="flex items-center gap-2 text-xs text-text-secondary font-mono relative z-10">
          <Terminal className="w-4 h-4 text-gold" />
          <span>Built on Llama 3 • Qdrant • Groq RAG Stack</span>
        </div>
      </div>

      {/* RIGHT PANEL (Sign In / Sign Up Form) */}
      <div className="w-full md:w-1/2 bg-dark-surface flex items-center justify-center p-8 md:p-16 relative">
        <div className="w-full max-w-md bg-navy-black/60 border border-dark-border rounded-2xl p-8 backdrop-blur-md shadow-2xl relative z-10">
          <div className="mb-8">
            <h2 className="text-2xl md:text-3xl font-bold font-display text-text-primary">
              {mode === "login" ? "Welcome back" : "Create Account"}
            </h2>
            <p className="text-text-secondary text-sm mt-2">
              {mode === "login"
                ? "Sign in to continue your legal research"
                : "Join LexAI to start your legal research"}
            </p>
          </div>

          <div className="space-y-5">
            {/* Email Field */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-dark-surface border border-dark-border rounded-xl focus:ring-2 focus:ring-gold/30 focus:border-gold outline-none text-text-primary placeholder:text-text-secondary/50 text-sm transition-all"
                />
              </div>
            </div>

            {/* Password Field */}
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary">
                  Password
                </label>
                {mode === "login" && (
                  <button className="text-xs text-gold/80 hover:text-gold transition">
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-10 py-2.5 bg-dark-surface border border-dark-border rounded-xl focus:ring-2 focus:ring-gold/30 focus:border-gold outline-none text-text-primary placeholder:text-text-secondary/50 text-sm transition-all"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSubmit();
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary transition"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="bg-red-950/40 border border-red-500/40 text-red-400 text-xs rounded-xl px-4 py-3 leading-normal">
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full py-3 bg-gold hover:bg-gold/90 active:scale-[0.99] text-navy-black font-semibold rounded-xl transition-all shadow-lg shadow-gold/10 disabled:opacity-50 disabled:pointer-events-none mt-2 flex items-center justify-center"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-navy-black border-t-transparent rounded-full animate-spin" />
              ) : mode === "login" ? (
                "Sign In"
              ) : (
                "Create Account"
              )}
            </button>
          </div>

          {/* Toggle mode links */}
          <div className="mt-6 text-center text-sm text-text-secondary">
            {mode === "login" ? (
              <>
                Don't have an account?{" "}
                <button
                  onClick={() => setMode("signup")}
                  className="text-gold hover:underline font-medium ml-1"
                >
                  Sign up
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  onClick={() => setMode("login")}
                  className="text-gold hover:underline font-medium ml-1"
                >
                  Sign in
                </button>
              </>
            )}
          </div>

          {/* Small legal disclaimer */}
          <div className="mt-8 text-center text-[10px] text-text-secondary/60 leading-normal border-t border-dark-border/40 pt-4">
            Legal information provided by LexAI is for educational and research purposes only. It does not constitute formal legal counsel.
          </div>
        </div>
      </div>
    </div>
  );
}
