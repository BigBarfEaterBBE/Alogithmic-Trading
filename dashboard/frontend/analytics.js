let drawdownChart = null;
let histogramChart = null;
let allocationChart = null;
let durationChart = null;
let analyticsData = null;
const analyticsFilters = {
    drawdown: "ALL",
    histogram: "ALL",
    allocation: "ALL",
    duration: "ALL"
};

async function loadAnalytics() {
    const res = await fetch(
        "http://127.0.0.1:5000/api/analytics"
    );
    analyticsData = await res.json();
    setupAnalyticsFilters();
    renderAnalytics();
}

function setupAnalyticsFilters() {
    document.querySelectorAll(".analytics-filter").forEach(filter => {
        filter.addEventListener("click", () => {
            const card = filter.dataset.card;
            const strategy = filter.dataset.strategy;
            analyticsFilters[card] = strategy;
            document.querySelectorAll(`.analytics-filter[data-card="${card}"]`).forEach(el => el.classList.remove("active"));
            filter.classList.add("active");
            renderAnalytics();
        });
    });
}

function renderAnalytics() {
    buildDrawdownChart(
        analyticsData.drawdown[analyticsFilters.drawdown].labels,
        analyticsData.drawdown[analyticsFilters.drawdown].values
    );
    buildHistogram(
        analyticsData.trade_returns[analyticsFilters.histogram]
    );
    console.log(
                analyticsFilters.allocation,
                analyticsData.allocation
            );
    buildAllocationChart(
        analyticsData.allocation[analyticsFilters.allocation]
    );
    buildTradeDurationChart(
        analyticsData.trade_durations[analyticsFilters.duration],
        analyticsData.avg_trade_duration[analyticsFilters.duration]
    );
    buildStrategyComparison(analyticsData.strategy_stats);
    
}

function buildDrawdownChart(labels, values) {
    const formattedLabels = labels.map(label => {
        const date = new Date(label);
        return date.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
            hour12: true
        });
    });

    const ctx = document.getElementById("drawdownChart");
    if (drawdownChart) {
        drawdownChart.destroy();
    }

    drawdownChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: formattedLabels,
            datasets: [{
                label: "Drawdown",
                data: values,
                borderColor: "#ef4444",
                borderWidth: 3,
                tension: 0.4,
                pointRadius: 0,
                fill: true,
                backgroundColor: (context) => {
                    const chart = context.chart;
                    const { ctx, chartArea } = chart;
                    if (!chartArea) return null;
                    const gradient = ctx.createLinearGradient(
                        0,
                        chartArea.top,
                        0,
                        chartArea.bottom
                    );
                    gradient.addColorStop(
                        0, "rgba(239,68,68,0.35)"
                    );
                    gradient.addColorStop(
                        1,
                        "rgba(239,68,68,0)"
                    );
                    return gradient
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index"
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: "#111827",
                    borderColor: "#ef4444",
                    borderWidth: 1,
                    padding: 12,
                    titleColor: "#fff",
                    bodyColor: "#fff",
                    callbacks: {
                        label: (ctx) => `Drawdown: ${ctx.raw.toFixed(2)}%`
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: "rgba(255,255,255,0.04)"
                    },
                    ticks: {
                        color: "rgba(255,255,255,0.6)",
                        maxTicksLimit: 6
                    }
                },
                y: {
                    grid: {
                        color: "rgba(255,255,255,0.04)"
                    },
                    ticks: {
                        color: "rgba(255,255,255,0.6)"
                    }
                }
            }
        }
    });
}

