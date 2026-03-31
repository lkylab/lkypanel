import Chart from 'chart.js/auto';
import '../css/dashboard.css';

export function initDashboard(data) {
    console.log('initDashboard started with data:', data);
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748b', font: { size: 10 } } },
            y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748b', font: { size: 10 } }, min: 0, max: 100 }
        }
    };

    const labels = Array.from({length: 10}, (_, i) => `-${9-i}m`);
    let cpuChart, ramChart, diskChart, phpChart;

    try {
        cpuChart = new Chart(document.getElementById('cpuChart'), {
            type: 'line',
            data: {
                labels,
                datasets: [{ data: data.cpuHistory, borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.08)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 }]
            },
            options: chartDefaults
        });
    } catch (e) { console.error('Failed to init CPU chart:', e); }

    try {
        ramChart = new Chart(document.getElementById('ramChart'), {
            type: 'line',
            data: {
                labels,
                datasets: [{ data: data.ramHistory, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.08)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 }]
            },
            options: chartDefaults
        });
    } catch (e) { console.error('Failed to init RAM chart:', e); }

    try {
        const diskOpts = JSON.parse(JSON.stringify(chartDefaults));
        diskOpts.scales.y.max = 100;
        diskChart = new Chart(document.getElementById('diskChart'), {
            type: 'bar',
            data: {
                labels: ['Used', 'Free'],
                datasets: [{ data: [data.diskPercent, data.diskFreePercent], backgroundColor: ['rgba(129,140,248,0.7)', 'rgba(255,255,255,0.06)'], borderRadius: 6 }]
            },
            options: { ...diskOpts, scales: { x: diskOpts.scales.x, y: { ...diskOpts.scales.y } } }
        });
    } catch (e) { console.error('Failed to init Disk chart:', e); }

    try {
        phpChart = new Chart(document.getElementById('phpChart'), {
            type: 'doughnut',
            data: {
                labels: data.phpLabels,
                datasets: [{ data: data.phpCounts, backgroundColor: ['#38bdf8','#818cf8','#22c55e','#fb923c'], borderWidth: 0 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 12 } } }
            }
        });
    } catch (e) { console.error('Failed to init PHP chart:', e); }

    // Real-time polling
    function updateStats() {
        console.log('Update interval triggered');
        fetch('/admin/api/stats/', { credentials: 'same-origin' })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(stats => {
                console.log('Stats update:', stats);
                const cpuPct = stats.cpu.percent.reduce((a, b) => a + b, 0) / stats.cpu.count;
                updateGauge('CPU', cpuPct);
                updateGauge('RAM', stats.memory.percent);
                updateGauge('DISK', stats.storage.percent);
                
                if (cpuChart) pushChartData(cpuChart, cpuPct);
                if (ramChart) pushChartData(ramChart, stats.memory.percent);
            })
            .catch(err => console.error('Poll failed:', err));
    }

    function updateGauge(label, pct) {
        const cards = document.querySelectorAll('.gauge-card');
        cards.forEach(card => {
            const sub = card.querySelector('.gauge-sub');
            if(sub && sub.textContent.trim() === label) {
                const ring = card.querySelector('circle:last-child');
                if(ring) {
                    const offset = 251.2 - (pct / 100) * 251.2;
                    ring.style.strokeDashoffset = offset;
                    const valSpan = card.querySelector('.gauge-label span:first-child');
                    if(valSpan) valSpan.textContent = `${pct.toFixed(1)}%`;
                }
            }
        });
    }

    function pushChartData(chart, val) {
        try {
            chart.data.datasets[0].data.shift();
            chart.data.datasets[0].data.push(val);
            chart.update('none');
        } catch(e) {}
    }

    console.log('Setting interval for 5s...');
    setInterval(updateStats, 5000);
}

window.initDashboard = initDashboard;
