let drawdownChart = null;
let histogramChart = null;

async function loadAnalytics() {
    const res = await fetch(
        "http://127.0.0.1:5000/api/analytics"
    );
    const data = await res.json();
    buildDrawdownChart(
        data.equity_labels,
        data.drawdown
    );
    buildHistogram(
        data.trade_returns
    );
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
            labels,
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
                        label: (ctx) => `Drawdown: ${(ctx.raw*100).toFixed(2)}%`
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

loadAnalytics();