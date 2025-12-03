const API_BASE = '/api/v1';

// Utilities
const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(amount);
};

const showNotification = (message, isError = false) => {
    const notif = document.getElementById('notification');
    notif.textContent = message;
    notif.style.borderColor = isError ? 'var(--error-color)' : 'var(--accent-color)';
    notif.classList.add('show');
    setTimeout(() => notif.classList.remove('show'), 3000);
};

// API Calls
const api = {
    async getCategories() {
        const res = await fetch(`${API_BASE}/budget/categories`);
        return res.json();
    },
    async getIncomeTransactions() {
        const res = await fetch(`${API_BASE}/budget/income-transactions`);
        return res.json();
    },
    async updateBudget(id, monthlyAmount) {
        const res = await fetch(`${API_BASE}/budget/categories/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monthly_amount: monthlyAmount.toString() })
        });
        if (!res.ok) throw new Error('Failed to update budget');
        return res.json();
    },
    async distributeIncome(transactionId) {
        const res = await fetch(`${API_BASE}/budget/distribute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transaction_id: parseInt(transactionId) })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Distribution failed');
        }
        return res.json();
    },
    async transferFunds(fromId, toId, amount, transferAll) {
        const payload = {
            from_category_id: parseInt(fromId),
            to_category_id: parseInt(toId),
            transfer_all: transferAll
        };
        if (!transferAll) payload.amount = amount.toString();

        const res = await fetch(`${API_BASE}/budget/transfer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Transfer failed');
        }
        return res.json();
    },
    async uploadBackup(file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error('Upload failed');
        return res.json();
    }
};

// UI Rendering
const renderCategories = (categories) => {
    const grid = document.getElementById('categories-grid');
    grid.innerHTML = '';

    // Populate select options for transfer
    const fromSelect = document.getElementById('transfer-from');
    const toSelect = document.getElementById('transfer-to');
    const options = categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    fromSelect.innerHTML = '<option value="">Select Source</option>' + options;
    toSelect.innerHTML = '<option value="">Select Target</option>' + options;

    categories.forEach(cat => {
        const card = document.createElement('div');
        card.className = 'card category-card';
        card.innerHTML = `
            <div class="category-header">
                <div>
                    <span class="color-dot" style="background-color: ${cat.color || '#fff'}"></span>
                    <span class="category-name">${cat.name}</span>
                </div>
            </div>
            <div class="category-stats">
                <div class="amount-row">
                    <span class="amount-label">Monthly Budget</span>
                    <span class="amount-value">${formatCurrency(cat.monthlyAmount || 0)}</span>
                </div>
                <div class="amount-row">
                    <span class="amount-label">Total Available</span>
                    <span class="amount-value" style="color: ${(cat.totalAmount || 0) < 0 ? 'var(--error-color)' : 'var(--success-color)'}">${formatCurrency(cat.totalAmount || 0)}</span>
                </div>
            </div>
            <div class="actions">
                <button class="secondary" onclick="editBudget(${cat.id}, ${cat.monthlyAmount || 0})">Edit Budget</button>
            </div>
        `;
        grid.appendChild(card);
    });

    // Update Total Balance
    const totalBalance = categories.reduce((sum, cat) => sum + parseFloat(cat.totalAmount || 0), 0);
    document.getElementById('total-balance-amount').textContent = formatCurrency(totalBalance);
};

const renderIncomeTransactions = (transactions) => {
    const list = document.getElementById('income-transactions-list');
    list.innerHTML = '';

    if (transactions.length === 0) {
        list.innerHTML = '<p style="color: var(--text-secondary);">No recent income transactions found.</p>';
        return;
    }

    transactions.forEach(tx => {
        const item = document.createElement('div');
        item.className = 'transaction-item';
        item.innerHTML = `
            <div class="transaction-info">
                <span class="transaction-merchant">${tx.merchantName || tx.merchant_name || 'Unknown'}</span>
                <span class="transaction-date">${new Date(tx.dateTime || tx.date_time).toLocaleDateString()}</span>
                <span class="amount-value" style="color: var(--success-color)">${formatCurrency(tx.amount)}</span>
            </div>
            <button class="distribute-btn-small" onclick="distributeIncome(${tx.id})">Distribute</button>
        `;
        list.appendChild(item);
    });
};

// Event Handlers
window.distributeIncome = async (id) => {
    if (!confirm('Distribute this income?')) return;
    try {
        const res = await api.distributeIncome(id);
        showNotification(`Distributed! Remainder: ${formatCurrency(res.remainder)}`);
        loadData();
    } catch (e) {
        showNotification(e.message, true);
    }
};

window.editBudget = async (id, current) => {
    const newAmount = prompt("Enter new monthly amount:", current);
    if (newAmount !== null && !isNaN(newAmount)) {
        try {
            await api.updateBudget(id, newAmount);
            showNotification('Budget updated');
            loadData();
        } catch (e) {
            showNotification(e.message, true);
        }
    }
};

document.getElementById('transfer-form').onsubmit = async (e) => {
    e.preventDefault();
    const from = document.getElementById('transfer-from').value;
    const to = document.getElementById('transfer-to').value;
    const amount = document.getElementById('transfer-amount').value;
    const transferAll = document.getElementById('transfer-all').checked;

    if (!from || !to) return showNotification('Select categories', true);
    if (!transferAll && !amount) return showNotification('Enter amount', true);

    try {
        await api.transferFunds(from, to, amount, transferAll);
        showNotification('Transfer successful');
        loadData();
        e.target.reset();
    } catch (e) {
        showNotification(e.message, true);
    }
};

document.getElementById('upload-form').onsubmit = async (e) => {
    e.preventDefault();
    const file = document.getElementById('backup-file').files[0];
    if (!file) return showNotification('Select a file', true);

    try {
        await api.uploadBackup(file);
        showNotification('Backup uploaded and processed');
        loadData();
    } catch (e) {
        showNotification(e.message, true);
    }
};

document.getElementById('transfer-all').onchange = (e) => {
    document.getElementById('transfer-amount').disabled = e.target.checked;
};

// Init
const loadData = async () => {
    try {
        const [cats, txs] = await Promise.all([
            api.getCategories(),
            api.getIncomeTransactions()
        ]);
        renderCategories(cats);
        renderIncomeTransactions(txs);
    } catch (e) {
        console.error(e);
        showNotification('Failed to load data', true);
    }
};

loadData();
