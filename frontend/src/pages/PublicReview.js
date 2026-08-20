import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../api';

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function PublicReview() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/public/${slug}`).then((r) => setData(r.data)).catch(() => setData(false));
  }, [slug]);

  const choose = async (id) => {
    setBusy(true);
    try {
      const r = await api.post(`/public/${slug}/use/${id}`);
      await navigator.clipboard.writeText(r.data.text);
      window.location.href = r.data.google_url;
    } catch {
      toast.error('Please tap again to copy your review');
      setBusy(false);
    }
  };

  if (data === false) return <div className="public-page"><div className="center-box"><span className="brand-mark">R</span><h1>Link not found</h1><p>This review link may be mistyped or not set up yet.</p></div></div>;
  if (!data) return <div className="loading-screen">Loading…</div>;

  const { business } = data;

  return (
    <div className="public-page">
      <div className="public-inner">
        {business.photo_url && <img className="public-photo" src={`${BACKEND}${business.photo_url}`} alt={business.name} data-testid="public-photo" onError={(e) => { e.currentTarget.style.display = 'none'; }} />}
        <div className="public-identity">
          {business.logo_url
            ? <img className="public-logo" src={`${BACKEND}${business.logo_url}`} alt={`${business.name} logo`} data-testid="public-logo" />
            : <span className="brand-mark">R</span>}
          <div>
            <h1 data-testid="public-business-name">{business.name || 'Leave a review'}</h1>
            {(business.category || business.location) && <p className="sub" style={{ margin: 0 }}>{[business.category, business.location].filter(Boolean).join(' · ')}</p>}
          </div>
        </div>
        <p className="sub">Tap the one that feels like your visit. We copy it for you.</p>
        <div className="review-cards">
          {data.drafts.map((d, i) => (
            <button className="review-card" key={d.id} disabled={busy} onClick={() => choose(d.id)} data-testid={`public-draft-${i}`}>
              <span>{d.text}</span>
              <ArrowRight size={18} />
            </button>
          ))}
        </div>
        <p className="public-foot">After tapping, paste it on Google and hit post. Takes 5 seconds.</p>
      </div>
    </div>
  );
}
