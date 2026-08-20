import { useState } from 'react';
import { Check } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';

export default function ChangePassword() {
  const [form, setForm] = useState({ current_password: '', new_password: '' });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/auth/change-password', form);
      setForm({ current_password: '', new_password: '' });
      toast.success('Password changed');
    } catch (x) { toast.error(errText(x)); }
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
          <input type="password" required value={form.current_password} onChange={set('current_password')} data-testid="current-password-input" />
        </div>
        <div className="field">
          <label>New password</label>
          <input type="password" minLength={8} required value={form.new_password} onChange={set('new_password')} data-testid="new-password-input" />
        </div>
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" data-testid="save-password-button"><Check size={18} /> Save new password</button>
        </div>
      </form>
    </>
  );
}
