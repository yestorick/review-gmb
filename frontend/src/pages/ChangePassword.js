import { useState } from 'react';
import { Check, CheckCircle2 } from 'lucide-react';
import { api, errText } from '../api';
import { PasswordInput } from '../components/PasswordInput';

export default function ChangePassword() {
  const [form, setForm] = useState({ current_password: '', new_password: '' });
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setError(''); setDone(false); };

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
          <h1 className="page-title" data-testid="change-password-heading">Change Password</h1>
          <p className="page-help">Pick something you will remember. At least 8 characters.</p>
        </div>
      </div>
      <form className="form-card" onSubmit={submit} style={{ maxWidth: 480 }}>
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
      </form>
    </>
  );
}
