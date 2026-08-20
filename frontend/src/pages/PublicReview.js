import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ClipboardCheck, Quote } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../api';

export default function PublicReview() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('all');
  const [busy, setBusy] = useState(false);

  const load = () => api.get(`/public/${slug}`).then((r) => setData(r.data));
  useEffect(() => { load().catch(() => setData(false)); }, [slug]);

  const choose = async (id) => {
    setBusy(true);
    let result;
    try {
      result = (await api.post(`/public/${slug}/use/${id}`)).data;
    } catch (x) {
      if (x?.response?.status === 409) {
        toast.error('Someone just used that one. Pick another review.');
        load().catch(() => {});
      } else {
        toast.error('Please tap again to copy your review');
      }
      setBusy(false);
      return;
    }
    try {
      await navigator.clipboard.writeText(result.text);
    } catch {
      toast.message('Copy it from here, then paste on Google', { description: result.text });
    }
    window.location.href = result.google_url;
  };

  if (data === false) {
    return (
      <div className="public-page">
        <div className="center-box"><span className="brand-mark">R</span><h1>Link not found</h1><p>This review link may be mistyped or not set up yet.</p></div>
      </div>
    );
  }
  if (!data) return <div className="loading-screen">Loading…</div>;

  const { business, categories = [] } = data;
  const drafts = tab === 'all' ? data.drafts : data.drafts.filter((d) => d.category === tab);

  return (
    <div className="public-page">
      <div className="public-inner">
        <header className="public-head">
          <h1 data-testid="public-business-name">{business.name || 'Leave a review'}</h1>
          {(business.category || business.location) && (
            <p className="public-meta">{[business.category, business.location].filter(Boolean).join(' · ')}</p>
          )}
          <p className="public-lead">Pick the review that matches your visit. We copy it and open Google for you.</p>
        </header>

        {categories.length > 1 && (
          <div className="tab-strip" data-testid="public-tabs">
            <button className={`tab${tab === 'all' ? ' on' : ''}`} onClick={() => setTab('all')} data-testid="public-tab-all">All Reviews</button>
            {categories.map((c) => (
              <button key={c} className={`tab${tab === c ? ' on' : ''}`} onClick={() => setTab(c)} data-testid={`public-tab-${c}`}>{c}</button>
            ))}
          </div>
        )}

        {drafts.length === 0 ? (
          <div className="quote-card empty-card" data-testid="public-empty">
            <strong>All reviews are taken right now</strong>
            <p>Every ready-made review here has already been used. Please check back a little later — fresh ones are on the way.</p>
          </div>
        ) : (
          <div className="quote-list">
            {drafts.map((d, i) => (
              <article className="quote-card" key={d.id} data-testid={`public-draft-${i}`}>
                <Quote className="quote-mark" size={26} strokeWidth={0} fill="currentColor" />
                <p className="quote-text">{d.text}</p>
                <button className="copy-post" disabled={busy} onClick={() => choose(d.id)} data-testid={`public-copy-${i}`}>
                  <ClipboardCheck size={18} /> Copy &amp; Post
                </button>
              </article>
            ))}
          </div>
        )}

        <p className="public-foot">After tapping, just paste it on Google and hit post. Takes 5 seconds.</p>
      </div>
    </div>
  );
}
