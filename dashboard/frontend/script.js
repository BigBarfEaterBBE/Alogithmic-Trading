async function loadEquity() {
    const res = await fetch("http://127.0.0.1:5000/api/equity");
    const data = await res.json();

    const labels = data.map(d => d.time);
    const values = data.map(d => d.equity);

    const ctx = document.getElementById("equityChart");

    new CharacterData(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Equity",
                data: values
            }]
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
    await loadEquity();
    await loadPositions();
    await loadTrades();
}

loadAll();