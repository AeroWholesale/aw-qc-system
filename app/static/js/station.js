/* ═══════════════════════════════════════════
   AeroWholesale QC — Station Controller
   ═══════════════════════════════════════════ */
const socket = io();

let currentDevice = null;
let autoData = {};
let manualChecks = {};
let computedGrade = null;
let diagStepsCompleted = 0;
const DIAG_STEPS = ["hardware","battery","storage","smart","display","memory","wifi","bluetooth","camera","audio","security","speeds"];

// ── Persist station settings ──
const stationId = localStorage.getItem("qc_station_id") || "Station-1";
const techName = localStorage.getItem("qc_tech_name") || "";
document.getElementById("idle-station").textContent = stationId.toUpperCase();
if (document.getElementById("tech-name")) document.getElementById("tech-name").value = techName;

// ── State Machine ──
function showPanel(id) {
    document.querySelectorAll(".panel").forEach(p => p.classList.add("hidden"));
    document.getElementById("state-" + id).classList.remove("hidden");
    // Notify dashboard
    fetch("/api/station/update", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ station_id: stationId, state: id, device: currentDevice })
    }).catch(() => {});
}

function resetAll() {
    currentDevice = null;
    autoData = {};
    manualChecks = {};
    computedGrade = null;
    diagStepsCompleted = 0;
    document.getElementById("manual-serial").value = "";
    document.querySelectorAll(".diag-step").forEach(s => { s.classList.remove("done","running"); });
    document.querySelectorAll(".check-row").forEach(r => { r.classList.remove("checked-pass","checked-fail"); });
    document.querySelectorAll(".cbtn.active").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".cosmetic-select").forEach(s => { s.value = ""; });
    document.getElementById("load-progress").style.width = "0%";
    showPanel("idle");
}

// Load today's count
async function loadTodayCount() {
    try {
        const res = await fetch("/api/devices/stats");
        const stats = await res.json();
        document.getElementById("idle-count").textContent = stats.total;
    } catch(e) {}
}
loadTodayCount();

// ── Manual start ──
document.getElementById("btn-manual-start").addEventListener("click", startManual);
document.getElementById("manual-serial").addEventListener("keydown", e => { if (e.key === "Enter") startManual(); });

async function startManual() {
    const serial = document.getElementById("manual-serial").value.trim();
    if (!serial) return;
    const res = await fetch("/api/devices/detect", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ serial_number: serial, device_type: "macbook", model: "MacBook (manual entry)", station_id: stationId })
    });
    const data = await res.json();
    if (data.existing && (data.device.status === "passed" || data.device.status === "failed")) {
        alert(data.warning);
        return;
    }
    currentDevice = data.device;
    await fetch(`/api/devices/${currentDevice.id}`, {
        method: "PATCH", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ status: "testing", station_id: stationId })
    });
    // Skip loading, go straight to testing
    populateAutoDefaults();
    showPanel("testing");
}

// ── Auto detection via SocketIO (from station_watcher.py) ──
socket.on("device_registered", device => {
    if (device.station_id === stationId && !currentDevice) {
        currentDevice = device;
        startDiagLoading();
    }
});

// ── Diagnostics loading state ──
function startDiagLoading() {
    document.getElementById("load-model").textContent = currentDevice.model;
    document.getElementById("load-serial").textContent = currentDevice.serial_number;
    diagStepsCompleted = 0;
    showPanel("loading");
    // Simulate diagnostics if agent.py isn't running (demo mode)
    simulateDiag();
}

function simulateDiag() {
    let i = 0;
    const interval = setInterval(() => {
        if (i >= DIAG_STEPS.length) {
            clearInterval(interval);
            diagComplete();
            return;
        }
        completeDiagStep(DIAG_STEPS[i]);
        i++;
    }, 800);
}

socket.on("diagnostic_step", data => {
    if (currentDevice && data.device_id === currentDevice.id) {
        if (data.data) Object.assign(autoData, data.data);
        completeDiagStep(data.step);
        if (diagStepsCompleted >= DIAG_STEPS.length) diagComplete();
    }
});

