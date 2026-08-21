import { useEffect, useState } from 'react';
import { Check, CheckCircle2, Copy, Download, Pencil } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';

export default function Settings() {
  const [form, setForm] = useState({ name: '', business_category: '', location: '', service_area: '', google_review_url: '' });
  const [business, setBusiness] = useState(null);
  const [qr, setQr] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setError(''); };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(business.public_url);
      toast.success('Link copied');
    } catch {
      toast.message('Copy it from here', { description: business.public_url });
    }
  };

  useEffect(() => {
    (async () => {
      const b = (await api.get('/settings')).data.business;
      setBusiness(b);
      setForm({
        name: b.name || '', business_category: b.business_category || '', location: b.location || '',
        service_area: b.service_area || '', google_review_url: b.google_review_url || '',
      });
      setQr((await api.get(`/public/${b.public_slug}/qr`)).data.data_url);
      setLoaded(true);
      setEditing(!b.name);
    })().catch((x) => toast.error(errText(x)));
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setError('');
    try {
      setBusiness((await api.put('/settings', form)).data);
      setEditing(false);
      toast.success('Saved');
    } catch (x) { setError(errText(x)); }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title" data-testid="settings-heading">My Business</h1>
          <p className="page-help">{editing ? 'Fill your details and paste your Google review link, then tap Save.' : 'Your details are saved. Tap Edit if you want to change anything.'}</p>
        </div>
      </div>

      <form className="form-card" onSubmit={save} style={{ marginBottom: 18 }}>
        <div className="form-grid">
          <div className="field">
            <label>Business Name</label>
            <input value={form.name} onChange={set('name')} disabled={!editing} placeholder="Sharma Dental Clinic" data-testid="settings-name-input" />
          </div>
          <div className="field">
            <label>Business Category</label>
            <input value={form.business_category} onChange={set('business_category')} disabled={!editing} placeholder="Dentist" data-testid="settings-category-input" />
          </div>
          <div className="field">
            <label>Location</label>
            <input value={form.location} onChange={set('location')} disabled={!editing} placeholder="Kolkata" data-testid="settings-location-input" />
          </div>
          <div className="field">
            <label>Service Area<span className="hint">Optional</span></label>
            <input value={form.service_area} onChange={set('service_area')} disabled={!editing} placeholder="Salt Lake, New Town" data-testid="settings-service-area-input" />
          </div>
          <div className="field full">
            <label>Google Review Link<span className="hint">Open your Google listing, tap Reviews, then "Get more reviews" and copy that link</span></label>
            <input value={form.google_review_url} onChange={set('google_review_url')} disabled={!editing} placeholder="https://g.page/your-business/review" data-testid="settings-google-url-input" />
          </div>
        </div>
        {error && <div className="inline-error" data-testid="settings-error">{error}</div>}
        <div className="form-foot">
          {editing ? (
            <button className="btn btn-primary" type="submit" disabled={!loaded} data-testid="save-settings-button"><Check size={18} /> {loaded ? 'Save' : 'Loading…'}</button>
          ) : (
            <>
              <span className="saved-pill" data-testid="settings-saved-pill"><CheckCircle2 size={16} /> Saved</span>
              <button className="btn btn-ghost" type="button" onClick={() => setEditing(true)} data-testid="edit-settings-button"><Pencil size={16} /> Edit</button>
            </>
          )}
        </div>
      </form>

      {business && (
        <div className="form-card">
          <h2 style={{ fontSize: '1.05rem', marginTop: 0 }}>Your QR code &amp; link</h2>
          <p className="page-help" style={{ marginTop: 0 }}>
            Status: {business.is_active
              ? <span className="status-pill on" data-testid="settings-link-status">ACTIVE</span>
              : <span className="status-pill off" data-testid="settings-link-status">ADD GOOGLE LINK</span>}
          </p>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
            {qr && <img src={qr} alt="Your review QR code" width={150} height={150} data-testid="business-qr-image" />}
            <div>
              <strong data-testid="settings-public-url">{business.public_url}</strong>
              <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
                <button className="btn btn-ghost" onClick={copyLink} data-testid="settings-copy-link"><Copy size={16} /> Copy link</button>
                <a className="btn btn-ghost" href={qr} download="review-qr.png" data-testid="settings-download-qr"><Download size={16} /> Download QR</a>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
