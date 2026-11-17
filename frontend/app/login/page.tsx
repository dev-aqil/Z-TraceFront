"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { signIn } from "@/lib/api";

// Only a path on this site: a crafted link must not send someone who has just signed in to another site.
const safeNext = (value: string | null) => (value && /^\/(?![/\\])/.test(value) ? value : "/trace");

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Until the page's script is running, a submit would be the browser's own: keep the button off until then.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await signIn(email, password);
      window.location.assign(safeNext(new URLSearchParams(window.location.search).get("next")));
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return <main className="flex min-h-dvh items-center justify-center bg-[#f7f9fb] px-5 py-10 text-[#0d293b]">
    <div className="w-full max-w-sm">
      <Image src="/tracefront-logo-black.png" alt="TraceFront" width={140} height={50} priority className="h-11 w-auto" />
      {/* method="post": if a submit ever does bypass the handler, the fields must not end up in the address bar. */}
      <form onSubmit={submit} method="post" className="mt-6 rounded-2xl border border-slate-200 bg-white p-6">
        <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-1 text-xs leading-5 text-slate-600">Each company sees and enters its own records. Ministry of Health officers see the whole chain.</p>
        <label className="mt-5 block text-xs font-semibold">Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" autoFocus className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" />
        </label>
        <label className="mt-4 block text-xs font-semibold">Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" />
        </label>
        {error && <p role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-800">{error}</p>}
        <button type="submit" disabled={busy || !ready}className="mt-5 w-full rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="mt-4 text-xs leading-5 text-slate-500">Accounts are created by the system administrator. There is no public sign-up.</p>
    </div>
  </main>;
}
