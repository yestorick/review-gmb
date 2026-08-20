import { useEffect, useState } from 'react';
import { Plus, Shapes, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { api, errText } from '../api';
import { CategoryModal } from '../components/CategoryModal';

const shortDate = (iso) => new Date(iso).toLocaleDateString('en-GB').replaceAll('/', '-');

export default function Categories() {
  const [rows, setRows] = useState([]);
  const [showModal, setShowModal] = useState(false);

  const load = async () => {
    try { setRows((await api.get('/categories')).data); } catch (x) { toast.error(errText(x)); }
  };
  useEffect(() => { load(); }, []);

  const remove = async (id) => {
    if (!window.confirm('Delete this category?')) return;
    try { await api.delete(`/categories/${id}`); toast.success('Category deleted'); load(); } catch (x) { toast.error(errText(x)); }
  };

  return (
    <>
      {showModal && <CategoryModal onClose={() => setShowModal(false)} onCreated={() => { toast.success('Category added'); load(); }} />}

      <div className="page-head">
        <div>
          <h1 className="page-title" data-testid="categories-heading">Category List ({rows.length})</h1>
          <p className="page-help">Groups help you keep reviews tidy, like "haircut" or "home delivery".</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)} data-testid="add-category-button"><Plus size={18} /> ADD NEW</button>
      </div>

      <div className="card">
        {rows.length ? (
          <div className="table-wrap">
            <table data-testid="categories-table">
              <thead><tr><th>Sr. No.</th><th>Category Name</th><th>Created Date</th><th>Action</th></tr></thead>
              <tbody>
                {rows.map((c, i) => (
                  <tr key={c.id} data-testid={`category-row-${i}`}>
                    <td>{i + 1}</td>
                    <td>{c.name}</td>
                    <td>{shortDate(c.created_at)}</td>
                    <td><button className="icon-btn danger" onClick={() => remove(c.id)} data-testid={`category-delete-${i}`}><Trash2 size={17} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty" data-testid="categories-empty">
            <Shapes size={30} />
            <strong>No categories yet</strong>
            <span>Tap ADD NEW and type a simple group name.</span>
            <div style={{ marginTop: 18 }}><button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={18} /> ADD NEW</button></div>
          </div>
        )}
      </div>
    </>
  );
}
