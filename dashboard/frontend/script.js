let equityChart = null;
let equityData = [];
let currentRange = "5D";
let currentStrategy = "TOTAL";
async function loadEquity(range = "5D") {
    const res = await fetch("http://127.0.0.1:5000/api/equity");
    const data = await res.json();

    equityData = data;

    let filtered = [...data];
    
    if (currentStrategy != "TOTAL") {
        filtered = filtered.filter(
            d => d.strategy === currentStrategy
        );
    }

    const now = new Date();

    if (range === "5D") {
        filtered = filtered.filter(d => {
            const date = new Date(d.time);
            return (now-date) <= 5 * 24 * 60 * 60 * 1000;
        });
    }

    if (range === "1M") {
        filtered = filtered.filter(d => {
            const date = new Date(d.time);
            return (now-date) <= 30 * 24 * 60 * 60 * 1000;
        });
    }

    const labels = filtered.map(d => {
        const date = new Date(d.time);

        return date.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
            hour12: true
        });
    });
    let values = [];
    if (currentStrategy === "TOTAL") {
        let latestMR = null;
        let latestPB = null;

        filtered.forEach(d => {
            if (d.strategy === "MR") {
                latestMR = Number(d.equity);
            }
            if (d.strategy === "PB") {
                latestPB = Number(d.equity);
            }

            const total = (latestMR ?? latesPB ?? 0) + (latestPB ?? latestMR ?? 0);
            values.push(total);
        });
    } else {
        values = filtered.map(d => Number(d.equity));
    }

    const startValue = values[0];
    const endValue = values[values.length - 1];
    const positive = endValue >= startValue;
    const body = document.body
    document.body.classList.remove("profit", "loss");
    if (positive) {
        document.body.classList.add("profit");
    } else {
        document.body.classList.add("loss");
    }
    const lineColor = positive ? "#22c55e" : "#ef4444";

    const ctx = document.getElementById("equityChart");

    if (equityChart) {
        equityChart.destroy();
    }

    equityChart = new Chart(ctx, {
        type: "line",

        data: {
            labels,
            datasets: [{
                label: "Portfolio Equity",
                data: values,
                borderColor: lineColor,
                borderWidth: 3,
                tension: 0.4,
                pointRadius: 0,
                fill: true,
                backgroundColor: (context) => {
                    const chart = context.chart;
                    const {ctx, chartArea} = chart;
                    if (!chartArea) return null;

                    const gradient = ctx.createLinearGradient(
                        0,
                        chartArea.top,
                        0,
                        chartArea.bottom
                    );
                    if (positive) {
                        gradient.addColorStop(0, "rgba(34,197, 94, 0.35)");
                        gradient.addColorStop(1, "rgba(34,197, 94, 0)");
                    }
                    else {
                        gradient.addColorStop(0, "rgba(239,68,68,0.35)");
                        gradient.addColorStop(1, "rgba(239,68,68,0)");
                    }

                    return gradient;
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
                    borderColor: lineColor,
                    borderWidth: 1,
                    padding: 12,
                    titleColor: "#fff",
                    bodyColor: "#fff",
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

async function loadPositions() {
    const res = await fetch("http://127.0.0.1:5000/api/positions");
    const data = await res.json();
    
    const list = document.getElementById("positions");
    list.innerHTML = "";
    
    data.forEach(pos => {
        const li = document.createElement("li");
        li.textContent = `${pos.ticker}: ${pos.shares} shares`;
        list.appendChild(li);
    });
}

async function loadTrades() {
    const res = await fetch("http://127.0.0.1:5000/api/trades");
    const data = await res.json();

    const table = document.getElementById("tradesTable");
    table.innerHTML = "";

    data.slice(-20).forEach(trade => {
        const row = document.createElement("tr");

        Object.values(trade).forEach(val => {
            const cell = document.createElement("td");
            cell.textContent = val;
            row.appendChild(cell);
        });

        table.appendChild(row);
    });
}

async function loadAll() {
    await loadEquity("5D");
    await loadPositions();
    await loadTrades();
}

document.querySelectorAll(".chart-btn").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".chart-btn").forEach(btn => btn.classList.remove("active"));
        button.classList.add("active");
        currentRange = button.dataset.range;
        loadEquity(currentRange);
    });
});

document.querySelectorAll(".strategy-btn").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".strategy-btn").forEach(btn => btn.classList.remove("active"));
        button.classList.add("active");
        currentStrategy = button.dataset.strategy;
        loadEquity(currentRange);
    });
});

loadAll();