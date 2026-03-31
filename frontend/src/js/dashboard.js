import Chart from 'chart.js/auto';
import '../css/dashboard.css';

export function initDashboard(data) {
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
    
    const cpuChart = new Chart(document.getElementById('cpuChart'), {
        type: 'line',
        data: {
            labels,
            datasets: [{ data: data.cpuHistory, borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.08)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 }]
        },
        options: chartDefaults
    });

    const ramChart = new Chart(document.getElementById('ramChart'), {
        type: 'line',
        data: {
            labels,
            datasets: [{ data: data.ramHistory, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.08)', fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2 }]
        },
        options: chartDefaults
    });

    const diskOpts = JSON.parse(JSON.stringify(chartDefaults));
    diskOpts.scales.y.max = 100;
    const diskChart = new Chart(document.getElementById('diskChart'), {
        type: 'bar',
        data: {
            labels: ['Used', 'Free'],
            datasets: [{ data: [data.diskPercent, data.diskFreePercent], backgroundColor: ['rgba(129,140,248,0.7)', 'rgba(255,255,255,0.06)'], borderRadius: 6 }]
        },
        options: { ...diskOpts, scales: { x: diskOpts.scales.x, y: { ...diskOpts.scales.y } } }
    });

    const phpChart = new Chart(document.getElementById('phpChart'), {
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

    // Real-time polling
    function updateStats() {
        console.log('Fetching dashboard stats...');
        fetch('/admin/api/stats/', { credentials: 'same-origin' })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
                return r.json();
            })
            .then(stats => {
                console.log('Stats received:', stats);
                const cpuPct = stats.cpu.percent.reduce((a, b) => a + b, 0) / stats.cpu.count;
                updateGauge('CPU', cpuPct);
                updateGauge('RAM', stats.memory.percent);
                updateGauge('DISK', stats.storage.percent);
                
                pushChartData(cpuChart, cpuPct);
                pushChartData(ramChart, stats.memory.percent);
            })
            .catch(err => {
                console.error('Failed to update stats:', err);
            });
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
                    card.querySelector('.gauge-label span:first-child').textContent = `${pct.toFixed(1)}%`;
                }
            }
        });
    }

    function pushChartData(chart, val) {
        chart.data.datasets[0].data.shift();
        chart.data.datasets[0].data.push(val);
        chart.update('none');
    }

    setInterval(updateStats, 5000);
}

window.initDashboard = initDashboard;