function buildHistogram(trades) {
    const bins = 20;
    const min = Math.min(...trades);
    const max = Math.max(...trades);
    const binSize = (max-min) / bins;
    const counts = Array(bins).fill(0);
    trades.forEach(value => {
        let index = Math.floor(
            (value - min) / binSize
        );
        if (index >= bins) {
            index = bins - 1;
        }
        counts[index]++;
    });
    const labels = counts.map((_, i) => {
        const start = min + i *binSize;
        const end = start + binSize;
        return `$${start.toFixed(0)}-$${end.toFixed(0)}`;
    });
    const ctx = document.getElementById("histogramChart");
    if (histogramChart) {
        histogramChart.destroy();
    }
    histogramChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                data: counts,
                borderRadius: 8,
                backgroundColor: (context) => {
                    const chart = context.chart;
                    const { ctx, chartArea } = chart;
                    if (!chartArea) {
                        return "#38bdf8";
                    }
                    const gradient =
                        ctx.createLinearGradient(
                            0,
                            chartArea.top,
                            0,
                            chartArea.bottom
                        );
                    gradient.addColorStop(
                        0,
                        "rgba(56,189,248,0.9)"
                    );
                    gradient.addColorStop(
                        1,
                        "rgba(56,189,247,0.25)"
                    );
                    return gradient;
                },
                borderColor: "#38bdf8",
                borderWidth: 1.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1200,
                easing: "easeOutQuart"
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: "#111827",
                    borderColor: "#38bdf8",
                    borderWidth: 1,
                    padding: 12,
                    titleColor: "#fff",
                    bodyColor: "#fff",
                    callbacks: {
                        title: (items) => items[0].label,
                        label: (ctx) => {
                            return `${ctx.raw} trades`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: "rgba(255,255,255,0.04)"
                    },
                    ticks: {
                        color: "rgba(255,255,255,0.6)",
                        maxTicksLimit: 8,
                        maxRotation: 0
                    }
                },
                y: {
                    grid: {
                        color: "rgba(255,255,255,0.04)"
                    },
                    ticks: {
                        color: "rgba(255,255,255,0.6)"
                    }
                }
            }
        }
    });
}

function buildAllocationChart(positions = []) {
    if (!Array.isArray(positions)) {
        console.error("Allocation data invalid:", positions);
        return;
    }
    console.log("allocation data", analyticsData.allocation);
    console.log("selected", analyticsFilters.allocation);
    console.log(
        "positions",
        analyticsData.allocation?.[analyticsFilters.allocation]
    );
    const ctx = document.getElementById("allocationChart");
    if (allocationChart) {
        allocationChart.destroy();
    }
    
    allocationChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            
            labels: positions.map(
                p => p.ticker
            ),
            datasets: [{
                data:positions.map(
                    p => p.value
                ),
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "70%",
            plugins: {
                legend: {
                    position: "right",
                    labels: {
                        color: "white"
                    }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
                            const pct = (ctx.raw / total) * 100;
                            return `${ctx.label}: ${pct.toFixed(1)}%`;
                        }
                    }
                }
            }
        }
    });
}

function buildTradeDurationChart(durations, avgDuration) {
    if (!durations || durations.length === 0) {
        return;
    }
    const avg = durations.reduce((a,b) => a + b, 0) / durations.length;
    const min = Math.min(...durations);
    const max = Math.max(...durations);
    document.getElementById("avgDuration").textContent = `${avgDuration.toFixed(1)}h`;
    document.getElementById("minDuration").textContent =  `${min.toFixed(1)}h`;
    document.getElementById("maxDuration").textContent = `${max.toFixed(1)}h`;
    const ctx = document.getElementById("durationChart");
    if (durationChart) {
        durationChart.destroy();
    }
    durationChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: durations.map(
                (_, i) => `Trade ${i + 1}`
            ),
            datasets: [{
                label: "Duration (hours)",
                data: durations,
                borderRadius: 8,
                backgroundColor: "rgba(59,130,246,0.7)",
                borderColor: "rgba(59,130,246,1)",
                borderWidth:1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.raw.toFixed(1)} hours`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: "Hours"
                    }
                }
            }
        }
    });
}

function buildStrategyComparison(stats) {
    const body = document.getElementById(
        "strategyComparisonBody"
    );
    body.innerHTML = "";
    stats.forEach(strategy => {
        const row = document.createElement("tr");
        const returnClass = strategy.return_pct >= 0 ? "positive" : "negative";
        row.innerHTML = `
            <td>${strategy.name}</td>
            <td class="${returnClass}">
                ${strategy.return_pct.toFixed(2)}
            </td>
            <td>${strategy.win_rate.toFixed(1)}%</td>
            <td>${strategy.trades}</td>
            <td>$${strategy.avg_trade.toFixed(2)}</td>
            <td>${strategy.max_drawdown.toFixed(2)}%</td>
        `;
        body.appendChild(row);
    });
}

loadAnalytics();