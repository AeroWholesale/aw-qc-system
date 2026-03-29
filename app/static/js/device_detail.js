async function loadDevice() {
    const res = await fetch(`/api/devices/${DEVICE_ID}`);
    const device = await res.json();

    document.getElementById("detail-serial").textContent = device.serial_number;
    document.getElementById("detail-model").textContent = device.model;
    document.getElementById("detail-type").textContent = device.device_type;
    document.getElementById("detail-type").className = `badge badge-${device.device_type}`;
    document.getElementById("detail-status").textContent = device.status;
    document.getElementById("detail-status").className = `badge badge-${device.status}`;
    document.getElementById("detail-station").textContent = device.station_id ? `Station: ${device.station_id}` : "";
    document.getElementById("detail-tech").textContent = device.tested_by ? `Tech: ${device.tested_by}` : "";
    document.getElementById("detail-time").textContent = new Date(device.created_at).toLocaleString();

    const resResults = await fetch(`/api/tests/device/${DEVICE_ID}`);
    const results = await resResults.json();

    const container = document.getElementById("results-container");
    if (results.length === 0) {
        container.innerHTML = "<p>No test results yet.</p>";
        return;
    }

    // Group by category
    const grouped = {};
    results.forEach(r => {
        const cat = r.test_category || "Other";
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(r);
    });

    let html = "";
    for (const [category, items] of Object.entries(grouped)) {
        html += `<div class="test-category-header">${category.toUpperCase()}</div>`;
        html += `<table class="results-table"><thead><tr>
            <th>Test</th><th>Result</th><th>Details</th><th>Time</th>
        </tr></thead><tbody>`;
        items.forEach(r => {
            const status = r.skipped ? "skip" : (r.passed ? "pass" : "fail");
            const label = r.skipped ? "SKIPPED" : (r.passed ? "PASS" : "FAIL");
            html += `<tr class="result-${status}">
                <td>${r.test_name}</td>
                <td><span class="badge badge-${status === "pass" ? "passed" : status === "fail" ? "failed" : "skip"}">${label}</span></td>
                <td>${r.details || "—"}</td>
                <td>${new Date(r.created_at).toLocaleTimeString()}</td>
            </tr>`;
        });
        html += `</tbody></table>`;
    }
    container.innerHTML = html;
}

loadDevice();
