// Stores the latest queue list so live search works without losing data on auto-refresh
let currentQueue = [];

// Safely escape text before placing it inside HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
}

// Removes "YYYY-MM-DD " so only the clock time (e.g. "03:45:10 PM") is shown
function formatTimeOnly(dateTimeStr) {
    return String(dateTimeStr ?? '').replace(/^\d{4}-\d{2}-\d{2}\s+/, '');
}

// Display today's date once in the top-right corner
function showTodayDate() {
    const today = new Date().toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
    document.getElementById('today-date').textContent = today;
}

// 1. Load Live Dashboard Stats (GET /api/stats)
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const stats = await res.json();

        const servingText = stats.currently_serving
            ? `Token #${stats.currently_serving.token_number} - ${stats.currently_serving.name}`
            : 'None';

        document.getElementById('stat-serving').textContent = servingText;
        document.getElementById('stat-waiting').textContent = stats.waiting_count;
        document.getElementById('stat-served').textContent = stats.served_count;
        document.getElementById('stat-cancelled').textContent = stats.cancelled_count;
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

// 2. Fetch Waiting Queue from Backend (GET /api/queue)
async function loadQueue() {
    try {
        const res = await fetch('/api/queue');
        const data = await res.json();
        currentQueue = data.queue || [];
        document.getElementById('queue-count').textContent = data.count;
        renderQueueTable();
    } catch (err) {
        console.error('Failed to load queue:', err);
    }
}

