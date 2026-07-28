import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { apiRequest } from "../lib/api";
import type { AuthData } from "../lib/types";


const MODE_LABELS: Record<AuthData["runtime"]["activeAccessMode"], string> = {
  locked: "Solo questo computer",
  lan: "Rete locale LAN",
  online: "Server online protetto",
};


export function LoginPage({ auth }: { auth: AuthData }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: () => apiRequest<AuthData>("/api/auth/login/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
    onSuccess: (result) => {
      queryClient.setQueryData(["auth"], result.data);
      const requested = new URLSearchParams(location.search).get("next") || "/";
      const destination = requested.startsWith("/") && !requested.startsWith("//") ? requested : "/";
      navigate(destination, { replace: true });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  return <main className="auth-screen" data-component-type="view" data-theme="dark">
    <section className="auth-card" data-component-type="panel" data-theme="parchment">
      <header>
        <span className="brand-rune" aria-hidden="true">RD</span>
        <div><p className="eyebrow">Accesso protetto</p><h1>ReDjango</h1></div>
      </header>
      <p className="auth-intro">Accedi con il tuo account per entrare nella postazione di gioco.</p>
      <form onSubmit={submit}>
        <label>Nome utente<input autoFocus autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
        <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {mutation.error && <p className="auth-error" role="alert">{mutation.error.message}</p>}
        <button className="button primary" disabled={mutation.isPending || !username.trim() || !password}>
          {mutation.isPending ? "Accesso…" : "Accedi"}
        </button>
      </form>
      <footer>
        <span>Modalità attiva: <strong>{MODE_LABELS[auth.runtime.activeAccessMode]}</strong></span>
        <a href="/admin/login/">Accesso Django Admin</a>
      </footer>
    </section>
  </main>;
}
