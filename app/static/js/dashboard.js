/* ═══════════════════════════════════════════
   AeroWholesale QC — Supervisor Dashboard
   ═══════════════════════════════════════════ */
const socket = io();
socket.emit("join_dashboard");

const GRADE_COLORS = {
    CAP1:"#22C55E", CAP:"#4ADE80", "CA+":"#86EFAC", CA:"#A3E635",
    CAB:"#F59E0B", SD:"#60A5FA", "SD-":"#93C5FD", SDB:"#F59E0B",
    XF:"#EF4444", XC:"#EF4444"
};

// Stations state
const stations = {};
for (let i = 1; i <= 10; i++) {
    stations[`Station-${i}`] = { state: "idle", device: null, lastGrade: null, count: 0 };
}

// ── Clock ──
function updateClock() {
    document.getElementById("dash-clock").textContent = new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

// ── Stats ──
async function loadStats() {
    try {
        const stats = await fetch("/api/devices/stats").then(r => r.json());
        document.getElementById("ds-total").textContent = stats.total;
        document.getElementById("ds-passed").textContent = stats.passed;
        document.getElementById("ds-failed").textContent = stats.failed;
        document.getElementById("ds-rate").textContent = stats.pass_rate + "%";
        const rateEl = document.getElementById("ds-rate");
        rateEl.style.color = stats.pass_rate >= 80 ? "#22C55E" : stats.pass_rate >= 60 ? "#F59E0B" : "#EF4444";
    } catch(e) {}
}

// ── Station Grid ──
function renderStations() {
    const grid = document.getElementById("station-grid");
    grid.innerHTML = "";
    let activeCount = 0;
    for (const [id, stn] of Object.entries(stations)) {
        if (stn.state === "testing" || stn.state === "loading") activeCount++;
        const stateClass = stn.state === "testing" || stn.state === "loading" ? "stn-testing" :
                           stn.state === "confirmed" || stn.state === "grade" ? "stn-done" : "stn-idle";
        const statusLabel = stn.state === "idle" ? "IDLE" :
                            stn.state === "testing" || stn.state === "loading" ? "TESTING" : "DONE";
        const detail = stn.device ? stn.device.model : "";
        const lastGrade = stn.lastGrade ? `Last: ${stn.lastGrade}` : "";

        grid.innerHTML += `
            <div class="stn-card ${stateClass}" onclick="window.open('/station','_blank')">
                <div class="stn-name">${id}</div>
                <div class="stn-status">${statusLabel}</div>
                <div class="stn-detail">${detail}</div>
                <div class="stn-count">${lastGrade}${lastGrade && stn.count ? " · " : ""}${stn.count ? stn.count + " today" : ""}</div>
            </div>`;
    }
    document.getElementById("ds-active").textContent = activeCount;
}

// ── Live Feed ──
let feedItems = [];

async function loadFeed() {
    try {
        const devices = await fetch("/api/devices/").then(r => r.json());
        const completed = devices.filter(d => d.status === "passed" || d.status === "failed").slice(0, 20);
        feedItems = completed;
        renderFeed();
    } catch(e) {}
}

function renderFeed() {
    const body = document.getElementById("feed-body");
    body.innerHTML = feedItems.map(d => {
        const time = new Date(d.updated_at).toLocaleTimeString();
        const grade = d.grade || (d.status === "passed" ? "PASS" : "FAIL");
        const gradeColor = GRADE_COLORS[grade] || (d.status === "passed" ? "#22C55E" : "#EF4444");
        const bat = d.battery_health != null ? d.battery_health + "%" : "—";
        return `<tr>
            <td>${time}</td>
            <td>${d.station_id || "—"}</td>
            <td class="feed-serial">${d.serial_number}</td>
            <td>${d.model}</td>
            <td>${bat}</td>
            <td><span class="feed-grade" style="background:${gradeColor}22;color:${gradeColor}">${grade}</span></td>
        </tr>`;
    }).join("");
}

function addFeedItem(device) {
    feedItems.unshift(device);
    if (feedItems.length > 20) feedItems.pop();
    renderFeed();
}

// ── SocketIO Events ──
socket.on("station_status", data => {
    const id = data.station_id;
    if (stations[id]) {
        stations[id].state = data.state;
        stations[id].device = data.device;
        renderStations();
    }
});

socket.on("device_registered", device => {
    loadStats();
});

socket.on("device_update", device => {
    loadStats();
    if (device.station_id && stations[device.station_id]) {
        stations[device.station_id].device = device;
        if (device.status === "testing") stations[device.station_id].state = "testing";
        renderStations();
    }
});

socket.on("device_complete", device => {
    loadStats();
    addFeedItem(device);
    if (device.station_id && stations[device.station_id]) {
        stations[device.station_id].state = "done";
        stations[device.station_id].lastGrade = device.grade || (device.status === "passed" ? "PASS" : "FAIL");
        stations[device.station_id].count++;
        renderStations();
    }
});

// ── Init ──
loadStats();
loadFeed();
renderStations();
