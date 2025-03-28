import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';

// --- Config ---
// Use environment variables for build-time config is best practice
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000/api';
// Allow overriding device ID via URL parameter or env var, fallback to default
const DEFAULT_DEVICE_ID = process.env.REACT_APP_DEFAULT_DEVICE_ID || 'RPiStepper_001';

// --- Helper Functions ---
const formatTimestamp = (ts) => {
  if (!ts) return 'N/A';
  try {
      return new Date(ts * 1000).toLocaleString();
  } catch (e) {
      return 'Invalid Date';
  }
};

function App() {
  const [deviceId, setDeviceId] = useState(DEFAULT_DEVICE_ID); // Allow changing device ID later?
  const [config, setConfig] = useState({}); // Store fetched config
  const [status, setStatus] = useState({ timestamp: null }); // Store latest status
  const [commandStatus, setCommandStatus] = useState(''); // Feedback on command send
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [error, setError] = useState(null);

  // Refs for input fields to manage uncontrolled state temporarily if needed,
  // but controlled components are generally preferred. Using state for inputs here.
  const [motor1Target, setMotor1Target] = useState('');
  const [motor2Target, setMotor2Target] = useState('');
  // State for config inputs - reflects the *editing* state
  const [editableConfig, setEditableConfig] = useState({});

  // Ref for status polling interval
  const statusIntervalRef = useRef(null);

  // --- Fetch Config ---
  const fetchConfig = useCallback(async () => {
    setIsLoadingConfig(true);
    setError(null);
    setCommandStatus('');
    try {
      const response = await axios.get(`${API_BASE_URL}/devices/${deviceId}/config`);
      setConfig(response.data || {});
      setEditableConfig(response.data || {}); // Initialize editable config
      // Maybe pre-fill some control inputs based on config?
    } catch (err) {
      console.error("Error fetching config:", err);
      const errorMsg = err.response?.data?.error || err.message || 'Network Error?';
      setError(`Failed to fetch config: ${errorMsg}`);
      setConfig({}); // Reset config on error
      setEditableConfig({});
    } finally {
      setIsLoadingConfig(false);
    }
  }, [deviceId]); // Re-fetch if deviceId changes

  // --- Save Config ---
  const saveConfig = async () => {
    setError(null);
    setCommandStatus('');
    setIsSavingConfig(true);
    try {
      // Convert relevant editable config fields to numbers before saving
      const configToSend = { ...editableConfig };
      for (const key in configToSend) {
          // Example conversion - adjust based on your config fields
          if (key.includes('speed') || key.includes('accel') || key.includes('config')) {
              const numVal = parseInt(configToSend[key], 10);
              if (!isNaN(numVal)) {
                  configToSend[key] = numVal;
              } else {
                   // Handle invalid number input? Or let backend validate?
                   console.warn(`Invalid number for ${key}: ${configToSend[key]}`);
                   // Optionally remove invalid keys or set to default?
              }
          }
      }

      await axios.put(`${API_BASE_URL}/devices/${deviceId}/config`, configToSend);
      setCommandStatus('Configuration saved successfully!');
      setConfig(configToSend); // Update main config state after successful save
    } catch (err) {
      console.error("Error saving config:", err);
      const errorMsg = err.response?.data?.error || err.message || 'Network Error?';
      setError(`Failed to save config: ${errorMsg}`);
    } finally {
      setIsSavingConfig(false);
    }
  };

  // --- Send Command ---
  const sendCommand = async (commandPayload) => {
     setError(null);
     setCommandStatus('Sending command...');
     try {
       const response = await axios.post(`${API_BASE_URL}/devices/${deviceId}/command`, commandPayload);
       setCommandStatus(`Command accepted (MID: ${response.data?.mid || 'N/A'})`);
       // Optionally clear command status after a delay
       setTimeout(() => setCommandStatus(''), 3000);
     } catch (err) {
       console.error("Error sending command:", err);
       const errorMsg = err.response?.data?.error || err.message || 'Network Error?';
       setError(`Failed to send command: ${errorMsg}`);
       setCommandStatus(''); // Clear status on error
     }
  };

  // --- Fetch Status (Polling) ---
  // NOTE: WebSockets are strongly recommended for real-time status updates.
  // This polling approach is simpler but less efficient and real-time.
  const fetchStatus = useCallback(async () => {
      setIsLoadingStatus(true); // Indicate loading on manual refresh or initial load
      // setError(null); // Optionally clear error on each poll?
      try {
         const response = await axios.get(`${API_BASE_URL}/devices/${deviceId}/status`);
         setStatus(response.data || { timestamp: null });
      } catch (err) {
         console.warn("Error fetching status:", err);
         // Don't necessarily set a major error for failed status poll, could be temporary
         // setError(`Status fetch failed: ${err.message}`);
         // If 404, maybe device just hasn't reported status yet?
         if (err.response?.status !== 404) {
              setError(`Status fetch failed: ${err.response?.data?.error || err.message}`);
         }
         // Keep previous status if fetch fails? Or clear it?
         // setStatus({ timestamp: null });
      } finally {
        setIsLoadingStatus(false);
      }
  }, [deviceId]);

  // --- Handle Config Input Changes ---
  const handleEditableConfigChange = (e) => {
    const { name, value } = e.target;
    setEditableConfig(prevConfig => ({
      ...prevConfig,
      [name]: value, // Store as string from input, convert on save
    }));
  };

  // --- Effects ---
  useEffect(() => {
    fetchConfig(); // Fetch config on initial load or deviceId change
    fetchStatus(); // Fetch status on initial load or deviceId change

    // Set up polling interval for status
    // Clear existing interval if deviceId changes
    if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
    }
    // Poll every 2 seconds (adjust interval as needed)
    statusIntervalRef.current = setInterval(fetchStatus, 2000);

    // Cleanup interval on component unmount or before re-running effect
    return () => {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
    };
  }, [fetchConfig, fetchStatus, deviceId]); // Dependencies: functions and deviceId


  // --- UI Rendering ---
  const renderStatusValue = (label, value, formatFn = (v) => v) => (
      <p><strong>{label}:</strong> {status.timestamp ? formatFn(value) : 'N/A'}</p>
  );

  return (
    <div className="App">
      <header className="App-header">
        <h1>Stepper Motor Control</h1>
        {/* Basic Device ID display/selector could go here */}
        <p>Device ID: {deviceId}</p>
      </header>

      {/* Global Error/Feedback Area */}
      {error && <p className="error-message">Error: {error}</p>}
      {commandStatus && <p className="command-status">{commandStatus}</p>}

      <div className="main-content">
        {/* Status Section */}
        <section className="card status-card">
          <h2>
            Device Status
            <button onClick={fetchStatus} disabled={isLoadingStatus} className="refresh-button">
                {isLoadingStatus ? 'Refreshing...' : 'Refresh'}
            </button>
          </h2>
          {isLoadingStatus && !status.timestamp && <p>Loading status...</p>}
          {renderStatusValue('Last Update', status.timestamp, formatTimestamp)}
          {renderStatusValue('Connection', status.connection_status)}
          {renderStatusValue('Motor 1 Pos', status.motor1_pos)}
          {renderStatusValue('Motor 2 Pos', status.motor2_pos)}
          {renderStatusValue('Status Flags', status.status_flags, (v) => `0x${v?.toString(16)}`)}
          {renderStatusValue('Switch Flags', status.switch_flags, (v) => `SW1:${v & 1 ? 'P' : '-'} SW2:${v & 2 ? 'P' : '-'}`)}
          {renderStatusValue('Error Flags', status.error_flags, (v) => `0x${v?.toString(16)}`)}
        </section>

        {/* Control Section */}
        <section className="card control-card">
          <h2>Motor Control</h2>
          <div className="control-group">
            <label htmlFor="m1_target">M1 Target:</label>
            <input
              id="m1_target"
              type="number"
              value={motor1Target}
              onChange={(e) => setMotor1Target(e.target.value)}
              placeholder="Steps"
            />
            <button onClick={() => sendCommand({ motor: 1, action: 'set_target', value: parseInt(motor1Target || 0, 10) })}>
              Set & Move M1
            </button>
             <button onClick={() => sendCommand({ motor: 1, action: 'stop_move' })}>
               Stop M1
             </button>
          </div>
          <div className="control-group">
            <label htmlFor="m2_target">M2 Target:</label>
            <input
              id="m2_target"
              type="number"
              value={motor2Target}
              onChange={(e) => setMotor2Target(e.target.value)}
              placeholder="Steps"
            />
            <button onClick={() => sendCommand({ motor: 2, action: 'set_target', value: parseInt(motor2Target || 0, 10) })}>
              Set & Move M2
            </button>
             <button onClick={() => sendCommand({ motor: 2, action: 'stop_move' })}>
               Stop M2
             </button>
          </div>
           {/* Add more buttons: e.g., Home, Jog */}
           {/* <button onClick={() => sendCommand({ motor: 1, action: 'start_homing' })}>Home M1</button> */}
        </section>

        {/* Configuration Section */}
        <section className="card config-card">
          <h2>Configuration</h2>
          {isLoadingConfig ? <p>Loading configuration...</p> : (
            <div className="config-form">
              {/* Dynamically create inputs based on editableConfig keys, or list known keys */}
              {Object.keys(editableConfig).sort().map(key => (
                <div className="config-item" key={key}>
                  <label htmlFor={`config_${key}`}>{key}:</label>
                  <input
                    id={`config_${key}`}
                    type="text" // Use text for flexibility, convert on save
                    name={key}
                    value={editableConfig[key] ?? ''}
                    onChange={handleEditableConfigChange}
                  />
                </div>
              ))}
              {Object.keys(editableConfig).length === 0 && !isLoadingConfig && <p>No configuration loaded or device not found.</p>}

              <div className="config-actions">
                  <button onClick={saveConfig} disabled={isSavingConfig}>
                      {isSavingConfig ? 'Saving...' : 'Save Configuration'}
                  </button>
                  <button onClick={fetchConfig} disabled={isLoadingConfig}>
                      Reload Configuration
                  </button>
                   <button onClick={() => sendCommand({ action: 'resend_config' })} title="Tell agent to refetch and apply config">
                      Force Agent Re-apply Config
                   </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