function completeDiagStep(step) {
    const el = document.querySelector(`.diag-step[data-step="${step}"]`);
    if (el && !el.classList.contains("done")) {
        el.classList.remove("running");
        el.classList.add("done");
        diagStepsCompleted++;
    }
    const pct = Math.round(diagStepsCompleted / DIAG_STEPS.length * 100);
    document.getElementById("load-progress").style.width = pct + "%";
    const remaining = Math.max(0, Math.round((DIAG_STEPS.length - diagStepsCompleted) * 0.8 * 3.75));
    document.getElementById("load-status").textContent = diagStepsCompleted >= DIAG_STEPS.length
        ? "Diagnostics complete" : `Running diagnostics... ${remaining}s remaining`;
}

function diagComplete() {
    // Check for gate conditions
    const icloudLocked = autoData.icloud_locked || false;
    const mdmEnrolled = autoData.mdm_enrolled || false;
    const blacklisted = autoData.blacklisted || false;

    if (icloudLocked || mdmEnrolled || blacklisted) {
        let reason = icloudLocked ? "iCloud Activation Lock is ON" :
                     mdmEnrolled ? "MDM Profile is enrolled" : "Device is BLACKLISTED";
        document.getElementById("gate-reason").textContent = reason;
        showPanel("gate");
    } else {
        populateAutoDefaults();
        showPanel("testing");
    }
}

// ── Port visibility by model ──
// Models with HDMI + SD: MacBook Pro 14"/16" (2021+)
// Models without: MacBook Air, MacBook Pro 13"
const PORTS_BY_MODEL = {
    hdmi: /MacBook Pro.*(14|16)/i,
    sd_card: /MacBook Pro.*(14|16)/i,
    headphone_jack: /MacBook/i,  // all MacBooks have this
};

function updatePortVisibility() {
    const modelStr = autoData.model || currentDevice?.model || "";
    document.querySelectorAll(".port-optional").forEach(row => {
        const check = row.dataset.check;
        const pattern = PORTS_BY_MODEL[check];
        if (pattern && !pattern.test(modelStr)) {
            row.classList.add("hidden");
        } else {
            row.classList.remove("hidden");
        }
    });
}

function populateAutoDefaults() {
    // Fill auto results with whatever data we have, or demo defaults
    const d = autoData;
    setAuto("model", d.model || currentDevice?.model || "—", "info");
    setAuto("serial", d.serial || currentDevice?.serial_number || "—", "info");
    setAuto("ram", d.ram || "—", d.ram ? "pass" : "");
    setAuto("storage", d.storage || "—", d.storage ? "pass" : "");
    setAuto("macos", d.macos || "—", d.macos ? "pass" : "");

    const bat = d.battery_health;
    if (bat !== undefined) {
        setAuto("battery", bat + "%", bat >= 80 ? "pass" : bat >= 60 ? "warn" : "fail");
    }
    setAuto("cycles", d.cycle_count !== undefined ? d.cycle_count.toString() : "—", "info");

    const smart = d.smart_status || "";
    setAuto("smart", smart || "—", smart.toLowerCase() === "verified" ? "pass" : smart ? "fail" : "");

    setAuto("disk-read", d.disk_read ? `${d.disk_read} MB/s` : "—", d.disk_read ? "pass" : "");
    setAuto("disk-write", d.disk_write ? `${d.disk_write} MB/s` : "—", d.disk_write ? "pass" : "");
    setAuto("wifi", d.wifi ? "Detected ✓" : "—", d.wifi ? "pass" : d.wifi === false ? "fail" : "");
    setAuto("bluetooth", d.bluetooth ? "Detected ✓" : "—", d.bluetooth ? "pass" : d.bluetooth === false ? "fail" : "");
    setAuto("camera", d.camera ? "Detected ✓" : "—", d.camera ? "pass" : d.camera === false ? "fail" : "");
    setAuto("mem-pressure", d.mem_pressure !== undefined ? d.mem_pressure + "%" : "—", d.mem_pressure !== undefined && d.mem_pressure <= 70 ? "pass" : "warn");
    setAuto("icloud", d.icloud_locked ? "LOCKED" : "OFF ✓", d.icloud_locked ? "fail" : "pass");
    setAuto("mdm", d.mdm_enrolled ? "Enrolled" : "Clean ✓", d.mdm_enrolled ? "fail" : "pass");
    setAuto("filevault", d.filevault || "—", "info");
    setAuto("sip", d.sip || "—", "info");

    updatePortVisibility();
}

