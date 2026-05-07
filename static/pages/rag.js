/* pages/rag.js — RAG index status page */

async function loadStatus() {
  const data = await apiFetch('/rag/status').catch(() => null);
  if (!data) { return; }
  renderConfig(data);
  renderIndexes(data.indexes || []);
}

function renderConfig(data) {
  const items = [
    { label: 'RAG Enabled', value: data.enabled ? '✓ yes' : '✗ no', highlight: data.enabled },
    { label: 'Embedding Model', value: data.embedding_model },
    { label: 'Chunk Size', value: data.chunk_size + ' tokens' },
    { label: 'Top-K', value: data.top_k + ' chunks' },
  ];
  document.getElementById('config-grid').innerHTML = items.map(i => `
    <div class="config-card${i.highlight === true ? ' enabled' : i.highlight === false ? ' disabled' : ''}">
      <div class="config-label">${esc(i.label)}</div>
      <div class="config-value">${esc(String(i.value))}</div>
    </div>
  `).join('');
}

function renderIndexes(indexes) {
  const table = document.getElementById('index-table');
  const empty = document.getElementById('no-indexes');
  const tbody = document.getElementById('index-tbody');
  if (!indexes.length) {
    table.style.display = 'none';
    empty.style.display = '';
    return;
  }
  table.style.display = '';
  empty.style.display = 'none';
  tbody.innerHTML = indexes.map(idx => `
    <tr>
      <td class="idx-source" title="${esc(idx.source)}">${esc(idx.source)}</td>
      <td><span class="state-badge state-${esc(idx.state)}">${esc(idx.state)}</span></td>
      <td>${idx.chunk_count || '—'}</td>
      <td class="idx-fp">${esc(idx.fingerprint ? idx.fingerprint.slice(0, 8) + '…' : '—')}</td>
    </tr>
  `).join('');
}

async function triggerIndex() {
  const source = document.getElementById('trigger-source').value.trim();
  if (!source) { toast('Enter a local repo path', true); return; }
  const btn = document.getElementById('trigger-btn');
  await withLoading(btn, 'Queuing…', async () => {
    await apiFetch('/rag/index', { method: 'POST', body: { source } });
    toast('Indexing started — refresh in a few seconds');
    document.getElementById('trigger-source').value = '';
    setTimeout(loadStatus, 1500);
  }).catch(e => toast('Failed: ' + e.message, true));
}

document.addEventListener('DOMContentLoaded', () => {
  loadStatus();
  document.getElementById('refresh-btn').addEventListener('click', loadStatus);
  document.getElementById('trigger-btn').addEventListener('click', triggerIndex);
});
