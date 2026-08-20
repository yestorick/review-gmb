import { useEffect, useRef, useState } from 'react';
import { Check, Copy, Download, ImagePlus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';

const BACKEND = process.env.REACT_APP_BACKEND_URL;

function ImageUpload({ kind, label, hint, url, onChange }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    const body = new FormData();
    body.append('file', file);
    try {
      const r = await api.post(`/business/image/${kind}`, body, { headers: { 'Content-Type': 'multipart/form-data' } });
      onChange(r.data);
      toast.success(`${label} updated`);
    } catch (x) { toast.error(errText(x)); } finally { setBusy(false); e.target.value = ''; }
  };
  const remove = async () => {
    try {
      onChange((await api.delete(`/business/image/${kind}`)).data);
      toast.success(`${label} removed`);
    } catch (x) { toast.error(errText(x)); }
  };

  return (
    <div className="upload-box">
      <div>
        <strong>{label}</strong>
        <p className="page-help" style={{ margin: '4px 0 0' }}>{hint}</p>
      </div>
      {url ? (
        <img src={`${BACKEND}${url}`} alt={label} className={kind === 'logo' ? 'preview-logo' : 'preview-photo'} data-testid={`${kind}-preview`}
          onError={() => toast.error(`${label} could not be loaded. Please upload it again.`)} />
      ) : (
        <div className="preview-empty" data-testid={`${kind}-empty`}><ImagePlus size={22} /></div>
      )}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => input.current.click()} data-testid={`${kind}-upload-button`}>
          <ImagePlus size={16} /> {busy ? 'Uploading…' : url ? `Change ${label.toLowerCase()}` : `Upload ${label.toLowerCase()}`}
        </button>
        {url && <button type="button" className="btn btn-ghost danger" onClick={remove} data-testid={`${kind}-remove-button`}><Trash2 size={16} /> Remove</button>}
      </div>
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={upload} data-testid={`${kind}-file-input`} />
    </div>
  );
}

export default function Settings() {
  const [form, setForm] = useState({ name: '', business_category: '', location: '', service_area: '', google_review_url: '' });
  const [business, setBusiness] = useState(null);
  const [qr, setQr] = useState('');
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    (async () => {
      const b = (await api.get('/settings')).data.business;
      setBusiness(b);
      setForm({
        name: b.name || '', business_category: b.business_category || '', location: b.location || '',
        service_area: b.service_area || '', google_review_url: b.google_review_url || '',
      });
      setQr((await api.get(`/public/${b.public_slug}/qr`)).data.data_url);
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
          <button className="btn btn-primary" type="submit" data-testid="save-settings-button"><Check size={18} /> Save</button>
        </div>
      </form>

      {business && (
        <div className="form-card" style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.05rem', marginTop: 0 }}>Your logo &amp; shop photo</h2>
          <p className="page-help" style={{ marginTop: 0 }}>These show on your customer page, so people know they are in the right place.</p>
          <div className="upload-grid">
            <ImageUpload kind="logo" label="Logo" hint="A square image works best. JPG, PNG or WEBP, up to 5 MB."
              url={business.logo_url} onChange={setBusiness} />
            <ImageUpload kind="photo" label="Shop photo" hint="A clear photo of your shop, clinic or team." url={business.photo_url} onChange={setBusiness} />
          </div>
        </div>
      )}

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
                <button className="btn btn-ghost" onClick={() => { navigator.clipboard.writeText(business.public_url); toast.success('Link copied'); }} data-testid="settings-copy-link"><Copy size={16} /> Copy link</button>
                <a className="btn btn-ghost" href={qr} download="review-qr.png" data-testid="settings-download-qr"><Download size={16} /> Download QR</a>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
