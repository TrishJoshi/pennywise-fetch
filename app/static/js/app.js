const API_BASE = '/api/v1';
let currentBuckets = [];
let currentMovingCategoryId = null;

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
    async getBuckets() {
        const res = await fetch(`${API_BASE}/budget/buckets`);
        return res.json();
    },
    async getIncomeTransactions() {
        const res = await fetch(`${API_BASE}/budget/income-transactions`);
        return res.json();
    },
    async getDistributions() {
        const res = await fetch(`${API_BASE}/budget/distributions`);
        return res.json();
    },
    async revertDistribution(id) {
        const res = await fetch(`${API_BASE}/budget/distributions/${id}/revert`, {
            method: 'POST'
        });
        if (!res.ok) throw new Error((await res.json()).detail);
        return res.json();
    },
    async resetBucket(id) {
        const res = await fetch(`${API_BASE}/budget/buckets/${id}/reset`, {
            method: 'POST'
        });
        if (!res.ok) throw new Error((await res.json()).detail);
        return res.json();
    },
    async deleteBucket(id) {
        const res = await fetch(`${API_BASE}/budget/buckets/${id}`, {
            method: 'DELETE'
        });
        if (!res.ok) throw new Error((await res.json()).detail);
        return res.json();
    },
    async updateBucketBudget(id, monthlyAmount) {
        const res = await fetch(`${API_BASE}/budget/buckets/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monthly_amount: monthlyAmount.toString() })
        });
        if (!res.ok) throw new Error('Failed to update budget');
        return res.json();
    },
    async moveCategory(categoryId, bucketId) {
        const res = await fetch(`${API_BASE}/budget/categories/${categoryId}/bucket?bucket_id=${bucketId}`, {
            method: 'PUT'
        });
        if (!res.ok) throw new Error('Failed to move category');
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
            from_bucket_id: parseInt(fromId),
            to_bucket_id: parseInt(toId),
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
const renderBuckets = (buckets) => {
    const grid = document.getElementById('categories-grid');
    grid.innerHTML = '';

    // Populate select options for transfer
    const fromSelect = document.getElementById('transfer-from');
    const toSelect = document.getElementById('transfer-to');
    const options = buckets.map(b => `<option value="${b.id}">${b.name}</option>`).join('');
    fromSelect.innerHTML = '<option value="">Select Source Bucket</option>' + options;
    toSelect.innerHTML = '<option value="">Select Target Bucket</option>' + options;

    buckets.forEach(bucket => {
        const card = document.createElement('div');
        card.className = 'card category-card';

        const totalAmount = parseFloat(bucket.totalAmount || 0);
        const isNegative = totalAmount < 0;

        // Categories List
        const categoriesList = bucket.categories.map(cat => `
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; padding: 4px 0; border-bottom: 1px solid #eee;">
                <span>${cat.name}</span>
                <button class="secondary" style="padding: 2px 6px; font-size: 0.7rem;" onclick="moveCategory(${cat.id})">Move</button>
            </div>
        `).join('');

        card.innerHTML = `
            <div class="category-header">
                <div>
                    <span class="category-name">${bucket.name}</span>
                    <span style="font-size: 0.8rem; color: var(--text-secondary);">(${bucket.categories.length} categories)</span>
                </div>
            </div>
            <div class="category-stats">
                <div class="amount-row">
                    <span class="amount-label">Monthly Budget</span>
                    <span class="amount-value">${formatCurrency(bucket.monthlyAmount || 0)}</span>
                </div>
                <div class="amount-row">
                    <span class="amount-label">Total Available</span>
                    <span class="amount-value" style="color: ${isNegative ? 'var(--error-color)' : 'var(--success-color)'}">${formatCurrency(totalAmount)}</span>
                </div>
            </div>
            
            <div style="margin: 10px 0; max-height: 100px; overflow-y: auto;">
                ${categoriesList}
            </div>

            <div class="actions">
                <button class="secondary" onclick="editBudget(${bucket.id}, ${bucket.monthlyAmount || 0})">Edit Budget</button>
                ${isNegative ? `
                    <button class="secondary" style="background-color: var(--warning-color); color: black;" onclick="resetBucket(${bucket.id})">Reset from Others</button>
                ` : ''}
                ${bucket.categories.length === 0 && totalAmount === 0 ? `
                    <button class="secondary" style="border-color: var(--error-color); color: var(--error-color);" onclick="deleteBucket(${bucket.id})">Delete</button>
                ` : ''}
            </div>
        `;
        grid.appendChild(card);
    });

    // Update Total Balance
    const totalBalance = buckets.reduce((sum, b) => sum + parseFloat(b.totalAmount || 0), 0);
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

const renderDistributionHistory = (events) => {
    const list = document.getElementById('distribution-history-list');
    list.innerHTML = '';

    if (events.length === 0) {
        list.innerHTML = '<p style="color: var(--text-secondary);">No distribution history.</p>';
        return;
    }

    events.forEach(event => {
        const item = document.createElement('div');
        item.className = 'transaction-item';
        item.style.flexDirection = 'column';
        item.style.alignItems = 'flex-start';

        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.justifyContent = 'space-between';
        header.style.width = '100%';
        header.style.marginBottom = '8px';

        header.innerHTML = `
            <div class="transaction-info">
                <span class="transaction-merchant">Distribution #${event.id}</span>
                <span class="transaction-date">${new Date(event.timestamp).toLocaleString()}</span>
            </div>
            <div style="text-align: right;">
                <span class="amount-value" style="color: var(--success-color)">${formatCurrency(event.totalAmount)}</span>
                ${event.isReverted ?
                '<span style="color: var(--error-color); font-size: 0.8rem; display: block;">Reverted</span>' :
                `<button class="distribute-btn-small" style="background-color: var(--error-color); margin-top: 4px;" onclick="revertDistribution(${event.id})">Revert</button>`
            }
            </div>
        `;

        const details = document.createElement('div');
        details.style.fontSize = '0.85rem';
        details.style.color = 'var(--text-secondary)';
        details.style.width = '100%';

        const logDetails = event.logs.map(log =>
            `${log.bucketName}: ${formatCurrency(log.amount)}`
        ).join(', ');

        details.textContent = logDetails;

        item.appendChild(header);
        item.appendChild(details);
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

window.revertDistribution = async (id) => {
    if (!confirm('Are you sure you want to revert this distribution? This will deduct the amounts from buckets.')) return;
    try {
        await api.revertDistribution(id);
        showNotification('Distribution reverted successfully');
        loadData();
    } catch (e) {
        showNotification(e.message, true);
    }
};

window.resetBucket = async (id) => {
    if (!confirm('Reset this bucket? This will transfer funds from "Others" to make the balance 0.')) return;
    try {
        await api.resetBucket(id);
        showNotification('Bucket reset successfully');
        loadData();
    } catch (e) {
        showNotification(e.message, true);
    }
};

window.deleteBucket = async (id) => {
    if (!confirm('Are you sure you want to delete this bucket?')) return;
    try {
        await api.deleteBucket(id);
        showNotification('Bucket deleted successfully');
        loadData();
    } catch (e) {
        showNotification(e.message, true);
    }
};

window.editBudget = async (id, current) => {
    const newAmount = prompt("Enter new monthly amount:", current);
    if (newAmount !== null && !isNaN(newAmount)) {
        try {
            await api.updateBucketBudget(id, newAmount);
            showNotification('Budget updated');
            loadData();
        } catch (e) {
            showNotification(e.message, true);
        }
    }
};

window.moveCategory = (categoryId) => {
    console.log('moveCategory called with ID:', categoryId);
    try {
        currentMovingCategoryId = categoryId;
        const modal = document.getElementById('move-category-modal');
        if (!modal) {
            console.error('Modal element not found');
            alert('Error: Modal element not found');
            return;
        }

        const select = document.getElementById('move-category-select');
        if (!select) {
            console.error('Select element not found');
            alert('Error: Select element not found');
            return;
        }

        if (!currentBuckets || !Array.isArray(currentBuckets)) {
            console.error('currentBuckets is invalid:', currentBuckets);
            currentBuckets = [];
        }

        const options = currentBuckets.map(b => `<option value="${b.id}">${b.name}</option>`).join('');
        select.innerHTML = '<option value="">Select Target Bucket</option>' + options;

        modal.classList.remove('hidden');
        console.log('Modal opened');
    } catch (e) {
        console.error('Error in moveCategory:', e);
        alert('Error: ' + e.message);
    }
};

window.closeMoveCategoryModal = () => {
    document.getElementById('move-category-modal').classList.add('hidden');
    currentMovingCategoryId = null;
};

window.confirmMoveCategory = async () => {
    const select = document.getElementById('move-category-select');
    const bucketId = select.value;

    if (!bucketId) {
        showNotification('Please select a target bucket', true);
        return;
    }

    try {
        await api.moveCategory(currentMovingCategoryId, bucketId);
        showNotification('Category moved');
        closeMoveCategoryModal();
        loadData();
    } catch (e) {
        showNotification(e.message, true);
    }
};

document.getElementById('transfer-form').onsubmit = async (e) => {
    e.preventDefault();
    const from = document.getElementById('transfer-from').value;
    const to = document.getElementById('transfer-to').value;
    const amount = document.getElementById('transfer-amount').value;
    const transferAll = document.getElementById('transfer-all').checked;

    if (!from || !to) return showNotification('Select buckets', true);
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
        const [buckets, txs, dists] = await Promise.all([
            api.getBuckets(),
            api.getIncomeTransactions(),
            api.getDistributions()
        ]);
        currentBuckets = buckets;
        renderBuckets(buckets);
        renderIncomeTransactions(txs);
        renderDistributionHistory(dists);
    } catch (e) {
        console.error(e);
        showNotification('Failed to load data', true);
    }
};

loadData();
