const socket = io();
socket.emit("join_dashboard");

function statusBadge(status) {
    return `<span class="badge badge-${status}">${status}</span>`;
}

function deviceRow(d) {
    const time = new Date(d.created_at).toLocaleTimeString();
    const tests = d.total_tests > 0
        ? `${d.pass_count}/${d.total_tests}`
        : "—";
    return `<tr class="device-row" data-id="${d.id}" onclick="window.location='/device/${d.id}'">
        <td class="mono">${d.serial_number}</td>
        <td>${d.device_type}</td>
        <td>${d.model}</td>
        <td>${statusBadge(d.status)}</td>
        <td>${d.station_id || "—"}</td>
        <td>${d.tested_by || "—"}</td>
        <td>${tests}</td>
        <td>${time}</td>
    </tr>`;
}

function updateStats(stats) {
    document.getElementById("stat-total").textContent = stats.total;
    document.getElementById("stat-pending").textContent = stats.pending;
    document.getElementById("stat-testing").textContent = stats.testing;
    document.getElementById("stat-passed").textContent = stats.passed;
    document.getElementById("stat-failed").textContent = stats.failed;
}

function updateDeviceRow(device) {
    const existing = document.querySelector(`tr[data-id="${device.id}"]`);
    if (existing) {
        existing.outerHTML = deviceRow(device);
    }
}

// Initial load
fetch("/api/devices/stats").then(r => r.json()).then(updateStats);
fetch("/api/devices/").then(r => r.json()).then(devices => {
    document.getElementById("device-list").innerHTML = devices.map(deviceRow).join("");
});

// Real-time updates
socket.on("device_registered", device => {
    const list = document.getElementById("device-list");
    list.insertAdjacentHTML("afterbegin", deviceRow(device));
    fetch("/api/devices/stats").then(r => r.json()).then(updateStats);
});

socket.on("device_update", device => {
    updateDeviceRow(device);
    fetch("/api/devices/stats").then(r => r.json()).then(updateStats);
});

socket.on("device_complete", device => {
    updateDeviceRow(device);
    fetch("/api/devices/stats").then(r => r.json()).then(updateStats);
});
