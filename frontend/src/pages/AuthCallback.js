import { useEffect, useRef, useState } from 'react';
import { api, errText } from '../api';

export default function AuthCallback({ setUser }) {
  const done = useRef(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const sessionId = new URLSearchParams(window.location.hash.replace('#', '')).get('session_id');
    (async () => {
      try {
        const r = await api.post('/auth/google/session', { session_id: sessionId });
        setUser(r.data);
        window.location.replace('/reviews');
      } catch (x) {
        setError(errText(x));
      }
    })();
  }, [setUser]);

  if (error) {
    return (
      <div className="auth-page">
        <div className="auth-card" data-testid="google-callback-error">
          <span className="brand-mark">R</span>
          <h1>Google sign-in did not work</h1>
          <p className="sub">{error}</p>
          <a className="btn btn-primary" href="/" style={{ justifyContent: 'center' }}>Back to sign in</a>
        </div>
      </div>
    );
  }
  return <div className="loading-screen" data-testid="google-callback">Signing you in…</div>;
}
