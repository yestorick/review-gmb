import { useEffect, useState } from 'react';
import { Building2, Check, CheckCircle2, Link2, Mail, ShieldCheck } from 'lucide-react';
import { api, errText } from '../api';
import { PasswordInput } from '../components/PasswordInput';

const longDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }) : '—');

export default function Profile({ user }) {
  const [business, setBusiness] = useState(null);
  const [form, setForm] = useState({ current_password: '', new_password: '' });
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setError(''); setDone(false); };
  const isGoogle = user?.auth_provider === 'google';

  useEffect(() => {
    api.get('/settings').then((r) => setBusiness(r.data.business)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.post('/auth/change-password', form);
      setForm({ current_password: '', new_password: '' });
      setDone(true);
    } catch (x) { setError(errText(x)); } finally { setBusy(false); }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title" data-testid="profile-heading">My Profile</h1>
          <p className="page-help">Your login details and password, all in one place.</p>
        </div>
      </div>

      <div className="form-card profile-card" data-testid="profile-details">
        <div className="profile-top">
          {user?.picture
            ? <img className="profile-avatar" src={user.picture} alt={user.name || user.email} data-testid="profile-avatar" />
            : <span className="profile-avatar initials" data-testid="profile-initials">{((user?.name || user?.email || '?').trim())[0].toUpperCase()}</span>}
          <div>
            <strong className="profile-name" data-testid="profile-name">{user?.name || business?.name || 'Business owner'}</strong>
            <span className="profile-sub" data-testid="profile-email-top">{user?.email}</span>
          </div>
        </div>

        <dl className="detail-list">
          <div>
            <dt><Mail size={16} /> Login email</dt>
            <dd data-testid="profile-email">{user?.email}</dd>
          </div>
          <div>
            <dt><ShieldCheck size={16} /> Sign-in method</dt>
            <dd data-testid="profile-provider">{isGoogle ? 'Google account' : 'Email and password'}</dd>
          </div>
          <div>
            <dt><Check size={16} /> Member since</dt>
            <dd data-testid="profile-joined">{longDate(user?.created_at)}</dd>
          </div>
          <div>
            <dt><Building2 size={16} /> Business</dt>
            <dd data-testid="profile-business">{business?.name || 'Not added yet'}</dd>
          </div>
          <div>
            <dt><Link2 size={16} /> Review link</dt>
            <dd data-testid="profile-link">{business?.is_active ? business.public_url : 'Starts working once you add your Google review link'}</dd>
          </div>
        </dl>
      </div>

      <form className="form-card" onSubmit={submit} style={{ maxWidth: 520, marginTop: 18 }}>
        <h2 style={{ fontSize: '1.05rem', marginTop: 0 }}>Change password</h2>
        {isGoogle ? (
          <p className="page-help" style={{ marginTop: 0 }} data-testid="profile-google-note">
            You sign in with Google, so there is no password to change here. Manage it in your Google account.
          </p>
        ) : (
          <>
            <p className="page-help" style={{ marginTop: 0 }}>Pick something you will remember. At least 8 characters.</p>
            <div className="field" style={{ marginBottom: 16 }}>
              <label>Current password</label>
              <PasswordInput testid="current-password-input" required value={form.current_password} onChange={set('current_password')} />
            </div>
            <div className="field">
              <label>New password</label>
              <PasswordInput testid="new-password-input" minLength={8} required value={form.new_password} onChange={set('new_password')} />
            </div>
            {error && <div className="inline-error" data-testid="change-password-error">{error}</div>}
            {done && <div className="inline-success" data-testid="change-password-success"><CheckCircle2 size={18} /> <span>Your password has been changed. Use it next time you sign in.</span></div>}
            <div className="form-foot">
              <button className="btn btn-primary" type="submit" disabled={busy} data-testid="save-password-button"><Check size={18} /> {busy ? 'Saving…' : 'Save new password'}</button>
            </div>
          </>
        )}
      </form>
    </>
  );
}