function setAuto(key, value, badge) {
    const valEl = document.getElementById("ar-" + key);
    const badgeEl = document.getElementById("ab-" + key);
    if (valEl) valEl.textContent = value;
    if (badgeEl && badge) {
        const labels = { pass: "PASS", fail: "FAIL", warn: "WARN", info: "INFO" };
        badgeEl.textContent = labels[badge] || badge;
        badgeEl.className = "ar-badge badge-" + badge;
    } else if (badgeEl) {
        badgeEl.textContent = "";
        badgeEl.className = "ar-badge";
    }
}

// ── Gate Check ──
document.getElementById("btn-gate-reject").addEventListener("click", () => {
    if (currentDevice) {
        fetch(`/api/devices/${currentDevice.id}`, {
            method: "PATCH", headers: {"Content-Type":"application/json"},
            body: JSON.stringify({ status: "failed", notes: "Gate check reject: " + document.getElementById("gate-reason").textContent })
        });
    }
    resetAll();
});

document.getElementById("btn-gate-override").addEventListener("click", () => {
    const code = prompt("Enter supervisor code:");
    if (code === "1234") {
        populateAutoDefaults();
        showPanel("testing");
    } else {
        alert("Invalid code");
    }
});

// ── Manual Checks ──
window.markCheck = function(btn, result) {
    const row = btn.closest(".check-row");
    const check = row.dataset.check;
    manualChecks[check] = result;

    row.querySelectorAll(".cbtn.pass, .cbtn.fail").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    row.classList.remove("checked-pass","checked-fail");
    row.classList.add(result === "pass" ? "checked-pass" : "checked-fail");
};

window.markCosmetic = function(sel) {
    const row = sel.closest(".check-row");
    const check = row.dataset.check;
    manualChecks[check] = sel.value;
};

// ── Audio tests ──
let audioCtx;
window.playTone = function(channel) {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const pan = audioCtx.createStereoPanner();
    const gain = audioCtx.createGain();
    osc.frequency.value = 440;
    pan.pan.value = channel === "left" ? -1 : 1;
    gain.gain.value = 0.5;
    osc.connect(pan).connect(gain).connect(audioCtx.destination);
    osc.start();
    setTimeout(() => osc.stop(), 1500);
};

let mediaRecorder, audioChunks;
window.testMic = function() {
    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = () => {
            const blob = new Blob(audioChunks, { type: "audio/webm" });
            new Audio(URL.createObjectURL(blob)).play();
            stream.getTracks().forEach(t => t.stop());
        };
        mediaRecorder.start();
        setTimeout(() => mediaRecorder.stop(), 3000);
    }).catch(() => alert("Microphone access denied"));
};

// ── Camera preview ──
window.openCameraPreview = function() {
    document.getElementById("camera-modal").classList.remove("hidden");
    navigator.mediaDevices.getUserMedia({ video: true }).then(stream => {
        document.getElementById("camera-video").srcObject = stream;
    }).catch(() => alert("Camera access denied"));
};
window.closeCameraPreview = function() {
    document.getElementById("camera-modal").classList.add("hidden");
    const vid = document.getElementById("camera-video");
    if (vid.srcObject) { vid.srcObject.getTracks().forEach(t => t.stop()); vid.srcObject = null; }
};

