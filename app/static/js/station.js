const socket = io();

let currentDevice = null;
let testDefinitions = [];
let testResults = {};

// Restore station settings from localStorage
const stationInput = document.getElementById("station-id");
const techInput = document.getElementById("tech-name");
stationInput.value = localStorage.getItem("qc_station_id") || "";
techInput.value = localStorage.getItem("qc_tech_name") || "";
stationInput.addEventListener("change", () => localStorage.setItem("qc_station_id", stationInput.value));
techInput.addEventListener("change", () => localStorage.setItem("qc_tech_name", techInput.value));

function showState(state) {
    document.querySelectorAll(".station-state").forEach(el => el.classList.add("hidden"));
    document.getElementById(`state-${state}`).classList.remove("hidden");
    if (state === "ready") {
        document.getElementById("serial-input").focus();
    }
}

function updateProgress() {
    const total = testDefinitions.length;
    const done = Object.keys(testResults).length;
    const pct = total > 0 ? (done / total * 100) : 0;
    document.getElementById("test-progress").style.width = pct + "%";
    document.getElementById("progress-text").textContent = `${done} / ${total}`;
    document.getElementById("btn-submit").disabled = done < total;
}

function buildChecklist(definitions) {
    const container = document.getElementById("test-checklist");
    container.innerHTML = "";
    let currentCategory = "";

    definitions.forEach(def => {
        if (def.test_category !== currentCategory) {
            currentCategory = def.test_category;
            container.insertAdjacentHTML("beforeend",
                `<div class="test-category-header">${currentCategory.toUpperCase()}</div>`);
        }

        const row = document.createElement("div");
        row.className = "test-row";
        row.dataset.testName = def.test_name;
        row.innerHTML = `
            <div class="test-info">
                <div class="test-name">${def.test_name}</div>
                <div class="test-instructions">${def.instructions || ""}</div>
            </div>
            <div class="test-buttons">
                <button class="btn btn-pass" onclick="markTest('${def.test_name}', '${def.test_category}', true, false)">PASS</button>
                <button class="btn btn-fail" onclick="markTest('${def.test_name}', '${def.test_category}', false, false)">FAIL</button>
                <button class="btn btn-skip" onclick="markTest('${def.test_name}', '${def.test_category}', false, true)">SKIP</button>
            </div>`;
        container.appendChild(row);
    });
}

window.markTest = function(testName, category, passed, skipped) {
    testResults[testName] = { test_name: testName, test_category: category, passed, skipped };

    const row = document.querySelector(`.test-row[data-test-name="${testName}"]`);
    row.classList.remove("result-pass", "result-fail", "result-skip");
    if (skipped) row.classList.add("result-skip");
    else if (passed) row.classList.add("result-pass");
    else row.classList.add("result-fail");

    // Highlight active button
    row.querySelectorAll(".test-buttons .btn").forEach(b => b.classList.remove("active"));
    if (skipped) row.querySelector(".btn-skip").classList.add("active");
    else if (passed) row.querySelector(".btn-pass").classList.add("active");
    else row.querySelector(".btn-fail").classList.add("active");

    updateProgress();
};

// Register device
document.getElementById("btn-register").addEventListener("click", async () => {
    const serial = document.getElementById("serial-input").value.trim();
    if (!serial) return;

    const payload = {
        serial_number: serial,
        device_type: document.getElementById("device-type").value,
        model: document.getElementById("device-model").value || "Unknown",
        station_id: stationInput.value,
        tested_by: techInput.value,
    };

    const res = await fetch("/api/devices/detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.existing && (data.device.status === "passed" || data.device.status === "failed")) {
        document.getElementById("detect-warning").textContent = data.warning;
        document.getElementById("detect-warning").classList.remove("hidden");
        return;
    }

    currentDevice = data.device;
    testResults = {};

    // Mark as testing
    await fetch(`/api/devices/${currentDevice.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            status: "testing",
            station_id: stationInput.value,
            tested_by: techInput.value,
        }),
    });

    // Load test definitions
    const defRes = await fetch(`/api/tests/definitions/${currentDevice.device_type}`);
    testDefinitions = await defRes.json();

    document.getElementById("test-serial").textContent = currentDevice.serial_number;
    document.getElementById("test-model").textContent = currentDevice.model;
    document.getElementById("test-type").textContent = currentDevice.device_type;
    document.getElementById("test-type").className = `badge badge-${currentDevice.device_type}`;

    buildChecklist(testDefinitions);
    updateProgress();
    showState("testing");
});

// Submit results
document.getElementById("btn-submit").addEventListener("click", async () => {
    const payload = {
        device_id: currentDevice.id,
        results: Object.values(testResults),
    };

    const res = await fetch("/api/tests/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await res.json();

    const device = data.device;
    const resultEl = document.getElementById("overall-result");
    resultEl.textContent = device.status.toUpperCase();
    resultEl.className = `overall-result overall-${device.status}`;

    document.getElementById("result-summary").textContent =
        `${device.pass_count} passed, ${device.fail_count} failed out of ${device.total_tests} tests`;

    showState("complete");
});

// Cancel
document.getElementById("btn-cancel").addEventListener("click", async () => {
    if (currentDevice) {
        await fetch(`/api/devices/${currentDevice.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "pending" }),
        });
    }
    resetStation();
});

// Next device
document.getElementById("btn-next").addEventListener("click", () => {
    resetStation();
});

function resetStation() {
    currentDevice = null;
    testDefinitions = [];
    testResults = {};
    document.getElementById("serial-input").value = "";
    document.getElementById("device-model").value = "";
    document.getElementById("detect-warning").classList.add("hidden");
    showState("ready");
}

// Enter key on serial input triggers register
document.getElementById("serial-input").addEventListener("keydown", e => {
    if (e.key === "Enter") document.getElementById("btn-register").click();
});
