let equityChart = null;
let equityData = [];
let currentRange = "5D";
let currentStrategy = "TOTAL";
let currentPositionsFilter = "TOTAL";
async function loadEquity(range = "5D") {
    const res = await fetch("http://127.0.0.1:5000/api/equity");
    let data = await res.json();
    console.log(data);
    equityData = data;

    let filtered = data.filter(d => d && d.strategy && d.equity).map(d => ({
        ...d,
        strategy: String(d.strategy).trim(),
        equity: Number(d.equity)
    }));
    
    if (currentStrategy != "TOTAL") {
        filtered = filtered.filter(
            d => d.strategy === currentStrategy
        );
    }
    filtered.sort((a,b ) => new Date(a.time) - new Date(b.time));

    const now = new Date();

    let cutoff = null;
    if (range === "1D") {
        // weekday
        if (now.getDay() >= 1 && now.getDay() <= 5) {
            cutoff = new Date(now - 24 * 60 * 60 * 1000);
        }
        //saturday
        else if (now.getDay() === 6) {
            cutoff = new Date(now);
            cutoff.setDate(now.getDate()-1);
            cutoff.setHours(0,0,0,0);
        }
        //sunday
        else if (now.getDay() === 0) {
            cutoff = new Date(now);
            cutoff.setDate(now.getDate() -2);
            cutoff.setHours(0,0,0,0);
        }
    }
    if (range === "5D") {
        cutoff = new Date(now - 5 * 24 * 60 * 60 * 1000);
    }
    if (range === "1M") {
        cutoff = new Date(now - 30 * 24 * 60 * 60 * 1000);
    }
    if (cutoff) {
        // latest MR before cutoff
        const prevMR = [...filtered].reverse().find(d => d.strategy === "MR" && new Date(d.time) < cutoff);
        // last PB before cutoff
        const prevPB = [...filtered].reverse().find(d => d.strategy === "PB" && new Date(d.time) < cutoff);
        // keep only points inside cutoff range
        if (range === "1D" && (now.getDay() === 6 || now.getDay() === 0)) {
            //weekend -> only frida data
            filtered = filtered.filter(d => {
                const date = new Date(d.time);
                return (date >= cutoff && date.getDay() === 5);
            });
        } else {
            filtered = filtered.filter(d => new Date(d.time) >= cutoff);
        }

        // prepend previous values for continuity
        if (prevMR) filtered.unshift(prevMR);
        if (prevPB) filtered.unshift(prevPB);
        filtered.sort((a,b) => new Date(a.time) - new Date(b.time));
    }

    let values = [];
    let labels = [];
    if (currentStrategy === "TOTAL") {
        let lastMR = null;
        let lastPB = null;

        filtered.forEach(d => {
            if (d.strategy === "MR") {
                lastMR = Number(d.equity);
            }
            if (d.strategy === "PB") {
                lastPB = Number(d.equity);
            }

            if (lastMR !== null && lastPB !== null) {
                values.push(lastMR + lastPB);
                const date = new Date(d.time);

                labels.push(
                    date.toLocaleString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                    hour12: true
                    })
                );
            }
        });
    } else {
        filtered = filtered.filter(
            d => d.strategy === currentStrategy
        );
        values = filtered.map(d => Number(d.equity));
        labels = filtered.map(d => {
            const date = new Date(d.time);
            return date.toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
                hour12: true
            });
        });
    }

    console.log(filtered);
    console.log(values);

    if (values.length === 0) {
        console.error("No values to chart");
        return;
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
    let data = await res.json();

    if (currentPositionsFilter == "TOTAL") {
        const merged = {};

        data.forEach(pos => {
            if (!merged[pos.ticker]) {
                merged[pos.ticker] = {
                    ticker: pos.ticker,
                    shares: 0,
                    market_value: 0,
                    pnl: 0,
                    cost_basis: 0,
                    weighted_day_change: 0,
                    day_change_dollars: 0
                };
            }
            const shares = Number(pos.shares);
            const marketValue = Number(pos.market_value);
            const pnl = Number(pos.pnl);
            const avgCost = Number(pos.avg_cost);
            const dayPercent = Number(pos.day_change_percent);
            const dayDollars = Number(pos.day_change_dollars);

            merged[pos.ticker].shares += shares;
            merged[pos.ticker].market_value += marketValue;
            merged[pos.ticker].pnl += pnl;

            merged[pos.ticker].cost_basis += (avgCost * shares);

            
            // weighted averaging
            merged[pos.ticker].day_change_dollars += dayDollars;
            merged[pos.ticker].weighted_day_change += (dayPercent * marketValue);
        });

        data = Object.values(merged).map(pos => ({
            ...pos,
            pnl_percent:
                pos.cost_basis > 0 ? (pos.pnl / pos.cost_basis) * 100 : 0,
            
            day_change_percent:
                pos.market_value > 0 ? pos.weighted_day_change / pos.market_value : 0
        }));
    } else{
        data = data.filter(
            pos => pos.strategy === currentPositionsFilter
        );
    }
    
    const body = document.getElementById("positionsBody");
    body.innerHTML = "";
    
    data.forEach(pos => {
        const positiveDay = Number(pos.day_change_dollars) >= 0;
        const positiveReturn = Number(pos.pnl_percent) >= 0;
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${pos.ticker}</td>
            <td>${pos.shares.toFixed(2)}</td>
            <td>$${Number(pos.market_value).toLocaleString()}</td>
            <td class="${positiveDay ? "positive" : "negative"}">
                ${positiveDay ? "+" : ""}${pos.day_change_percent.toFixed(2)}%
            </td>
            <td class="${positiveReturn ? "positive" : "negative"}">
                ${positiveReturn ? "+" : ""}${pos.pnl_percent.toFixed(2)}%
            </td>`;
        body.appendChild(row);
    });
}

async function loadTrades() {
    const res = await fetch("http://127.0.0.1:5000/api/trades");
    let data = await res.json();

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
    await loadEquity(currentRange);
    await loadPositions();
    await loadTrades();
}

async function loadTickerBar() {
    const res = await fetch("http://127.0.0.1:5000/api/prices");
    const stocks = await res.json();
    track.innerHTML = "";
    track.style.display = "flex";

    //duplicate cards 4 seamless scrolling
    const loopedStocks = [...stocks, ...stocks];
    loopedStocks.forEach(stock => {
        const positive = stock.pnl_percent >= 0;
        const card = document.createElement("div");
        card.className = "stock-card";
        card.innerHTML = `
            <div class="stock-header">
                <div class="stock-left">
                    <img class="stock-logo" src="${stock.logo}" onerror="this.src='https://placehold.co/60x60/11827/ffffff?text=${stock.ticker}'">
                    <div>
                        <div class="stock-ticker">${stock.ticker}</div>
                    </div>
                </div>
                <div class="mini-chart-wrap">
                    <canvas class="stock-chart"></canvas>
                </div>
            </div>
            <div class="stock-row">
                <span class="stock-label">Total Shares:</span>
                <span class="stock-value">${stock.shares.toFixed(2)}</span>
            </div>
            <div class="stock-row">
                <span class="stock-label">Total Return</span>
                <span class="stock-return ${positive ?"positive" : "negative"}">
                    ${positive ? "▲" : "▼"} ${Math.abs(stock.pnl_percent).toFixed(2)}%
                </span>
            </div>`;
        track.appendChild(card);
        const canvas = card.querySelector("canvas");
        new Chart(canvas, {
            type: "line",
            data: {
                labels: (stock.chart || []).map((_, i) => i),
                datasets: [{
                    data: stock.chart || [],
                    borderColor: positive ? "#22c55e" : "#ef4444",
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.4,
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
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        display: false
                    }
                }
            }
        });
    });

    
}

const track = document.getElementById("tickerTrack");
// DRAG TO SCROLL
const wrapper = document.querySelector(".ticker-wrapper");
let position = 0;
let speed = 0.5;

function getOneSetWidth() {
    return track.scrollWidth / 2;
}

let isDragging = false;
let startX = 0;
let startPosition = 0;

wrapper.addEventListener("mousedown", (e) => {
    isDragging = true;
    wrapper.style.cursor = "grabbing";
    startX = e.clientX;
    startPosition = position;
});
wrapper.addEventListener("touchstart", (e) => {
    isDragging = true;
    startX = e.touches[0].clientX;
    startPosition = position;
}, { passive: true });

window.addEventListener("mouseup", () => {
    isDragging = false;
    wrapper.style.cursor = "grab";
});
window.addEventListener("touchend", () => {
    isDragging = false;
});
window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    position = startPosition + dx;
});
window.addEventListener("touchmove", (e) => {
    if (!isDragging) return;

    const dx = e.touches[0].clientX - startX;
    position = startPosition + dx;
}, { passive: true });

function animateTicker() {
    if (!isDragging) {
        position -= speed;
    }
    if (position <= -getOneSetWidth()) {
        position += getOneSetWidth();
    }
    if (position > 0) {
        position -= getOneSetWidth();
    }
    track.style.transform = `translateX(${position}px)`;
    requestAnimationFrame(animateTicker);
}
wrapper.style.cursor = "grab";
animateTicker();

document.querySelectorAll(".chart-option").forEach(el => {
    el.addEventListener("click", () => {
        if (!el.dataset.range) return;
        document.querySelectorAll(".chart-option").forEach(e => e.classList.remove("active"));
        el.classList.add("active");
        currentRange = el.dataset.range;
        loadEquity(currentRange);
    })
});

document.querySelectorAll(".strategy-option").forEach(el => {
    el.addEventListener("click", () => {
        if (!el.dataset.strategy) return;
        document.querySelectorAll(".strategy-option").forEach(e => e.classList.remove("active"));
        el.classList.add("active");
        currentStrategy = el.dataset.strategy;
        loadEquity(currentRange);
    });
});

document.querySelectorAll(".positions-filter").forEach(el => {
    el.addEventListener("click", () => {
        document.querySelectorAll(".positions-filter").forEach(e => e.classList.remove("active"));
        el.classList.add("active");
        currentPositionsFilter = el.dataset.positionFilter;
        loadPositions();
    });
});

loadAll();
loadTickerBar();