// ── Keyboard Test ──
const KB_ROWS = [
    [{k:"Esc",c:"Escape"},{k:"F1",c:"F1"},{k:"F2",c:"F2"},{k:"F3",c:"F3"},{k:"F4",c:"F4"},{k:"F5",c:"F5"},{k:"F6",c:"F6"},{k:"F7",c:"F7"},{k:"F8",c:"F8"},{k:"F9",c:"F9"},{k:"F10",c:"F10"},{k:"F11",c:"F11"},{k:"F12",c:"F12"},{k:"⏏",c:"Power",w:"w15"}],
    [{k:"`",c:"Backquote"},{k:"1",c:"Digit1"},{k:"2",c:"Digit2"},{k:"3",c:"Digit3"},{k:"4",c:"Digit4"},{k:"5",c:"Digit5"},{k:"6",c:"Digit6"},{k:"7",c:"Digit7"},{k:"8",c:"Digit8"},{k:"9",c:"Digit9"},{k:"0",c:"Digit0"},{k:"-",c:"Minus"},{k:"=",c:"Equal"},{k:"⌫",c:"Backspace",w:"w2"}],
    [{k:"Tab",c:"Tab",w:"w15"},{k:"Q",c:"KeyQ"},{k:"W",c:"KeyW"},{k:"E",c:"KeyE"},{k:"R",c:"KeyR"},{k:"T",c:"KeyT"},{k:"Y",c:"KeyY"},{k:"U",c:"KeyU"},{k:"I",c:"KeyI"},{k:"O",c:"KeyO"},{k:"P",c:"KeyP"},{k:"[",c:"BracketLeft"},{k:"]",c:"BracketRight"},{k:"\\",c:"Backslash",w:"w15"}],
    [{k:"Caps",c:"CapsLock",w:"w175"},{k:"A",c:"KeyA"},{k:"S",c:"KeyS"},{k:"D",c:"KeyD"},{k:"F",c:"KeyF"},{k:"G",c:"KeyG"},{k:"H",c:"KeyH"},{k:"J",c:"KeyJ"},{k:"K",c:"KeyK"},{k:"L",c:"KeyL"},{k:";",c:"Semicolon"},{k:"'",c:"Quote"},{k:"Return",c:"Enter",w:"w225"}],
    [{k:"Shift",c:"ShiftLeft",w:"w225"},{k:"Z",c:"KeyZ"},{k:"X",c:"KeyX"},{k:"C",c:"KeyC"},{k:"V",c:"KeyV"},{k:"B",c:"KeyB"},{k:"N",c:"KeyN"},{k:"M",c:"KeyM"},{k:",",c:"Comma"},{k:".",c:"Period"},{k:"/",c:"Slash"},{k:"Shift",c:"ShiftRight",w:"w225"}],
    [{k:"Fn",c:"Fn"},{k:"⌃",c:"ControlLeft",w:"w15"},{k:"⌥",c:"AltLeft",w:"w15"},{k:"⌘",c:"MetaLeft",w:"w175"},{k:"",c:"Space",w:"space"},{k:"⌘",c:"MetaRight",w:"w175"},{k:"⌥",c:"AltRight",w:"w15"},{k:"←",c:"ArrowLeft"},{k:"↑↓",c:"ArrowUp"},{k:"→",c:"ArrowRight"}]
];

let pressedKeys = new Set();
let keyTimerInterval;

window.openKeyTest = function() {
    pressedKeys = new Set();
    const map = document.getElementById("keyboard-map");
    map.innerHTML = "";
    let totalKeys = 0;
    KB_ROWS.forEach(row => {
        const rowEl = document.createElement("div");
        rowEl.className = "kb-row";
        row.forEach(key => {
            totalKeys++;
            const k = document.createElement("div");
            k.className = "kb-key" + (key.w ? " " + key.w : "");
            k.textContent = key.k;
            k.dataset.code = key.c;
            rowEl.appendChild(k);
        });
        map.appendChild(rowEl);
    });
    document.getElementById("key-count").textContent = `0/${totalKeys} keys pressed`;
    document.getElementById("key-test-modal").classList.remove("hidden");

    let secs = 30;
    document.getElementById("key-timer").textContent = secs + "s";
    keyTimerInterval = setInterval(() => {
        secs--;
        document.getElementById("key-timer").textContent = secs + "s";
        if (secs <= 0) {
            clearInterval(keyTimerInterval);
            document.querySelectorAll(".kb-key:not(.pressed)").forEach(k => k.classList.add("missed"));
        }
    }, 1000);

    document.addEventListener("keydown", onKeyTestPress);
};

function onKeyTestPress(e) {
    e.preventDefault();
    const code = e.code;
    pressedKeys.add(code);
    document.querySelectorAll(`.kb-key[data-code="${code}"]`).forEach(k => k.classList.add("pressed"));
    const total = document.querySelectorAll(".kb-key").length;
    document.getElementById("key-count").textContent = `${pressedKeys.size}/${total} keys pressed`;
}

