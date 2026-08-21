import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle2 } from 'lucide-react';
import { api, errText } from '../api';
import { PasswordInput } from '../components/PasswordInput';
import { Logo, BrandLockup } from '../components/Logo';

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const googleSignIn = () => {
  const redirectUrl = window.location.origin + '/reviews';
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

export default function Auth({ setUser }) {
  const nav = useNavigate();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (mode === 'forgot') {
        const r = await api.post('/auth/forgot-password', { email: form.email });
        setSent(r.data.message);
      } else {
        const r = await api.post(`/auth/${mode}`, form);
        setUser(r.data);
        nav('/reviews');
      }
    } catch (x) {
      setError(errText(x));
    } finally { setBusy(false); }
  };

  const switchMode = (m) => { setMode(m); setError(''); setSent(''); };

  return (
    <main className="auth-page">
      <div className="auth-card" data-testid="auth-card">
        <BrandLockup size={40} />
        {mode === 'forgot' ? (
          <>
            <h1>Forgot your password?</h1>
            <p className="sub">Type your email and we will send you a link to set a new password.</p>
          </>
        ) : (
          <>
            <h1>{mode === 'login' ? 'Welcome back' : 'Create your free account'}</h1>
            <p className="sub">Ready-made Google reviews for your business. No tech skills needed.</p>
          </>
        )}

        <div className="beta-note" data-testid="beta-notice">
          <strong>🎉 We&apos;re in Beta!</strong>
          <span>Review Gate GMB is free to use while we test and improve it. Sign up, explore, use it, and share your feedback — it helps us build something better.</span>
        </div>

        {sent ? (
          <div className="inline-success" data-testid="forgot-success"><CheckCircle2 size={18} /> <span>{sent}</span></div>
        ) : (
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" data-testid="auth-email-input" type="email" required value={form.email}
                onChange={(e) => { setForm({ ...form, email: e.target.value }); setError(''); }} placeholder="you@business.com" />
            </div>
            {mode !== 'forgot' && (
              <div className="field">
                <label htmlFor="password">Password</label>
                <PasswordInput id="password" testid="auth-password-input" minLength={8} required value={form.password}
                  onChange={(e) => { setForm({ ...form, password: e.target.value }); setError(''); }} placeholder="At least 8 characters" />
                {mode === 'login' && (
                  <button type="button" className="text-btn" style={{ alignSelf: 'flex-start' }} onClick={() => switchMode('forgot')} data-testid="forgot-password-link">
                    Forgot password?
                  </button>
                )}
              </div>
            )}
            {error && <div className="inline-error" data-testid="auth-error">{error}</div>}
            <button className="btn btn-primary" type="submit" disabled={busy} data-testid="auth-submit-button">
              {mode === 'forgot' ? (busy ? 'Sending…' : 'Send reset link') : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>
        )}

        {mode !== 'forgot' && (
          <>
            <div className="or-line"><span>or</span></div>
            <button className="btn btn-google" onClick={googleSignIn} data-testid="google-signin-button">
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.7 30.1.5 24 .5 14.6.5 6.5 5.8 2.6 13.6l7.8 6c1.9-5.7 7.2-10.1 13.6-10.1Z" />
                <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-2.8-.4-4.1H24v8.1h12.5c-.3 2.1-1.6 5.2-4.6 7.3l7.6 5.9c4.5-4.2 6.6-10.3 6.6-17.2Z" />
                <path fill="#FBBC05" d="M10.4 28.4A14.6 14.6 0 0 1 9.6 24c0-1.5.3-3 .7-4.4l-7.8-6A23.9 23.9 0 0 0 0 24c0 3.8.9 7.5 2.6 10.4l7.8-6Z" />
                <path fill="#34A853" d="M24 47.5c6.1 0 11.3-2 15-5.5l-7.6-5.9c-2 1.4-4.7 2.4-7.4 2.4-6.4 0-11.7-4.3-13.6-10.1l-7.8 6C6.5 42.2 14.6 47.5 24 47.5Z" />
              </svg>
              Continue with Google
            </button>
          </>
        )}

        <div className="auth-switch">
          {mode === 'forgot' ? (
            <button className="text-btn" onClick={() => switchMode('login')} data-testid="back-to-login"><ArrowLeft size={14} /> Back to sign in</button>
          ) : (
            <>
              {mode === 'login' ? 'New here? ' : 'Already have an account? '}
              <button className="text-btn" data-testid="auth-mode-toggle" onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>
                {mode === 'login' ? 'Create an account' : 'Sign in'}
              </button>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
