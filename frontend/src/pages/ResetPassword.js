import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import { api, errText } from '../api';
import { PasswordInput } from '../components/PasswordInput';

export default function ResetPassword({ setUser }) {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const r = await api.post('/auth/reset-password', { token, password });
      setUser(r.data);
      setDone(true);
      setTimeout(() => nav('/reviews'), 1500);
    } catch (x) { setError(errText(x)); } finally { setBusy(false); }
  };

  return (
    <main className="auth-page">
      <div className="auth-card" data-testid="reset-card">
        <span className="brand-mark">R</span>
        <h1>Set a new password</h1>
        <p className="sub">Choose something you will remember. At least 8 characters.</p>
        {done ? (
          <div className="inline-success" data-testid="reset-success"><CheckCircle2 size={18} /> <span>Password changed. Taking you to your reviews…</span></div>
        ) : (
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="new-pass">New password</label>
              <PasswordInput id="new-pass" testid="reset-password-input" minLength={8} required value={password}
                onChange={(e) => { setPassword(e.target.value); setError(''); }} placeholder="At least 8 characters" />
            </div>
            {error && <div className="inline-error" data-testid="reset-error">{error}</div>}
            <button className="btn btn-primary" type="submit" disabled={busy || !token} data-testid="reset-submit-button">
              {busy ? 'Saving…' : 'Save new password'}
            </button>
            {!token && <div className="inline-error">This link is missing its code. Please open the link from your email again.</div>}
          </form>
        )}
      </div>
    </main>
  );
}
