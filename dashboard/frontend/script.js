let equityChart = null;
let equityData = [];
let currentRange = "5D";
let currentStrategy = "TOTAL";
let currentPositionsFilter = "TOTAL";
let showRollingAverage = true;
let showFlatAverage = false;
let currentTradeStrategy = "TOTAL";
let currentTradeSide = "ALL";
let selectedTradeTickers = new Set();
async function loadEquity(range = "5D") {
    const res = await fetch("http://127.0.0.1:5000/api/equity");
    let data = await res.json();
    const tradesRes = await fetch("http://127.0.0.1:5000/api/trades");
    const trades = await tradesRes.json();
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
    const chartPoints = [];
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
                chartPoints.push({
                    time: d.time,
                    value: lastMR + lastPB
                });
            }
        });
        values = chartPoints.map(p => p.value);
        labels = chartPoints.map(p => {
            const date = new Date(p.time);
            return date.toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
                hour12: true
            });
        });
    } else {
        filtered = filtered.filter(
            d => d.strategy === currentStrategy
        );
        filtered.forEach(d => {
            chartPoints.push({
                time: d.time,
                value: Number(d.equity)
            });
        });
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

    
    const flatAverage = values.reduce((a,b) => a+b,0) / values.length;
    const rollingWindow = Math.min(20,Math.max(5,Math.floor(values.length/8)));
    const rollingAverage = values.map((_, i) => {
        const start = Math.max(0,i-rollingWindow+1);
        const subset = values.slice(start,i+1);
        return subset.reduce((a,b) => a+b,0) / subset.length;
    });

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

    const averageValue = values.reduce((sum,val) => sum + val, 0) / values.length;
    const averageLine = values.map(() => averageValue);
    // const normalizedStrategy = 
    //     currentStrategy === "PB" ? "PULLBACK_TREND" : currentStrategy === "MR" ? "MEAN_REVERSION" : null;
    // const tradeReplayPoints = [];
    // trades.forEach(trade => {
    //     if (
    //         normalizedStrategy && trade.strategy !== normalizedStrategy
    //     ) {
    //         return;
    //     }
    //     const tradeTime = new Date(trade.time);
    //     let closestPoint = null;
    //     let closestDiff = Infinity;

    //     chartPoints.forEach((point,index) => {
    //         const diff = Math.abs(new Date(point.time) - tradeTime);
    //         if (diff < closestDiff) {
    //             closestDiff = diff;
    //             closestPoint = point;
    //         }
    //     });
    //     if (closestPoint) {
    //         const label = new Date(closestPoint.time).toLocaleString("en-US", {
    //             month: "short",
    //             day: "numeric",
    //             hour: "numeric",
    //             minute: "2-digit",
    //             hour12: true
    //         });
    //         tradeReplayPoints.push({
    //             x: label,
    //             y: closestPoint.value,
    //             action: trade.action,
    //             ticker: trade.ticker,
    //             shares: Number(trade.shares || 0),
    //             price: Number(trade.price || 0),
    //             strategy: trade.strategy
    //         });
    //     }
    // });



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
            },
            ...(showFlatAverage ? [{
                label: "Flat Avg",
                data: averageLine,
                borderColor : "rgba(255,255,255,0.55)",
                borderWidth: 2,
                borderDash: [8,6],
                pointRadius: 0,
                fill: false,
                tension: 0
            }] : []),
            // dashed rolling average line
            ...(showRollingAverage ? [{
                label: "Rolling Avg",
                data: rollingAverage,
                borderColor: "rgba(255,255,255,0.7)",
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.3,
                fill: false
            }] : [])//,
            // {
            //     label: "Trade Replay",
            //     data: tradeReplayPoints,
            //     parsing: false,
            //     showLine: false,
            //     pointRadius: 6,
            //     pointHoverRadius: 9,
            //     pointBackgroundColor: (ctx) => {
            //         const action = String(ctx.raw?.action || "").toUpperCase();
            //         if (action.includes("BUY") || action.includes("ADD")) {
            //             return "#22c55e";
            //         }
            //         if (action.includes("SELL")) {
            //             return "#ef4444";
            //         }
            //         return "#38bdf8";
            //     },
            //     pointBorderColor: "#ffffff",
            //     pointBorderWidth: 2,
            //     pointStyle: (ctx) => {
            //         const action = String(ctx.raw?.action || "").toUpperCase();
            //         if (action.includes("BUY") || action.includes("ADD")) {
            //             return "triangle";
            //         }
            //         if (action.includes("SELL")) {
            //             return "rectRot";
            //         }
            //         return "circle";
            //     }
            // }
        ]
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
                    callbacks: {
                        label: function(context) {
                            if (context.dataset.label === "Trade Replay") {
                                const trade = context.raw;
                                return [
                                    `${trade.action} ${trade.ticker}`,
                                    `${Number(trade.shares).toFixed(2)} shares`,
                                    `@ $${Number(trade.price).toFixed(2)}`,
                                    `${trade.strategy}`
                                ];
                            }

                            if (context.dataset.label !== "Portfolio Equity") {
                                return null;
                            }
                            const value = context.raw;
                            const index = context.dataIndex;
                            const rolling = rollingAverage[index];
                            const flat = flatAverage;
                            const rollingDiff = ((value - rolling) / rolling) * 100;
                            const flatDiff = ((value - flat) / flat) * 100;
                            return [
                                `Equity: $${value.toLocaleString()}`,
                                `Rolling Avg: ${rollingDiff >= 0 ? "+" : ""}${rollingDiff.toFixed(2)}%`,
                                `Flat Avg: ${flatDiff >= 0 ? "+" : ""}${flatDiff.toFixed(2)}%`
                            ];
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
                        maxTicksLimit: 6
                    },
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

    buildTickerFilterMenu(data);

    if (currentTradeStrategy !== "TOTAL") {
        const strategyMap = {
            PB: "PULLBACK_TREND",
            MR: "MEAN_REVERSION"
        };
        data = data.filter(
            trade => trade.strategy === strategyMap[currentTradeStrategy]
        );
    }
    if (currentTradeSide !== "ALL") {
        data = data.filter(trade => {
            const side = String(trade.side || trade.action || "").toUpperCase();
            if (currentTradeSide === "BUY") {
                return ["BUY", "ADD"].includes(side);
            }
            if (currentTradeSide === "SELL") {
                return [
                    "SELL",
                    "PARTIAL_SELL",
                    "PARTIAL SELL"
                ].includes(side);
            }
            return true;
        });
    }

    if (selectedTradeTickers.size > 0) {
        data = data.filter(trade => {
            const ticker = 
                trade.ticker || trade.symbol || trade.asset;
                return selectedTradeTickers.has(ticker);
        });
    }

    const container = document.getElementById("tradesTable");
    container.innerHTML = "";

    const recentTrades = data.slice(-20).reverse();

    document.getElementById("tradeCount").textContent =
    `${recentTrades.length} Trades`;

    recentTrades.forEach(trade => {
        
        const side = String(trade.side || trade.action || "").toUpperCase();
        const buyActions = ["BUY", "ADD"];
        const sellActions = ["SELL", "PARTIAL_SELL", "PARTIAL SELL"];
        const isBuy = buyActions.includes(side);
        const isSell = sellActions.includes(side);
        const ticker = trade.ticker || trade.symbol || trade.asset || "N/A";
        const qty = Number(trade.qty || trade.shares || 0);
        const price = Number(trade.price || trade.fill_price || 0);
        const notional = Number(trade.notional || 0);
        const realizedPnL = trade.profit !== "" && trade.profit != null ? Number(trade.profit) : null;
        const pnlPositive = realizedPnL !== null && realizedPnL >= 0;
        const strategy = trade.strategy;
        const timestamp = trade.time || trade.timestamp || "";
        const formattedTime = timestamp ? new Date(timestamp).toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
            hour12: true
        }) : "Unknown";
        const tradeCard = document.createElement("div");
        tradeCard.className = "trade-item";
        tradeCard.innerHTML = `
            <div class="trade-left">
                <div class="trade-side ${isBuy ? "buy" : "sell"}">
                    ${side.replace("_", " ")}
                </div>
                <div class="trade-main">
                    <div class="trade-top-row">
                        <span class="trade-ticker">
                            ${ticker}
                        </span>
                        <span class="trade-strategy">
                            ${strategy}
                        </span>
                    </div>
                    <div class="trade-meta">
                        ${qty.toFixed(2)} shares * $${price.toFixed(2)}
                    </div>
                </div>
            </div>
            <div class="trade-right">
                <div class="trade-total">
                    $${notional.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    })}
                </div>
                ${isSell && realizedPnL !== null ? `
                    <div class="trade-pnl ${pnlPositive? "positive" : "negatuve"}">
                        ${pnlPositive ? "+" : ""}$${realizedPnL.toFixed(2)}
                    </div>
                ` : ""}
                <div class="trade-time">
                    ${formattedTime}
                </div>

            </div>
        `;
        container.appendChild(tradeCard);
    });
}

