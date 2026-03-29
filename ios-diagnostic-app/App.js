import React, { useState, useRef, useEffect } from 'react';
import {
  StyleSheet, Text, View, TextInput, TouchableOpacity,
  ScrollView, Alert, Platform, Dimensions,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Device from 'expo-device';
import * as Battery from 'expo-battery';
import * as FileSystem from 'expo-file-system';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Audio } from 'expo-av';
import * as Haptics from 'expo-haptics';

const { width: SCREEN_W } = Dimensions.get('window');
const COLORS = {
  bg: '#07090F', card: '#0D1119', border: '#161D2B',
  accent: '#1D6EE8', pass: '#22C55E', fail: '#EF4444',
  warn: '#F59E0B', text: '#D1D9E6', muted: '#3D5070',
};

export default function App() {
  const [screen, setScreen] = useState('connecting'); // connecting | auto | manual | submit
  const [serverIp, setServerIp] = useState('192.168.0.190');
  const [connecting, setConnecting] = useState(false);
  const [autoResults, setAutoResults] = useState({});
  const [manualResults, setManualResults] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [deviceId, setDeviceId] = useState(null);

  const serverUrl = `http://${serverIp}:5000`;

  // ── SCREEN 1: CONNECTING ──
  async function handleConnect() {
    setConnecting(true);
    try {
      const res = await fetch(`${serverUrl}/health`, { method: 'GET' });
      if (res.ok) {
        // Register device
        const serial = Device.osBuildId || Device.modelId || 'unknown';
        const detectRes = await fetch(`${serverUrl}/api/devices/detect`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            serial_number: serial,
            device_type: Platform.OS === 'ios' ? 'iphone' : 'android',
            model: Device.modelName || 'Unknown',
            station_id: 'Mobile-QC',
          }),
        });
        const detectData = await detectRes.json();
        if (detectData.device) setDeviceId(detectData.device.id);
        setScreen('auto');
        runAutoTests();
      }
    } catch (e) {
      Alert.alert('Connection Failed', `Could not reach ${serverUrl}\n${e.message}`);
    }
    setConnecting(false);
  }

  // ── SCREEN 2: AUTO TESTS ──
  async function runAutoTests() {
    const results = {};

    // Device info
    results.model = { label: 'Device Model', value: Device.modelName || 'Unknown', pass: true };
    results.os = { label: 'OS Version', value: `${Platform.OS} ${Device.osVersion}`, pass: true };
    results.serial = { label: 'Serial / Build ID', value: Device.osBuildId || 'N/A', pass: true };
    setAutoResults({ ...results });

    // Battery
    try {
      const level = await Battery.getBatteryLevelAsync();
      const state = await Battery.getBatteryStateAsync();
      const stateMap = { 1: 'Unplugged', 2: 'Charging', 3: 'Full', 0: 'Unknown' };
      const pct = Math.round(level * 100);
      results.battery = { label: 'Battery', value: `${pct}% (${stateMap[state] || 'Unknown'})`, pass: pct > 20 };
    } catch {
      results.battery = { label: 'Battery', value: 'Unavailable', pass: false };
    }
    setAutoResults({ ...results });

    // Storage
    try {
      const total = await FileSystem.getTotalDiskCapacityAsync();
      const free = await FileSystem.getFreeDiskStorageAsync();
      const totalGB = (total / 1e9).toFixed(1);
      const freeGB = (free / 1e9).toFixed(1);
      results.storage = { label: 'Storage', value: `${freeGB} GB free / ${totalGB} GB`, pass: true };
    } catch {
      results.storage = { label: 'Storage', value: 'Unavailable', pass: false };
    }
    setAutoResults({ ...results });

    // WiFi (basic connectivity check)
    try {
      const res = await fetch('https://www.apple.com/library/test/success.html', { method: 'HEAD' });
      results.wifi = { label: 'WiFi', value: res.ok ? 'Connected' : 'No internet', pass: res.ok };
    } catch {
      results.wifi = { label: 'WiFi', value: 'Not connected', pass: false };
    }
    setAutoResults({ ...results });

    // Small delay then advance
    setTimeout(() => setScreen('manual'), 1500);
  }

  // ── SCREEN 3: MANUAL TESTS ──

  // Touch grid
  const GRID_COLS = 5;
  const GRID_ROWS = 8;
  const [touchedCells, setTouchedCells] = useState(new Set());

  function handleCellTouch(idx) {
    setTouchedCells(prev => {
      const next = new Set(prev);
      next.add(idx);
      return next;
    });
  }

  useEffect(() => {
    if (touchedCells.size === GRID_COLS * GRID_ROWS) {
      setManualResults(prev => ({ ...prev, touchscreen: { label: 'Touchscreen', pass: true } }));
    }
  }, [touchedCells]);

  // Volume buttons
  const [volUp, setVolUp] = useState(false);
  const [volDown, setVolDown] = useState(false);

  // Speaker
  async function testSpeaker() {
    try {
      const { sound } = await Audio.Sound.createAsync(
        { uri: 'https://www.soundjay.com/buttons/beep-01a.mp3' },
        { shouldPlay: true }
      );
      setTimeout(() => sound.unloadAsync(), 3000);
      Alert.alert('Speaker Test', 'Did you hear the tone?', [
        { text: 'No - FAIL', onPress: () => setManualResults(p => ({ ...p, speaker: { label: 'Speaker', pass: false } })) },
        { text: 'Yes - PASS', onPress: () => setManualResults(p => ({ ...p, speaker: { label: 'Speaker', pass: true } })) },
      ]);
    } catch (e) {
      setManualResults(p => ({ ...p, speaker: { label: 'Speaker', pass: false } }));
    }
  }

  // Microphone
  const recordingRef = useRef(null);
  async function testMicrophone() {
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) { Alert.alert('Permission denied'); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await recording.startAsync();
      recordingRef.current = recording;
      Alert.alert('Recording...', 'Speak now. Recording for 3 seconds.');
      setTimeout(async () => {
        await recording.stopAndUnloadAsync();
        const uri = recording.getURI();
        const { sound } = await Audio.Sound.createAsync({ uri });
        await sound.playAsync();
        Alert.alert('Microphone Test', 'Did you hear the playback?', [
          { text: 'No - FAIL', onPress: () => setManualResults(p => ({ ...p, microphone: { label: 'Microphone', pass: false } })) },
          { text: 'Yes - PASS', onPress: () => setManualResults(p => ({ ...p, microphone: { label: 'Microphone', pass: true } })) },
        ]);
      }, 3000);
    } catch (e) {
      setManualResults(p => ({ ...p, microphone: { label: 'Microphone', pass: false } }));
    }
  }

  // Camera
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const [showFrontCamera, setShowFrontCamera] = useState(false);
  const [showRearCamera, setShowRearCamera] = useState(false);

  // Vibration
  async function testVibration() {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    Alert.alert('Vibration Test', 'Did you feel the haptic feedback?', [
      { text: 'No - FAIL', onPress: () => setManualResults(p => ({ ...p, vibration: { label: 'Vibration', pass: false } })) },
      { text: 'Yes - PASS', onPress: () => setManualResults(p => ({ ...p, vibration: { label: 'Vibration', pass: true } })) },
    ]);
  }

  // ── SCREEN 4: SUBMIT ──
  async function submitResults() {
    setSubmitting(true);
    const allResults = {};
    // Flatten auto
    for (const [k, v] of Object.entries(autoResults)) {
      allResults[`auto_${k}`] = { passed: v.pass, value: v.value };
    }
    // Flatten manual
    for (const [k, v] of Object.entries(manualResults)) {
      allResults[`manual_${k}`] = { passed: v.pass };
    }

    try {
      await fetch(`${serverUrl}/api/station/diagnostics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: deviceId,
          step: 'ios_diagnostic',
          data: {
            model: autoResults.model?.value,
            os_version: autoResults.os?.value,
            battery_health: autoResults.battery?.value,
            storage: autoResults.storage?.value,
            wifi: autoResults.wifi?.pass,
            manual_tests: manualResults,
            all_results: allResults,
          },
        }),
      });
      setSubmitted(true);
    } catch (e) {
      Alert.alert('Submit Failed', e.message);
    }
    setSubmitting(false);
  }

  // ── RENDER ──
  return (
    <View style={styles.container}>
      <StatusBar style="light" />

      {/* ══ SCREEN 1: CONNECTING ══ */}
      {screen === 'connecting' && (
        <View style={styles.centerScreen}>
          <Text style={styles.logoText}>AERO</Text>
          <Text style={styles.logoSub}>WHOLESALE</Text>
          <Text style={styles.tagline}>QC Diagnostic</Text>
          <View style={{ height: 40 }} />
          <Text style={styles.connectLabel}>Connecting to QC Station...</Text>
          <TextInput
            style={styles.input}
            value={serverIp}
            onChangeText={setServerIp}
            placeholder="Server IP"
            placeholderTextColor={COLORS.muted}
            keyboardType="numeric"
          />
          <TouchableOpacity
            style={[styles.btn, connecting && styles.btnDisabled]}
            onPress={handleConnect}
            disabled={connecting}
          >
            <Text style={styles.btnText}>{connecting ? 'Connecting...' : 'Connect'}</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* ══ SCREEN 2: AUTO TESTS ══ */}
      {screen === 'auto' && (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          <Text style={styles.heading}>AUTO DIAGNOSTICS</Text>
          {Object.entries(autoResults).map(([key, r]) => (
            <View key={key} style={styles.resultRow}>
              <Text style={styles.resultLabel}>{r.label}</Text>
              <Text style={styles.resultValue}>{r.value}</Text>
              <Text style={[styles.badge, r.pass ? styles.badgePass : styles.badgeFail]}>
                {r.pass ? '\u2713' : '\u2717'}
              </Text>
            </View>
          ))}
          <View style={styles.progressWrap}>
            <View style={[styles.progressBar, { width: `${(Object.keys(autoResults).length / 5) * 100}%` }]} />
          </View>
          <Text style={styles.subtext}>Running tests...</Text>
        </ScrollView>
      )}

      {/* ══ SCREEN 3: MANUAL TESTS ══ */}
      {screen === 'manual' && !showFrontCamera && !showRearCamera && (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          <Text style={styles.heading}>MANUAL TESTS</Text>

          {/* Touchscreen Grid */}
          <Text style={styles.sectionHead}>Touchscreen — Tap all cells</Text>
          <View style={styles.grid}>
            {Array.from({ length: GRID_COLS * GRID_ROWS }, (_, i) => (
              <TouchableOpacity
                key={i}
                style={[styles.gridCell, touchedCells.has(i) && styles.gridCellActive]}
                onPress={() => handleCellTouch(i)}
                activeOpacity={0.7}
              />
            ))}
          </View>
          <Text style={styles.subtext}>{touchedCells.size}/{GRID_COLS * GRID_ROWS} cells</Text>

          {/* Volume Buttons */}
          <Text style={styles.sectionHead}>Volume Buttons</Text>
          <View style={styles.row}>
            <TouchableOpacity
              style={[styles.testBtn, volUp && styles.testBtnPass]}
              onPress={() => { setVolUp(true); setManualResults(p => ({ ...p, volume_up: { label: 'Vol Up', pass: true } })); }}
            >
              <Text style={styles.testBtnText}>Vol Up {volUp ? '\u2713' : ''}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.testBtn, volDown && styles.testBtnPass]}
              onPress={() => { setVolDown(true); setManualResults(p => ({ ...p, volume_down: { label: 'Vol Down', pass: true } })); }}
            >
              <Text style={styles.testBtnText}>Vol Down {volDown ? '\u2713' : ''}</Text>
            </TouchableOpacity>
          </View>

          {/* Speaker */}
          <Text style={styles.sectionHead}>Speaker</Text>
          <TouchableOpacity style={styles.testBtn} onPress={testSpeaker}>
            <Text style={styles.testBtnText}>
              {manualResults.speaker ? (manualResults.speaker.pass ? '\u2713 PASS' : '\u2717 FAIL') : 'Play Tone'}
            </Text>
          </TouchableOpacity>

          {/* Microphone */}
          <Text style={styles.sectionHead}>Microphone</Text>
          <TouchableOpacity style={styles.testBtn} onPress={testMicrophone}>
            <Text style={styles.testBtnText}>
              {manualResults.microphone ? (manualResults.microphone.pass ? '\u2713 PASS' : '\u2717 FAIL') : 'Record 3s & Play'}
            </Text>
          </TouchableOpacity>

          {/* Front Camera */}
          <Text style={styles.sectionHead}>Front Camera</Text>
          <TouchableOpacity style={styles.testBtn} onPress={async () => {
            if (!cameraPermission?.granted) await requestCameraPermission();
            setShowFrontCamera(true);
          }}>
            <Text style={styles.testBtnText}>
              {manualResults.front_camera ? '\u2713 PASS' : 'Preview Front Camera'}
            </Text>
          </TouchableOpacity>

          {/* Rear Camera */}
          <Text style={styles.sectionHead}>Rear Camera</Text>
          <TouchableOpacity style={styles.testBtn} onPress={async () => {
            if (!cameraPermission?.granted) await requestCameraPermission();
            setShowRearCamera(true);
          }}>
            <Text style={styles.testBtnText}>
              {manualResults.rear_camera ? '\u2713 PASS' : 'Preview Rear Camera'}
            </Text>
          </TouchableOpacity>

          {/* Vibration */}
          <Text style={styles.sectionHead}>Vibration (Haptic)</Text>
          <TouchableOpacity style={styles.testBtn} onPress={testVibration}>
            <Text style={styles.testBtnText}>
              {manualResults.vibration ? (manualResults.vibration.pass ? '\u2713 PASS' : '\u2717 FAIL') : 'Trigger Haptic'}
            </Text>
          </TouchableOpacity>

          <View style={{ height: 20 }} />
          <TouchableOpacity style={styles.btn} onPress={() => setScreen('submit')}>
            <Text style={styles.btnText}>Review & Submit</Text>
          </TouchableOpacity>
          <View style={{ height: 40 }} />
        </ScrollView>
      )}

      {/* Camera Preview Overlays */}
      {showFrontCamera && cameraPermission?.granted && (
        <View style={styles.cameraOverlay}>
          <CameraView style={styles.camera} facing="front" />
          <View style={styles.cameraControls}>
            <TouchableOpacity style={styles.btn} onPress={() => {
              setManualResults(p => ({ ...p, front_camera: { label: 'Front Camera', pass: true } }));
              setShowFrontCamera(false);
            }}>
              <Text style={styles.btnText}>PASS</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.btnFail]} onPress={() => {
              setManualResults(p => ({ ...p, front_camera: { label: 'Front Camera', pass: false } }));
              setShowFrontCamera(false);
            }}>
              <Text style={styles.btnText}>FAIL</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {showRearCamera && cameraPermission?.granted && (
        <View style={styles.cameraOverlay}>
          <CameraView style={styles.camera} facing="back" />
          <View style={styles.cameraControls}>
            <TouchableOpacity style={styles.btn} onPress={() => {
              setManualResults(p => ({ ...p, rear_camera: { label: 'Rear Camera', pass: true } }));
              setShowRearCamera(false);
            }}>
              <Text style={styles.btnText}>PASS</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.btnFail]} onPress={() => {
              setManualResults(p => ({ ...p, rear_camera: { label: 'Rear Camera', pass: false } }));
              setShowRearCamera(false);
            }}>
              <Text style={styles.btnText}>FAIL</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* ══ SCREEN 4: SUBMIT ══ */}
      {screen === 'submit' && (
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          <Text style={styles.heading}>RESULTS SUMMARY</Text>

          <Text style={styles.sectionHead}>Auto Tests</Text>
          {Object.entries(autoResults).map(([key, r]) => (
            <View key={key} style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>{r.label}</Text>
              <Text style={[styles.summaryBadge, r.pass ? styles.badgePass : styles.badgeFail]}>
                {r.pass ? 'PASS' : 'FAIL'}
              </Text>
            </View>
          ))}

          <Text style={[styles.sectionHead, { marginTop: 20 }]}>Manual Tests</Text>
          {Object.entries(manualResults).map(([key, r]) => (
            <View key={key} style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>{r.label}</Text>
              <Text style={[styles.summaryBadge, r.pass ? styles.badgePass : styles.badgeFail]}>
                {r.pass ? 'PASS' : 'FAIL'}
              </Text>
            </View>
          ))}
          {Object.keys(manualResults).length === 0 && (
            <Text style={styles.subtext}>No manual tests completed</Text>
          )}

          <View style={{ height: 20 }} />
          {submitted ? (
            <View style={styles.successBox}>
              <Text style={styles.successText}>Results Sent</Text>
            </View>
          ) : (
            <TouchableOpacity
              style={[styles.btn, submitting && styles.btnDisabled]}
              onPress={submitResults}
              disabled={submitting}
            >
              <Text style={styles.btnText}>{submitting ? 'Sending...' : 'Submit Results'}</Text>
            </TouchableOpacity>
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </View>
  );
}

const CELL_SIZE = (SCREEN_W - 60) / 5;

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg, paddingTop: 60 },
  centerScreen: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 30 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 20, paddingTop: 10 },

  // Logo
  logoText: { fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace', fontSize: 48, fontWeight: '900', color: COLORS.accent, letterSpacing: 12 },
  logoSub: { fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace', fontSize: 20, fontWeight: '700', color: COLORS.text, letterSpacing: 8, marginTop: -4 },
  tagline: { fontSize: 14, color: COLORS.muted, marginTop: 8 },
  connectLabel: { fontSize: 16, color: COLORS.text, marginBottom: 16 },

  // Input
  input: {
    width: '100%', backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: 8, padding: 14, color: COLORS.text, fontSize: 18,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace', textAlign: 'center', marginBottom: 16,
  },

  // Buttons
  btn: { backgroundColor: COLORS.accent, borderRadius: 8, paddingVertical: 14, paddingHorizontal: 28, alignItems: 'center', width: '100%' },
  btnDisabled: { opacity: 0.5 },
  btnFail: { backgroundColor: COLORS.fail },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  testBtn: {
    backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: 8, paddingVertical: 12, paddingHorizontal: 20, alignItems: 'center', marginBottom: 8,
  },
  testBtnPass: { borderColor: COLORS.pass },
  testBtnText: { color: COLORS.text, fontSize: 15, fontWeight: '600' },

  // Headings
  heading: {
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontSize: 20, fontWeight: '800', color: COLORS.text, letterSpacing: 2, marginBottom: 20,
  },
  sectionHead: {
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontSize: 13, fontWeight: '700', color: COLORS.muted, letterSpacing: 1, marginTop: 16, marginBottom: 8,
  },

  // Auto results
  resultRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.card,
    borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, padding: 12, marginBottom: 8,
  },
  resultLabel: { flex: 1, color: COLORS.muted, fontSize: 13, fontWeight: '600' },
  resultValue: { flex: 2, color: COLORS.text, fontSize: 14, fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace' },
  badge: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', textAlign: 'center', lineHeight: 28, fontSize: 16, fontWeight: '800', overflow: 'hidden' },
  badgePass: { backgroundColor: 'rgba(34,197,94,0.2)', color: COLORS.pass },
  badgeFail: { backgroundColor: 'rgba(239,68,68,0.2)', color: COLORS.fail },

  // Progress
  progressWrap: { height: 4, backgroundColor: COLORS.border, borderRadius: 2, marginTop: 16, overflow: 'hidden' },
  progressBar: { height: '100%', backgroundColor: COLORS.accent, borderRadius: 2 },
  subtext: { color: COLORS.muted, fontSize: 13, textAlign: 'center', marginTop: 8 },

  // Touch grid
  grid: {
    flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 2,
  },
  gridCell: {
    width: CELL_SIZE - 4, height: CELL_SIZE - 4,
    backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border, borderRadius: 4,
  },
  gridCellActive: { backgroundColor: COLORS.pass, borderColor: COLORS.pass },

  // Row
  row: { flexDirection: 'row', gap: 10 },

  // Camera
  cameraOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: '#000', zIndex: 100 },
  camera: { flex: 1 },
  cameraControls: { flexDirection: 'row', gap: 16, padding: 20, backgroundColor: COLORS.bg },

  // Summary
  summaryRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  summaryLabel: { color: COLORS.text, fontSize: 14, fontWeight: '600' },
  summaryBadge: { fontSize: 13, fontWeight: '800', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 4, overflow: 'hidden' },

  // Success
  successBox: {
    backgroundColor: 'rgba(34,197,94,0.15)', borderWidth: 1, borderColor: COLORS.pass,
    borderRadius: 8, padding: 20, alignItems: 'center',
  },
  successText: { color: COLORS.pass, fontSize: 20, fontWeight: '800' },
});