// Render (and filter) the Waiting Queue Table
function renderQueueTable() {
    const query = document.getElementById('queue-search').value.trim().toLowerCase();
    const emptyMsg = document.getElementById('empty-queue-msg');
    const table = document.getElementById('queue-table');
    const tbody = document.getElementById('queue-tbody');

    tbody.innerHTML = '';

    if (currentQueue.length === 0) {
        emptyMsg.textContent = 'The queue is currently empty.';
        emptyMsg.hidden = false;
        table.hidden = true;
        return;
    }

    // Keep each patient's real queue position even when filtered by search
    const filtered = currentQueue
        .map((patient, index) => ({ ...patient, _pos: index + 1 }))
        .filter((p) => {
            if (!query) return true;
            const nameMatch = String(p['Name']).toLowerCase().includes(query);
            const tokenMatch = String(p['Token Number']).includes(query);
            return nameMatch || tokenMatch;
        });

    if (filtered.length === 0) {
        emptyMsg.textContent = 'No matching patients found.';
        emptyMsg.hidden = false;
        table.hidden = true;
        return;
    }

    emptyMsg.hidden = true;
    table.hidden = false;

    filtered.forEach((patient) => {
        const tokenNum = patient['Token Number'];
        const isEmergency = String(patient['Ailment']).startsWith('[EMERGENCY]');
        const tr = document.createElement('tr');
        if (isEmergency) {
            tr.className = 'emergency-row';
        }

        tr.innerHTML = `
            <td>${patient._pos}</td>
            <td><strong>#${escapeHtml(tokenNum)}</strong></td>
            <td>${escapeHtml(patient['Name'])}</td>
            <td>${escapeHtml(patient['Age'])}</td>
            <td>${escapeHtml(patient['Gender'])}</td>
            <td>${escapeHtml(patient['Ailment'])}</td>
            <td>${escapeHtml(formatTimeOnly(patient['Time of entry']))}</td>
            <td>
                <button type="button" class="btn-row-cancel" onclick="cancelToken(${Number(tokenNum)})">Cancel</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function refreshAll() {
    await Promise.all([loadStats(), loadQueue()]);
}

// 3. Add Normal or Emergency Patient (POST /api/queue/add or /api/queue/emergency)
async function addPatient(isEmergency) {
    const form = document.getElementById('patient-form');
    const feedback = document.getElementById('add-feedback');

    if (!form.reportValidity()) {
        return;
    }

    const payload = {
        name: document.getElementById('name').value.trim(),
        age: document.getElementById('age').value,
        ailment: document.getElementById('ailment').value.trim(),
        gender: document.getElementById('gender').value
    };

    const endpoint = isEmergency ? '/api/queue/emergency' : '/api/queue/add';

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (!res.ok) {
            feedback.textContent = `Error: ${result.error || 'Could not add patient.'}`;
            return;
        }

        const d = result.data;
        const typeLabel = isEmergency ? 'EMERGENCY Token' : 'Token';
        feedback.textContent = `${typeLabel} #${d.token_number} issued to ${d.name} (Position: ${d.position_in_queue}, Time: ${formatTimeOnly(d.time_of_entry)}).`;
        form.reset();
        await refreshAll();
    } catch (err) {
        feedback.textContent = 'Network error while connecting to server.';
    }
}

// 4. Call Next Patient (POST /api/queue/next)
async function callNextPatient() {
    const resultDiv = document.getElementById('next-patient-result');

    try {
        const res = await fetch('/api/queue/next', { method: 'POST' });
        const data = await res.json();

        if (!res.ok) {
            resultDiv.innerHTML = `<p>${escapeHtml(data.message || 'The queue is empty.')}</p>`;
            await refreshAll();
            return;
        }

        const p = data.patient;
        resultDiv.innerHTML = `
            <p>
                <strong>Now Serving:</strong> Token #${escapeHtml(p.token_number)} - ${escapeHtml(p.name)}<br>
                <strong>Called At:</strong> ${escapeHtml(formatTimeOnly(p.exit_time))}<br>
                <strong>Wait Duration:</strong> ${escapeHtml(p.duration_minutes)} min ${escapeHtml(p.duration_seconds)} sec
            </p>
        `;
        await refreshAll();
    } catch (err) {
        resultDiv.textContent = 'Network error while calling next patient.';
    }
}

// 5. Check Token Status (GET /api/token/<token_number>)
async function checkTokenStatus() {
    const tokenInput = document.getElementById('token-input').value.trim();
    const resultDiv = document.getElementById('status-result');

    if (!tokenInput || Number(tokenInput) < 1) {
        resultDiv.innerHTML = '<p>Please enter a valid token number.</p>';
        return;
    }

    try {
        const res = await fetch(`/api/token/${encodeURIComponent(tokenInput)}`);
        const data = await res.json();

        const servingNow = data.currently_serving ? `Token #${data.currently_serving}` : 'None';
        let html = `<p><strong>Token #${escapeHtml(data.token_number)} Status:</strong> ${escapeHtml(data.status)}<br>`;

        if (data.status === 'Waiting') {
            html += `<strong>Queue Position:</strong> ${escapeHtml(data.position_in_queue)} (${escapeHtml(data.people_ahead)} ahead)<br>`;
        }

        html += `<strong>Currently Serving:</strong> ${escapeHtml(servingNow)}</p>`;
        resultDiv.innerHTML = html;
    } catch (err) {
        resultDiv.textContent = 'Network error while checking status.';
    }
}

// 6. Cancel a Waiting Token (DELETE /api/token/<token_number>)
async function cancelToken(tokenNumber) {
    if (!confirm(`Cancel Token #${tokenNumber}?`)) {
        return;
    }

    const resultDiv = document.getElementById('status-result');

    try {
        const res = await fetch(`/api/token/${encodeURIComponent(tokenNumber)}`, {
            method: 'DELETE'
        });
        const data = await res.json();

        if (!res.ok) {
            resultDiv.innerHTML = `<p>Error: ${escapeHtml(data.error || 'Could not cancel token.')}</p>`;
            return;
        }

        resultDiv.innerHTML = `<p>Token #${escapeHtml(data.data.token_number)} (${escapeHtml(data.data.name)}) has been cancelled.</p>`;
        await refreshAll();
    } catch (err) {
        resultDiv.textContent = 'Network error while cancelling token.';
    }
}

function cancelTokenFromInput() {
    const tokenInput = document.getElementById('token-input').value.trim();
    const resultDiv = document.getElementById('status-result');

    if (!tokenInput || Number(tokenInput) < 1) {
        resultDiv.innerHTML = '<p>Please enter a valid token number to cancel.</p>';
        return;
    }
    cancelToken(tokenInput);
}

document.addEventListener('DOMContentLoaded', () => {
    showTodayDate();
    refreshAll();
    setInterval(refreshAll, 5000);

    document.getElementById('token-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            checkTokenStatus();
        }
    });
});