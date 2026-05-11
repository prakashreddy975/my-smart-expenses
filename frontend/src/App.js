import React, { useState, useEffect, useCallback } from 'react';
import { api, setAuthToken, getStoredToken, clearStoredToken, persistToken } from './api';
import { 
  PlusCircle, Wallet, History, PieChart as PieIcon, 
  Trash2, RefreshCw, Landmark, CreditCard, DollarSign, 
  Receipt, TrendingUp, Edit3, Check, X, ShieldCheck, Tag, User, FileText, LogOut
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

function App() {
  // --- DATA STATES ---
  const [expenses, setExpenses] = useState([]);
  const [banks, setBanks] = useState([]);
  const [bills, setBills] = useState([]);
  const [analytics, setAnalytics] = useState({ total: 0, categories: {} });
  const [isSyncing, setIsSyncing] = useState(false);

  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [authError, setAuthError] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regPassword2, setRegPassword2] = useState('');

  // --- EDITING STATES ---
  const [editExpId, setEditExpId] = useState(null);
  const [editExpData, setEditExpData] = useState({});
  const [editBankId, setEditBankId] = useState(null);
  const [editBankData, setEditBankData] = useState({});
  const [editBillId, setEditBillId] = useState(null);
  const [editBillData, setEditBillData] = useState({});

  // --- FORM STATES ---
  const [form, setForm] = useState({ 
    date: new Date().toISOString().split('T')[0], 
    category: 'Food', description: '', amount: '', payment_method: 'LIQ' 
  });
  const [bankForm, setBankForm] = useState({ bank_name: '', balance: '' });
  const [billForm, setBillForm] = useState({ 
    card_name: 'CC : Amex', bill_date: '', bill_amount: '', paid_amount: '', paid_date: '', from_bank: '' 
  });

  const logout = useCallback(() => {
    clearStoredToken();
    setAuthToken(null);
    setUser(null);
    setExpenses([]);
    setBanks([]);
    setBills([]);
    setAnalytics({ total: 0, categories: {} });
  }, []);

  const fetchData = useCallback(async () => {
    setIsSyncing(true);
    try {
      const t = Date.now();
      const [resExp, resAnl, resBnk, resBil] = await Promise.all([
        api.get(`expenses?_t=${t}`),
        api.get(`analytics?_t=${t}`),
        api.get(`banks?_t=${t}`),
        api.get(`bills?_t=${t}`)
      ]);
      setExpenses(resExp.data || []);
      setAnalytics(resAnl.data || { total: 0, categories: {} });
      setBanks(resBnk.data || []);
      setBills(resBil.data || []);
    } catch (err) {
      if (err.response?.status === 401) logout();
      console.error("Sync Failed");
    }
    finally { setTimeout(() => setIsSyncing(false), 600); }
  }, [logout]);

  useEffect(() => {
    let cancelled = false;
    const token = getStoredToken();
    if (!token) {
      setAuthToken(null);
      setAuthReady(true);
      return undefined;
    }
    setAuthToken(token);
    api.get('auth/me')
      .then((res) => { if (!cancelled) setUser(res.data); })
      .catch(() => {
        if (!cancelled) {
          clearStoredToken();
          setAuthToken(null);
        }
      })
      .finally(() => { if (!cancelled) setAuthReady(true); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    fetchData();
    return undefined;
  }, [user, fetchData]);

  const onLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const { data } = await api.post('auth/login', { email: loginEmail.trim(), password: loginPassword });
      persistToken(data.token);
      setAuthToken(data.token);
      setUser(data.user);
      setLoginPassword('');
    } catch (err) {
      setAuthError(err.response?.data?.error || 'Sign in failed');
    }
  };

  const onRegister = async (e) => {
    e.preventDefault();
    setAuthError('');
    if (regPassword !== regPassword2) {
      setAuthError('Passwords do not match');
      return;
    }
    try {
      const { data } = await api.post('auth/register', { email: regEmail.trim(), password: regPassword });
      persistToken(data.token);
      setAuthToken(data.token);
      setUser(data.user);
    } catch (err) {
      setAuthError(err.response?.data?.error || 'Registration failed');
    }
  };

  // --- CALCULATIONS ---
  const totalBankSavings = banks.reduce((sum, b) => sum + parseFloat(b.balance || 0), 0);
  const totalDebtPaid = bills.reduce((sum, b) => sum + parseFloat(b.paid_amount || 0), 0);
  const postBillSavings = totalBankSavings - totalDebtPaid;

  // --- SUBMIT ACTIONS ---
  const handleExpenseSubmit = async (e) => {
    e.preventDefault();
    await api.post('expenses', { ...form, amount: parseFloat(form.amount) });
    setForm({ ...form, amount: '', description: '', payment_method: 'LIQ', category: 'Food' });
    fetchData();
  };

  const handleBankSubmit = async (e) => {
    e.preventDefault();
    await api.post('banks', { ...bankForm, balance: parseFloat(bankForm.balance) });
    setBankForm({ bank_name: '', balance: '' });
    fetchData();
  };

  const handleBillSubmit = async (e) => {
    e.preventDefault();
    await api.post('bills', billForm);
    setBillForm({ card_name: 'CC : Amex', bill_date: '', bill_amount: '', paid_amount: '', paid_date: '', from_bank: '' });
    fetchData();
  };

  // --- UPDATE ACTIONS ---
  const saveEditExp = async () => { await api.put(`expenses/${editExpId}`, editExpData); setEditExpId(null); fetchData(); };
  const saveEditBank = async () => { await api.put(`banks/${editBankId}`, editBankData); setEditBankId(null); fetchData(); };
  const saveEditBill = async () => { await api.put(`bills/${editBillId}`, editBillData); setEditBillId(null); fetchData(); };

  const deleteItem = async (type, id) => {
    if (!window.confirm("Permanently delete?")) return;
    await api.delete(`${type}/${id}`);
    fetchData();
  };

  const COLORS = ['#4361EE', '#3A86FF', '#06D6A0', '#FFBE0B', '#FB5607', '#FF006E', '#8338EC', '#2EC4B6', '#E63946', '#8D99AE'];
  const chartData = Object.entries(analytics.categories || {}).map(([name, value]) => ({ name, value: parseFloat(value) || 0 }));

  if (!authReady) {
    return (
      <div className="d-flex justify-content-center align-items-center text-muted" style={{ minHeight: '100vh', backgroundColor: '#f4f7fc' }}>
        Loading…
      </div>
    );
  }

  if (!user) {
    return (
      <div className="d-flex align-items-center py-5" style={{ backgroundColor: '#f4f7fc', minHeight: '100vh' }}>
        <div className="container" style={{ maxWidth: 420 }}>
          <div className="card shadow-sm border-0 rounded-4">
            <div className="card-body p-4">
              <h4 className="fw-bold mb-1">Smart Expense Tracker</h4>
              <p className="text-muted small mb-3">{authMode === 'login' ? 'Sign in with your email' : 'Create your account'}</p>
              {authError ? <div className="alert alert-danger py-2 small mb-3">{authError}</div> : null}
              {authMode === 'login' ? (
                <form onSubmit={onLogin}>
                  <label className="form-label small text-muted">Email</label>
                  <input type="email" className="form-control form-control-sm mb-2" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required autoComplete="username" />
                  <label className="form-label small text-muted">Password</label>
                  <input type="password" className="form-control form-control-sm mb-3" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required autoComplete="current-password" />
                  <button type="submit" className="btn btn-primary w-100 fw-bold rounded-3">Sign in</button>
                </form>
              ) : (
                <form onSubmit={onRegister}>
                  <label className="form-label small text-muted">Email</label>
                  <input type="email" className="form-control form-control-sm mb-2" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} required autoComplete="username" />
                  <label className="form-label small text-muted">Password (8+ characters)</label>
                  <input type="password" className="form-control form-control-sm mb-2" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} required autoComplete="new-password" />
                  <label className="form-label small text-muted">Confirm password</label>
                  <input type="password" className="form-control form-control-sm mb-3" value={regPassword2} onChange={(e) => setRegPassword2(e.target.value)} required autoComplete="new-password" />
                  <button type="submit" className="btn btn-primary w-100 fw-bold rounded-3">Create account</button>
                </form>
              )}
              <button type="button" className="btn btn-link btn-sm w-100 mt-2" onClick={() => { setAuthMode(authMode === 'login' ? 'register' : 'login'); setAuthError(''); }}>
                {authMode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ backgroundColor: '#f4f7fc', minHeight: '100vh', paddingBottom: '60px' }}>
      
      {/* BEAUTIFUL HEADER */}
      <div className="bg-white border-bottom shadow-sm mb-5 pt-4 pb-3">
        <div className="container">
          <div className="d-flex justify-content-between align-items-center">
            <div className="d-flex align-items-center">
              <div className="bg-primary rounded-circle p-2 me-3"><User size={24} className="text-white" /></div>
              <div>
                <h4 className="fw-bold text-dark mb-0">Welcome back</h4>
                <small className="text-muted"><ShieldCheck size={12} className="text-success" /> {user.email}</small>
              </div>
            </div>
            <div className="d-flex gap-2 align-items-center">
              <button type="button" onClick={logout} className="btn btn-outline-secondary rounded-pill px-3 btn-sm">
                <LogOut size={16} className="me-1" /> Log out
              </button>
              <button onClick={fetchData} className="btn btn-primary rounded-pill px-4 fw-bold shadow-sm">
                <RefreshCw size={16} className={`me-2 ${isSyncing ? 'animate-spin' : ''}`} /> Sync Hub
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="container">
        {/* TOP METRICS */}
        <div className="row g-3 mb-5 text-center">
          <div className="col-md-4">
            <div className="card border-0 shadow-sm p-4 rounded-4 bg-white">
              <Landmark className="text-success mb-2 mx-auto" size={28} />
              <small className="fw-bold text-muted text-uppercase small">Bank Total</small>
              <h2 className="fw-bold m-0">${totalBankSavings.toLocaleString()}</h2>
            </div>
          </div>
          <div className="col-md-4">
            <div className="card border-0 shadow-sm p-4 rounded-4 bg-white border-top border-primary border-4">
              <ShieldCheck className="text-primary mb-2 mx-auto" size={28} />
              <small className="fw-bold text-muted text-uppercase small">Post-Bill Savings</small>
              <h2 className="fw-bold m-0">${postBillSavings.toLocaleString()}</h2>
            </div>
          </div>
          <div className="col-md-4">
            <div className="card border-0 shadow-sm p-4 rounded-4 bg-dark text-white">
              <TrendingUp className="text-warning mb-2 mx-auto" size={28} />
              <small className="fw-bold opacity-75 text-uppercase small">Expense Outflow</small>
              <h2 className="fw-bold m-0 text-warning">${Number(analytics.total || 0).toLocaleString()}</h2>
            </div>
          </div>
        </div>

        <div className="row g-4">
          {/* --- LEFT: MANAGEMENT --- */}
          <div className="col-lg-4">
            <div className="card border-0 shadow-sm rounded-4 p-4 mb-4">
              <h6 className="fw-bold text-muted mb-4"><PlusCircle size={18} className="me-2 text-primary"/>Log Transaction</h6>
              <form onSubmit={handleExpenseSubmit}>
                <input type="date" className="form-control form-control-sm mb-2 bg-light border-0" value={form.date} onChange={e => setForm({...form, date: e.target.value})} required/>
                <select className="form-select form-select-sm mb-2 bg-light border-0" value={form.category} onChange={e => setForm({...form, category: e.target.value})}>
                  <option>Food</option><option>Home</option><option>CC Bills</option><option>Subscription</option><option>Shopping</option><option>Travel</option><option>Entertainment</option><option>Health</option><option>Other</option>
                </select>
                <select className="form-select form-select-sm mb-2 bg-light border-0" value={form.payment_method} onChange={e => setForm({...form, payment_method: e.target.value})}>
                  <option value="LIQ">LIQ</option><option value="DC BOFA">DC BOFA</option><option value="DC CHASE">DC CHASE</option><option value="CC : Amex">CC : Amex</option><option value="CC : BOFA">CC : BOFA</option><option value="CC : Chase">CC : Chase</option><option value="CC : Discover">CC : Discover</option>
                </select>
                <input className="form-control form-control-sm mb-3 bg-light border-0" placeholder="Description" value={form.description} onChange={e => setForm({...form, description: e.target.value})} />
                <div className="input-group input-group-sm mb-3">
                  <span className="input-group-text bg-primary text-white border-0">$</span>
                  <input type="number" step="0.01" className="form-control" placeholder="Amount" value={form.amount} onChange={e => setForm({...form, amount: e.target.value})} required/>
                </div>
                <button className="btn btn-primary btn-sm w-100 fw-bold rounded-3">Add Expense</button>
              </form>
            </div>

            <div className="card border-0 shadow-sm rounded-4 p-4 mb-4">
              <h6 className="fw-bold text-muted mb-3"><Landmark size={18} className="me-2 text-success"/>Banks</h6>
              <form onSubmit={handleBankSubmit}>
                <input className="form-control form-control-sm mb-2" placeholder="Bank Name" value={bankForm.bank_name} onChange={e => setBankForm({...bankForm, bank_name: e.target.value})} required/>
                <input type="number" className="form-control form-control-sm mb-3" placeholder="Balance" value={bankForm.balance} onChange={e => setBankForm({...bankForm, balance: e.target.value})} required/>
                <button className="btn btn-success btn-sm w-100 fw-bold">Update Bank</button>
              </form>
            </div>

            <div className="card border-0 shadow-sm rounded-4 p-4 mb-4" style={{ borderLeft: '4px solid #f72585' }}>
              <h6 className="fw-bold text-muted mb-3 d-flex align-items-center"><Receipt size={18} className="me-2 text-danger" />Log Credit Bill</h6>
              <form onSubmit={handleBillSubmit}>
                <select className="form-select form-select-sm mb-2 bg-light border-0" value={billForm.card_name} onChange={e => setBillForm({...billForm, card_name: e.target.value})} required>
                  <option value="CC : Amex">CC : Amex</option><option value="CC : BOFA">CC : BOFA</option><option value="CC : Chase">CC : Chase</option><option value="CC : Discover">CC : Discover</option>
                </select>
                <div className="row g-2 mb-2">
                  <div className="col-6"><small className="text-muted small">Bill Date</small><input type="date" className="form-control form-control-sm bg-light border-0" value={billForm.bill_date} onChange={e => setBillForm({...billForm, bill_date: e.target.value})} /></div>
                  <div className="col-6"><small className="text-muted small">Paid Date</small><input type="date" className="form-control form-control-sm bg-light border-0" value={billForm.paid_date} onChange={e => setBillForm({...billForm, paid_date: e.target.value})} /></div>
                </div>
                <input type="number" className="form-control form-control-sm mb-2" placeholder="Generated Amt" value={billForm.bill_amount} onChange={e => setBillForm({...billForm, bill_amount: e.target.value})} />
                <input type="number" className="form-control form-control-sm mb-2" placeholder="Paid Amt" value={billForm.paid_amount} onChange={e => setBillForm({...billForm, paid_amount: e.target.value})} />
                <select className="form-select form-select-sm mb-3" value={billForm.from_bank} onChange={e => setBillForm({...billForm, from_bank: e.target.value})}>
                  <option value="">Paid From Bank?</option>
                  {banks.map(b => <option key={b.id} value={b.bank_name}>{b.bank_name}</option>)}
                </select>
                <button className="btn btn-dark btn-sm w-100 fw-bold">Archive Bill</button>
              </form>
            </div>
          </div>

          {/* --- RIGHT: DISPLAY --- */}
          <div className="col-lg-8">
            <div className="card border-0 shadow-sm rounded-4 p-4 mb-4">
              <h6 className="fw-bold text-muted mb-4 d-flex align-items-center"><PieIcon size={18} className="me-2 text-primary" /> Analysis</h6>
              <div style={{ height: '220px' }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={chartData} innerRadius={60} outerRadius={85} dataKey="value" paddingAngle={8}>
                      {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} cornerRadius={4} />)}
                    </Pie>
                    <Tooltip />
                    <Legend verticalAlign="middle" align="right" layout="vertical" />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* BANK ACCOUNT TABLE (RESTORED) */}
            <div className="card border-0 shadow-sm rounded-4 p-4 mb-4">
              <h6 className="fw-bold mb-3 d-flex align-items-center text-success"><Landmark size={18} className="me-2" /> Bank Accounts</h6>
              <table className="table table-sm table-borderless align-middle m-0">
                <thead className="small text-secondary border-bottom"><tr><th>ACCOUNT</th><th className="text-end">BALANCE</th><th className="text-end">ACTIONS</th></tr></thead>
                <tbody>
                  {banks.map(b => (
                    <tr key={b.id} className="border-bottom">
                      {editBankId === b.id ? (
                        <>
                          <td><input className="form-control form-control-sm" value={editBankData.bank_name} onChange={e => setEditBankData({...editBankData, bank_name: e.target.value})} /></td>
                          <td><input type="number" className="form-control form-control-sm" value={editBankData.balance} onChange={e => setEditBankData({...editBankData, balance: e.target.value})} /></td>
                          <td className="text-end"><button onClick={saveEditBank} className="btn btn-sm text-success p-1"><Check size={18}/></button></td>
                        </>
                      ) : (
                        <>
                          <td className="fw-bold py-2">{b.bank_name}</td>
                          <td className="text-end fw-bold text-success">${parseFloat(b.balance).toLocaleString()}</td>
                          <td className="text-end">
                            <button onClick={() => {setEditBankId(b.id); setEditBankData(b);}} className="btn btn-sm text-primary opacity-50 p-1"><Edit3 size={14}/></button>
                            <button onClick={() => deleteItem('banks', b.id)} className="btn btn-sm text-danger opacity-50 p-1"><Trash2 size={14}/></button>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* CREDIT BILLS ARCHIVE */}
            <div className="card border-0 shadow-sm rounded-4 p-4 mb-4">
              <h6 className="fw-bold text-muted small mb-3">Credit Card Archive</h6>
              <div className="table-responsive">
                <table className="table table-sm table-borderless align-middle m-0">
                  <thead className="small text-secondary border-bottom">
                    <tr><th>CARD</th><th>DATE</th><th>GEN</th><th>PAID</th><th>BAL DUE</th><th className="text-end">ACTIONS</th></tr>
                  </thead>
                  <tbody>
                    {bills.map(bl => {
                      const balanceDue = parseFloat(bl.bill_amount || 0) - parseFloat(bl.paid_amount || 0);
                      return (
                        <tr key={bl.id} className="border-bottom">
                          {editBillId === bl.id ? (
                            <td colSpan="6"><div className="d-flex align-items-center">
                              <input className="form-control form-control-sm me-1" value={editBillData.card_name} onChange={e => setEditBillData({...editBillData, card_name: e.target.value})} />
                              <input type="date" className="form-control form-control-sm" value={editBillData.bill_date} onChange={e => setEditBillData({...editBillData, bill_date: e.target.value})} />
                              <input type="number" className="form-control form-control-sm me-1" value={editBillData.bill_amount} onChange={e => setEditBillData({...editBillData, bill_amount: e.target.value})} />
                              <input type="number" className="form-control form-control-sm" placeholder="Paid" value={editBillData.paid_amount} onChange={e => setEditBillData({...editBillData, paid_amount: e.target.value})} />
                              <button onClick={saveEditBill} className="btn btn-sm text-success"><Check size={18}/></button>
                            </div></td>
                          ) : (
                            <>
                              <td className="fw-bold py-2">{bl.card_name}</td>
                              <td className="small text-muted">{bl.bill_date}</td>
                              <td className="small text-muted">${bl.bill_amount}</td>
                              <td className="text-primary fw-bold small">${bl.paid_amount}</td>
                              <td className={`fw-bold small ${balanceDue > 0 ? 'text-danger' : 'text-success'}`}>${balanceDue.toFixed(2)}</td>
                              <td className="text-end">
                                  <button onClick={() => {setEditBillId(bl.id); setEditBillData(bl);}} className="btn btn-sm text-primary opacity-50"><Edit3 size={14}/></button>
                                  <button onClick={() => deleteItem('bills', bl.id)} className="btn btn-sm text-danger opacity-50"><Trash2 size={14}/></button>
                              </td>
                            </>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* TRANSACTION HISTORY */}
            <div className="card border-0 shadow-sm rounded-4 p-4">
              <h6 className="fw-bold text-muted small mb-3">Transaction History</h6>
              <div className="table-responsive">
                <table className="table table-sm align-middle m-0">
                  <thead className="small text-secondary border-bottom"><tr><th>DATE</th><th>CATEGORY</th><th>METHOD</th><th>DESC</th><th>AMT</th><th className="text-end">ACTIONS</th></tr></thead>
                  <tbody>
                    {[...expenses].reverse().slice(0, 10).map(e => (
                      <tr key={e.id} className="border-bottom">
                        {editExpId === e.id ? (
                          <td colSpan="6"><div className="d-flex align-items-center">
                            <input type="date" className="form-control form-control-sm me-1" value={editExpData.date} onChange={e => setEditExpData({...editExpData, date: e.target.value})} />
                            <select className="form-select form-select-sm" value={editExpData.category} onChange={e => setEditExpData({...editExpData, category: e.target.value})}>
                              <option>Food</option><option>Home</option><option>CC Bills</option><option>Subscription</option><option>Shopping</option><option>Travel</option><option>Entertainment</option><option>Health</option><option>Other</option>
                            </select>
                            <select className="form-select form-select-sm" value={editExpData.payment_method}
                                onChange={e => setEditExpData({...editExpData, payment_method: e.target.value})}>
                              <option value="LIQ">LIQ</option><option value="DC BOFA">DC BOFA</option><option value="DC CHASE">DC CHASE</option><option value="CC : Amex">CC : Amex</option><option value="CC : BOFA">CC : BOFA</option><option value="CC : Chase">CC : Chase</option><option value="CC : Discover">CC : Discover</option>
                            </select>
                            <input className="form-control form-control-sm me-1" value={editExpData.description} onChange={e => setEditExpData({...editExpData, description: e.target.value})} />
                            <input type="number" className="form-control form-control-sm me-1" value={editExpData.amount} onChange={e => setEditExpData({...editExpData, amount: e.target.value})} />
                            

                            
                            <button onClick={saveEditExp} className="btn btn-sm text-success"><Check size={18}/></button>
                          </div></td>
                        ) : (
                          <>
                            <td className="small py-3">{e.date}</td>
                            <td><span className="badge bg-primary-subtle text-primary border-0 px-2 small">{e.category}</span></td>
                            <td><span className="badge bg-info-subtle text-info border-0 px-2 small">{e.payment_method}</span></td>
                            <td className="small text-dark">{e.description || '—'}</td>
                            <td className="fw-bold text-dark text-nowrap">${parseFloat(e.amount).toFixed(2)}</td>
                            <td className="text-end">
                              <button onClick={() => {setEditExpId(e.id); setEditExpData(e);}} className="btn btn-sm text-primary opacity-50"><Edit3 size={14}/></button>
                              <button onClick={() => deleteItem('expenses', e.id)} className="btn btn-sm text-danger opacity-50 ms-1"><Trash2 size={14}/></button>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}

export default App;