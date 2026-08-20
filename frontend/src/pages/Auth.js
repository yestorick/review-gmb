import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { api, errText } from '../api';

export default function Auth({ setUser }) {
  const nav = useNavigate();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '' });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post(`/auth/${mode}`, form);
      setUser(r.data);
      nav('/reviews');
    } catch (x) {
      toast.error(errText(x));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <div className="auth-card" data-testid="auth-card">
        <span className="brand-mark">R</span>
        <h1>{mode === 'login' ? 'Welcome back' : 'Create your free account'}</h1>
        <p className="sub">Ready-made Google reviews for your shop. No tech skills needed.</p>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" data-testid="auth-email-input" type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@business.com" />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" data-testid="auth-password-input" type="password" minLength={8} required value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="At least 8 characters" />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy} data-testid="auth-submit-button">
            {mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <div className="auth-switch">
          {mode === 'login' ? 'New here? ' : 'Already have an account? '}
          <button className="text-btn" data-testid="auth-mode-toggle" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? 'Create an account' : 'Sign in'}
          </button>
        </div>
      </div>
    </main>
  );
}
