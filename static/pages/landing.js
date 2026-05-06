/* pages/landing.js — landing page stats */

async function loadStats() {
  try {
    const tickets = await apiFetch('/tickets');
    document.getElementById('s-total').textContent = tickets.length;
    document.getElementById('s-open').textContent = tickets.filter(t => t.status === 'open').length;
    const validated = tickets.filter(t => t.validation_passed !== null && t.validation_passed !== undefined);
    const passed = tickets.filter(t => t.validation_passed === true);
    document.getElementById('s-validated').textContent = validated.length;
    document.getElementById('s-passrate').textContent = validated.length
      ? Math.round(passed.length / validated.length * 100) + '%' : '—';
  } catch { /* ignore */ }
}

document.addEventListener('DOMContentLoaded', loadStats);
