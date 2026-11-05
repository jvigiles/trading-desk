import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/lib/supabase";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setErr(error.message);
    setBusy(false);
  }

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center p-6">
      <div className="mb-6">
        <div className="mono text-lg font-semibold">Trading Desk</div>
        <p className="mt-1 text-sm text-muted-foreground">Personal decision-support for IBKR paper trading. Sign in with the account created in Supabase.</p>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="input-email" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="input-password" />
        </div>
        {err && <p className="text-sm text-destructive" data-testid="text-login-error">{err}</p>}
        <Button type="submit" className="w-full" disabled={busy} data-testid="button-login">{busy ? "Signing in…" : "Sign in"}</Button>
      </form>
      <p className="mt-6 text-xs text-muted-foreground">Signups are disabled. Reset your password from the Supabase dashboard if needed. Nothing here is investment advice; you place every order yourself.</p>
    </div>
  );
}
