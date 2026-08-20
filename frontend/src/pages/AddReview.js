import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';

const TONES = ['Mixed (recommended)', 'Friendly', 'Storytelling', 'Short & Direct', 'Natural', 'Detailed'];
const STYLES = ['Simple', 'Detailed', 'Story'];
const WORD_LIMITS = ['15-25 Words', '25-40 Words', '40-50 Words', '50-70 Words'];
const COUNTS = [10, 15, 25, 40, 50];

export default function AddReview() {
  const nav = useNavigate();
  const [categories, setCategories] = useState([]);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    category: '', business_name: '', business_category: '', keywords: '', usp: '', location: '',
    language: 'English', customLanguage: '', tone: 'Mixed (recommended)', style: 'Detailed',
    word_limit: '40-50 Words', count: 15, service_area: '', other_suggestion: '',
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  useEffect(() => {
    (async () => {
      const [cats, settings] = await Promise.all([api.get('/categories'), api.get('/settings')]);
      setCategories(cats.data);
      const b = settings.data.business || {};
      setForm((f) => ({
        ...f,
        category: f.category || cats.data[0]?.name || '',
        business_name: b.name || '',
        business_category: b.business_category || '',
        location: b.location || '',
        service_area: b.service_area || '',
        keywords: b.keywords || '',
        usp: b.usp || '',
      }));
    })().catch((x) => toast.error(errText(x)));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const { customLanguage, ...rest } = form;
    const payload = { ...rest, language: form.language === 'Other' ? customLanguage.trim() || 'English' : form.language };
    try {
      const r = await api.post('/reviews/generate', payload);
      toast.success(`${r.data.count} reviews are ready`);
      nav('/reviews');
    } catch (x) {
      toast.error(errText(x));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <Link to="/reviews" className="text-btn back-link" data-testid="back-to-reviews"><ArrowLeft size={16} /> Back</Link>
          <h1 className="page-title" style={{ display: 'block', width: 'fit-content' }} data-testid="add-review-heading">Add Reviews</h1>
          <p className="page-help">Fill this once. We write natural reviews your customers can post in one tap.</p>
        </div>
      </div>

      <form className="form-card" onSubmit={submit}>
        <div className="form-grid">
          <div className="field">
            <label>Review Category <span className="req">*</span><span className="hint">Group reviews, e.g. haircut, delivery</span></label>
            <input list="category-list" required value={form.category} onChange={set('category')} placeholder="Type or pick a group" data-testid="category-input" />
            <datalist id="category-list">{categories.map((c) => <option key={c.id} value={c.name} />)}</datalist>
          </div>
          <div className="field">
            <label>Business Name <span className="req">*</span></label>
            <input required minLength={2} value={form.business_name} onChange={set('business_name')} placeholder="Sharma Dental Clinic" data-testid="business-name-input" />
          </div>
          <div className="field">
            <label>Business Category <span className="req">*</span><span className="hint">What you do</span></label>
            <input required minLength={2} value={form.business_category} onChange={set('business_category')} placeholder="Dentist" data-testid="business-category-input" />
          </div>
          <div className="field">
            <label>Keywords <span className="req">*</span><span className="hint">Words people search, separated by commas</span></label>
            <input required minLength={2} value={form.keywords} onChange={set('keywords')} placeholder="best dentist kolkata, painless filling" data-testid="keywords-input" />
          </div>
          <div className="field">
            <label>What you are known for<span className="hint">Comma separated</span></label>
            <input value={form.usp} onChange={set('usp')} placeholder="friendly staff, same day appointment" data-testid="usp-input" />
          </div>
          <div className="field">
            <label>Location <span className="req">*</span></label>
            <input required minLength={2} value={form.location} onChange={set('location')} placeholder="Kolkata" data-testid="location-input" />
          </div>
          <div className="field">
            <label>Language <span className="req">*</span></label>
            <select value={form.language} onChange={set('language')} data-testid="language-select">
              <option>English</option>
              <option>Other</option>
            </select>
          </div>
          {form.language === 'Other' ? (
            <div className="field">
              <label>Which language? <span className="req">*</span><span className="hint">e.g. Hindi, Bengali, Banglish (Bengali in English letters)</span></label>
              <input required value={form.customLanguage} onChange={set('customLanguage')} placeholder="Type the language" data-testid="custom-language-input" />
            </div>
          ) : <div className="field" />}
          <div className="field">
            <label>Review Tone <span className="req">*</span></label>
            <select value={form.tone} onChange={set('tone')} data-testid="tone-select">
              {TONES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Review Style <span className="req">*</span></label>
            <select value={form.style} onChange={set('style')} data-testid="style-select">
              {STYLES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Review Length <span className="req">*</span></label>
            <select value={form.word_limit} onChange={set('word_limit')} data-testid="word-limit-select">
              {WORD_LIMITS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Service Area<span className="hint">Optional</span></label>
            <input value={form.service_area} onChange={set('service_area')} placeholder="Salt Lake, New Town" data-testid="service-area-input" />
          </div>
          <div className="field full">
            <label>How many reviews? <span className="req">*</span></label>
            <div className="count-row">
              {COUNTS.map((c) => (
                <button type="button" key={c} className={`count-opt${form.count === c ? ' on' : ''}`} onClick={() => setForm({ ...form, count: c })} data-testid={`count-option-${c}`}>{c}</button>
              ))}
            </div>
          </div>
          <div className="field full">
            <label>Anything else to mention?<span className="hint">Optional</span></label>
            <textarea value={form.other_suggestion} onChange={set('other_suggestion')} placeholder="Mention our new branch, avoid price talk" data-testid="other-suggestion-input" />
          </div>
        </div>
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" disabled={busy} data-testid="generate-reviews-button">
            <Sparkles size={18} /> {busy ? 'Writing your reviews…' : `Generate ${form.count} reviews`}
          </button>
          <span className="note">{busy ? 'This takes up to a minute. Please stay on this page.' : 'You can edit or delete any review afterwards.'}</span>
        </div>
      </form>
    </>
  );
}