window.closeKeyTest = function() {
    clearInterval(keyTimerInterval);
    document.removeEventListener("keydown", onKeyTestPress);
    document.getElementById("key-test-modal").classList.add("hidden");
};

// ── Grade calculation ──
document.getElementById("btn-grade").addEventListener("click", async () => {
    const res = await fetch("/api/station/grade", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            battery_health: autoData.battery_health,
            cycle_count: autoData.cycle_count,
            manual_checks: manualChecks,
            auto_checks: autoData,
        })
    });
    computedGrade = await res.json();

    const badge = document.getElementById("grade-badge");
    badge.textContent = computedGrade.grade;
    badge.className = "grade-badge grade-" + computedGrade.grade.toLowerCase().replace("+","plus").replace("-","minus");

    document.getElementById("grade-desc").textContent = computedGrade.description;
    document.getElementById("grade-battery").textContent =
        `Battery: ${autoData.battery_health || "?"}% · ${autoData.cycle_count || "?"} cycles`;

    const failsEl = document.getElementById("grade-fails");
    failsEl.innerHTML = computedGrade.fail_reasons.map(r => `<div>• ${r}</div>`).join("");

    const techInput = document.getElementById("tech-name");
    if (!techInput.value) techInput.value = localStorage.getItem("qc_tech_name") || "";

    showPanel("grade");
});

// ── Confirm & Print ──
document.getElementById("btn-confirm").addEventListener("click", async () => {
    const techVal = document.getElementById("tech-name").value.trim();
    localStorage.setItem("qc_tech_name", techVal);

    const override = document.getElementById("grade-override").value;
    const finalGrade = override || computedGrade.grade;
    const passed = !["XF","XC"].includes(finalGrade);

    // Save to DB
    const batchResults = [];
    for (const [name, result] of Object.entries(manualChecks)) {
        batchResults.push({
            test_name: name,
            test_category: "manual",
            passed: result === "pass" || (result !== "fail" && result !== ""),
            skipped: false,
            details: typeof result === "string" && !["pass","fail"].includes(result) ? result : null,
        });
    }

    await fetch("/api/tests/batch", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ device_id: currentDevice.id, results: batchResults })
    });

    await fetch(`/api/devices/${currentDevice.id}`, {
        method: "PATCH", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            status: passed ? "passed" : "failed",
            tested_by: techVal,
            notes: document.getElementById("confirm-notes").value,
            grade: finalGrade,
            grade_description: computedGrade.description,
            battery_health: autoData.battery_health || null,
            cycle_count: autoData.cycle_count || null,
            ram: autoData.ram || null,
            storage: autoData.storage || null,
            model: autoData.model || currentDevice.model,
        })
    });

    // Print label
    const printRes = await fetch("/api/station/print", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            model: autoData.model || currentDevice.model,
            serial: currentDevice.serial_number,
            ram: autoData.ram || "",
            storage: autoData.storage || "",
            battery_health: autoData.battery_health || "",
            cycle_count: autoData.cycle_count || "",
            grade: finalGrade,
            passed: passed,
            fail_reason: computedGrade.fail_reasons.length > 0 ? computedGrade.fail_reasons[0] : "",
            station: stationId,
            tech: techVal,
        })
    });

    // Show confirmed
    const confGrade = document.getElementById("confirmed-grade");
    confGrade.textContent = finalGrade;
    confGrade.className = "confirmed-grade grade-" + finalGrade.toLowerCase().replace("+","plus").replace("-","minus");

    // Update today count
    const stats = await fetch("/api/devices/stats").then(r => r.json());
    document.getElementById("confirmed-count").textContent = stats.total;

    showPanel("confirmed");

    // Countdown
    let secs = 5;
    document.getElementById("countdown-num").textContent = secs;
    const cdInterval = setInterval(() => {
        secs--;
        document.getElementById("countdown-num").textContent = secs;
        if (secs <= 0) { clearInterval(cdInterval); resetAll(); }
    }, 1000);

    document.getElementById("btn-next-now").onclick = () => { clearInterval(cdInterval); resetAll(); };
});

// ── Init ──
showPanel("idle");
