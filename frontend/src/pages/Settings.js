import { useEffect, useState } from 'react';
import { Check, Copy, Download } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';

export default function Settings() {
  const [form, setForm] = useState({ name: '', business_category: '', location: '', service_area: '', google_review_url: '' });
  const [business, setBusiness] = useState(null);
  const [qr, setQr] = useState('');
  const [loaded, setLoaded] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

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
    })().catch((x) => toast.error(errText(x)));
  }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      setBusiness((await api.put('/settings', form)).data);
      toast.success('Saved');
    } catch (x) { toast.error(errText(x)); }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title" data-testid="settings-heading">My Business</h1>
          <p className="page-help">Paste your Google review link once. Then your QR code and link start working.</p>
        </div>
      </div>

      <form className="form-card" onSubmit={save} style={{ marginBottom: 18 }}>
        <div className="form-grid">
          <div className="field">
            <label>Business Name</label>
            <input value={form.name} onChange={set('name')} placeholder="Sharma Dental Clinic" data-testid="settings-name-input" />
          </div>
          <div className="field">
            <label>Business Category</label>
            <input value={form.business_category} onChange={set('business_category')} placeholder="Dentist" data-testid="settings-category-input" />
          </div>
          <div className="field">
            <label>Location</label>
            <input value={form.location} onChange={set('location')} placeholder="Kolkata" data-testid="settings-location-input" />
          </div>
          <div className="field">
            <label>Service Area<span className="hint">Optional</span></label>
            <input value={form.service_area} onChange={set('service_area')} placeholder="Salt Lake, New Town" data-testid="settings-service-area-input" />
          </div>
          <div className="field full">
            <label>Google Review Link<span className="hint">Open your Google listing, tap Reviews, then "Get more reviews" and copy that link</span></label>
            <input value={form.google_review_url} onChange={set('google_review_url')} placeholder="https://g.page/your-shop/review" data-testid="settings-google-url-input" />
          </div>
        </div>
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" disabled={!loaded} data-testid="save-settings-button"><Check size={18} /> {loaded ? 'Save' : 'Loading…'}</button>
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