async function loadAll() {
    try {
        await loadEquity(currentRange);
    } catch (err) {
        console.error("Equity failed:", err);
    }

    try {
        await loadPositions();
    } catch (err) {
        console.error("Positions failed:", err);
    }

    try {
        await loadTrades();
    } catch (err) {
        console.error("Trades failed:", err);
    }
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
                <span class="stock-label">Day Return:</span>
                <span class="stock-value ${stock.day_change_percent >= 0 ? "positive" : "negative"}">${stock.day_change_percent >= 0 ? "▲" : "▼"}${Math.abs(stock.day_change_percent).toFixed(2)}%</span>
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

function buildTickerFilterMenu(trades) {
    const menu = document.getElementById("tickerFilterMenu");
    const tickers = [...new Set(
        trades.map(t => t.ticker || t.symbol)
    )].sort();
    menu.innerHTML = "";
    tickers.forEach(ticker => {
        const row = document.createElement("label");
        row.className = "ticker-filter-option";
        row.innerHTML = `
            <input
                type="checkbox"
                value = "${ticker}"
                ${selectedTradeTickers.has(ticker) ? "checked" : ""}
            >
            ${ticker}
        `;
        const checkbox = row.querySelector("input");
        checkbox.addEventListener("change", () => {
            if (checkbox.checked) {
                selectedTradeTickers.add(ticker);
            } else {
                selectedTradeTickers.delete(ticker);
            }
            loadTrades();
        });
        menu.appendChild(row);

    });
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

document.getElementById("toggleRolling").addEventListener("click", (e) => {
    showRollingAverage = !showRollingAverage;
    document.getElementById("toggleRolling").classList.toggle("active", showRollingAverage);
    loadEquity(currentRange);
});
document.getElementById("toggleFlat").addEventListener("click", (e) => {
    showFlatAverage = !showFlatAverage;
    document.getElementById("toggleFlat").classList.toggle("active", showFlatAverage);
    loadEquity(currentRange);
});
document.querySelectorAll(".trade-filter").forEach(el => {
    el.addEventListener("click", () => {
        document.querySelectorAll(".trade-filter").forEach(x => x.classList.remove("active"));
        el.classList.add("active");
        currentTradeStrategy = el.dataset.tradeStrategy;
        loadTrades();
    });
});
document.querySelectorAll(".trade-side-filter").forEach(el => {
    el.addEventListener("click", () => {
        document.querySelectorAll(".trade-side-filter").forEach(x => x.classList.remove("active"));
        el.classList.add("active");
        currentTradeSide = el.dataset.tradeSide;
        loadTrades();
    });
});

loadAll();
loadTickerBar();