async function loadOITab() {
    const container = document.getElementById('oiList');
    container.innerHTML = '<div class="loading"><div class="spinner"></div>در حال دریافت Open Interest...</div>';
    try {
        const res = await fetch(`${API_URL}/coinglass/open-interest`);
        const data = await res.json();
        if (data?.data && data.data.length > 0) {
            let html = '';
            data.data.forEach(item => {
                const oiUsd = item.openInterestUsd || 0;
                html += `<div class="derivatives-card"><div class="derivatives-title">${item.symbol}</div><div class="derivatives-row"><span class="derivatives-label">Open Interest</span><span class="derivatives-value">$${formatVolume(oiUsd)}</span></div><div class="derivatives-row"><span class="derivatives-label">تعداد قرارداد</span><span class="derivatives-value">${formatVolume(item.openInterest || 0)}</span></div></div>`;
            });
            container.innerHTML = html || '<div class="empty">❌ داده‌ای پیدا نشد</div>';
            document.getElementById('resultsCount').innerHTML = '📊 Open Interest (OKX)';
        } else {
            container.innerHTML = `<div class="empty">❌ ${data?.error || 'خطا در دریافت داده‌ها'}</div>`;
        }
    } catch(e) { container.innerHTML = '<div class="empty">⚠️ خطا در دریافت Open Interest</div>'; }
}
