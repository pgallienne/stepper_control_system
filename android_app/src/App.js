import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  Button,
  ScrollView,
  ActivityIndicator,
  Alert,
  Platform, // For platform-specific details like API URL
  RefreshControl,
} from 'react-native';
import axios from 'axios';

// --- Config ---
// Android emulator typically uses 10.0.2.2 to reach host machine's localhost
const DEV_API_URL_ANDROID = 'http://10.0.2.2:5000/api';
const DEV_API_URL_IOS = 'http://localhost:5000/api';
// Use localhost for dev, replace with your actual IP/domain for production builds
const PROD_API_URL = 'http://YOUR_LIGHTSAIL_IP_OR_DOMAIN:5000/api';

// Determine API URL based on platform and development mode
const API_BASE_URL = __DEV__
  ? Platform.OS === 'android' ? DEV_API_URL_ANDROID : DEV_API_URL_IOS
  : PROD_API_URL;

const DEFAULT_DEVICE_ID = 'RPiStepper_001'; // Could make this configurable

// --- Helper ---
const formatTimestamp = (ts) => {
    if (!ts) return 'N/A';
    try {
        return new Date(ts * 1000).toLocaleString();
    } catch (e) { return 'Invalid Date'; }
};

export default function App() {
  const [deviceId, setDeviceId] = useState(DEFAULT_DEVICE_ID);
  const [config, setConfig] = useState({});
  const [editableConfig, setEditableConfig] = useState({});
  const [status, setStatus] = useState({ timestamp: null });
  const [commandStatus, setCommandStatus] = useState('');
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false); // For manual refresh
  const [isPollingStatus, setIsPollingStatus] = useState(false); // For background polling indicator
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false); // For pull-to-refresh

  const [motor1Target, setMotor1Target] = useState('');
  const [motor2Target, setMotor2Target] = useState('');

  const statusIntervalRef = useRef(null);

  // --- API Call Functions (Similar logic to web app) ---
  const fetchConfig = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoadingConfig(true);
    setError(null);
    setCommandStatus('');
    try {
      const response = await axios.get(`${API_BASE_URL}/devices/${deviceId}/config`);
      const fetchedConfig = response.data || {};
      setConfig(fetchedConfig);
      setEditableConfig(fetchedConfig);
    } catch (err) {
      console.error("Error fetching config:", err);
      const errorMsg = err.response?.data?.error || err.message || 'Network Error?';
      setError(`Failed to fetch config: ${errorMsg}`);
      setConfig({});
      setEditableConfig({});
    } finally {
      if (showLoading) setIsLoadingConfig(false);
    }
  }, [deviceId]);

  const saveConfig = async () => {
    setError(null);
    setCommandStatus('');
    setIsSavingConfig(true);
    try {
       // Prepare config data (ensure numbers are numbers)
       const configToSend = { ...editableConfig };
       for (const key in configToSend) {
           if (key.includes('speed') || key.includes('accel') || key.includes('config')) {
               const numVal = parseInt(configToSend[key], 10);
               configToSend[key] = isNaN(numVal) ? 0 : numVal; // Default to 0 if invalid
           }
       }
      await axios.put(`${API_BASE_URL}/devices/${deviceId}/config`, configToSend);
      Alert.alert('Success', 'Configuration saved!');
      setConfig(configToSend); // Update main config state
    } catch (err) {
      console.error("Error saving config:", err);
      const errorMsg = err.response?.data?.error || err.message || 'Network Error?';
      setError(`Failed to save config: ${errorMsg}`);
      Alert.alert('Error', `Failed to save config: ${errorMsg}`);
    } finally {
      setIsSavingConfig(false);
    }
  };

  const sendCommand = async (commandPayload) => {
     setError(null);
     setCommandStatus('Sending command...');
     try {
       const response = await axios.post(`${API_BASE_URL}/devices/${deviceId}/command`, commandPayload);
       setCommandStatus(`Command accepted (MID: ${response.data?.mid || 'N/A'})`);
       setTimeout(() => setCommandStatus(''), 3000); // Clear feedback
     } catch (err) {
       console.error("Error sending command:", err);
       const errorMsg = err.response?.data?.error || err.message || 'Network Error?';
       setError(`Failed to send command: ${errorMsg}`);
       Alert.alert('Error', `Failed to send command: ${errorMsg}`);
       setCommandStatus('');
     }
  };

  const fetchStatus = useCallback(async (showLoading = false) => {
      if (showLoading) setIsLoadingStatus(true); else setIsPollingStatus(true);
      // setError(null); // Maybe don't clear error on every poll
      try {
         const response = await axios.get(`${API_BASE_URL}/devices/${deviceId}/status`);
         setStatus(response.data || { timestamp: null });
      } catch (err) {
         console.warn("Error fetching status:", err);
         if (err.response?.status !== 404) { // Don't show error if just no status yet
            setError(`Status fetch failed: ${err.response?.data?.error || err.message}`);
         }
      } finally {
        if (showLoading) setIsLoadingStatus(false); else setIsPollingStatus(false);
      }
  }, [deviceId]);

  // --- Pull-to-refresh Handler ---
   const onRefresh = useCallback(async () => {
     setRefreshing(true);
     setError(null); // Clear error on refresh
     setCommandStatus('');
     await Promise.all([fetchConfig(false), fetchStatus(false)]); // Fetch both, no individual loading indicators
     setRefreshing(false);
   }, [fetchConfig, fetchStatus]);

  // --- Handle Config Input Changes ---
   const handleEditableConfigChange = (name, value) => {
     setEditableConfig(prevConfig => ({
       ...prevConfig,
       [name]: value, // Store as string from TextInput
     }));
   };

  // --- Effects ---
  useEffect(() => {
    fetchConfig();
    fetchStatus(true); // Show loading indicator on initial status fetch

    // Setup polling interval
    if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
    statusIntervalRef.current = setInterval(() => fetchStatus(false), 3000); // Poll every 3 seconds

    // Cleanup on unmount
    return () => {
      if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
    };
  }, [fetchConfig, fetchStatus, deviceId]); // Re-run if functions or deviceId change

  // --- UI ---
  const renderStatusValue = (label, value, formatFn = (v) => v ?? 'N/A') => (
     <View style={styles.statusRow}>
         <Text style={styles.statusLabel}>{label}:</Text>
         <Text style={styles.statusValue}>{status.timestamp ? formatFn(value) : 'N/A'}</Text>
     </View>
  );

  return (
    <ScrollView
        style={styles.container}
        refreshControl={ // Enable pull-to-refresh
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
    >
      <Text style={styles.title}>Stepper Control</Text>
      <Text style={styles.deviceId}>Device ID: {deviceId}</Text>

      {/* Global Error/Feedback */}
      {error && <Text style={styles.errorText}>Error: {error}</Text>}
      {commandStatus && <Text style={styles.statusText}>{commandStatus}</Text>}
      {isPollingStatus && <ActivityIndicator size="small" color="#007AFF" style={styles.pollingIndicator}/>}

      {/* Status Section */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Device Status</Text>
        {(isLoadingStatus && !status.timestamp) ? <ActivityIndicator size="large" color="#007AFF" /> : (
            <>
                {renderStatusValue('Last Update', status.timestamp, formatTimestamp)}
                {renderStatusValue('Connection', status.connection_status)}
                {renderStatusValue('Motor 1 Pos', status.motor1_pos)}
                {renderStatusValue('Motor 2 Pos', status.motor2_pos)}
                {renderStatusValue('Status Flags', status.status_flags, (v) => `0x${v?.toString(16)}`)}
                {renderStatusValue('Switch Flags', status.switch_flags, (v) => `SW1:${v & 1 ? 'P' : '-'} SW2:${v & 2 ? 'P' : '-'}`)}
                {renderStatusValue('Error Flags', status.error_flags, (v) => `0x${v?.toString(16)}`)}
            </>
        )}
      </View>

      {/* Control Section */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Motor Control</Text>
        <View style={styles.controlGroup}>
          <Text style={styles.label}>M1 Target:</Text>
          <TextInput
            style={styles.input}
            keyboardType="numeric"
            value={motor1Target}
            onChangeText={setMotor1Target}
            placeholder="Steps"
          />
          <View style={styles.buttonRow}>
              <Button title="Set & Move" onPress={() => sendCommand({ motor: 1, action: 'set_target', value: parseInt(motor1Target || 0, 10) })} />
              <Button title="Stop" color="#FF3B30" onPress={() => sendCommand({ motor: 1, action: 'stop_move' })} />
          </View>
        </View>
         <View style={styles.controlGroup}>
           <Text style={styles.label}>M2 Target:</Text>
           <TextInput
             style={styles.input}
             keyboardType="numeric"
             value={motor2Target}
             onChangeText={setMotor2Target}
             placeholder="Steps"
           />
            <View style={styles.buttonRow}>
               <Button title="Set & Move" onPress={() => sendCommand({ motor: 2, action: 'set_target', value: parseInt(motor2Target || 0, 10) })} />
               <Button title="Stop" color="#FF3B30" onPress={() => sendCommand({ motor: 2, action: 'stop_move' })} />
           </View>
         </View>
          {/* Add more buttons */}
      </View>

      {/* Configuration Section */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Configuration</Text>
        {isLoadingConfig ? <ActivityIndicator size="large" color="#007AFF" /> : (
          <>
            {Object.keys(editableConfig).sort().map(key => (
              <View style={styles.configItem} key={key}>
                <Text style={styles.configLabel}>{key}:</Text>
                <TextInput
                  style={styles.configInput}
                  value={String(editableConfig[key] ?? '')} // Ensure value is string
                  onChangeText={(value) => handleEditableConfigChange(key, value)}
                  // Use appropriate keyboardType for known numeric fields
                  keyboardType={key.includes('speed') || key.includes('accel') || key.includes('config') ? 'numeric' : 'default'}
                />
              </View>
            ))}
            {Object.keys(editableConfig).length === 0 && !isLoadingConfig && <Text>No configuration loaded.</Text>}

            <View style={styles.buttonContainer}>
                 <Button title={isSavingConfig ? "Saving..." : "Save Config"} onPress={saveConfig} disabled={isSavingConfig} />
            </View>
             <View style={styles.buttonContainer}>
                 <Button title="Reload Config" onPress={() => fetchConfig(true)} disabled={isLoadingConfig} />
             </View>
              <View style={styles.buttonContainer}>
                  <Button title="Force Agent Re-apply" onPress={() => sendCommand({ action: 'resend_config' })} color="#FFA500"/>
              </View>
          </>
        )}
      </View>
    </ScrollView>
  );
}

// --- Styles ---
const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 10,
    backgroundColor: '#F0F0F7',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 10,
    marginTop: Platform.OS === 'ios' ? 30 : 10, // Adjust for status bar
  },
  deviceId: {
      fontSize: 14,
      color: '#666',
      textAlign: 'center',
      marginBottom: 15,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 15,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 1.41,
    elevation: 2,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600', // Semibold
    marginBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#EEE',
    paddingBottom: 8,
  },
  statusRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      marginBottom: 6,
  },
  statusLabel: {
      fontSize: 15,
      color: '#555',
      fontWeight: '500',
  },
  statusValue: {
      fontSize: 15,
      color: '#000',
      textAlign: 'right',
  },
  controlGroup: {
    marginBottom: 15,
  },
  label: {
    fontSize: 15,
    fontWeight: '500',
    marginBottom: 5,
    color: '#333',
  },
  input: {
    borderWidth: 1,
    borderColor: '#DDD',
    backgroundColor: '#FFF',
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 5,
    marginBottom: 10,
    fontSize: 15,
  },
  buttonRow: {
      flexDirection: 'row',
      justifyContent: 'space-around', // Or 'flex-start' with gaps
      // gap: 10, // Not universally supported yet
  },
  buttonContainer: {
      marginTop: 10,
  },
  configItem: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: 8,
  },
  configLabel: {
      fontSize: 14,
      color: '#444',
      width: '45%', // Adjust width as needed
      marginRight: '5%',
  },
  configInput: {
      borderWidth: 1,
      borderColor: '#DDD',
      backgroundColor: '#FFF',
      paddingHorizontal: 8,
      paddingVertical: 5,
      borderRadius: 4,
      fontSize: 14,
      flex: 1, // Take remaining space
  },
  errorText: {
    color: '#D8000C', // Error red
    backgroundColor: '#FFD2D2', // Light red background
    padding: 10,
    borderRadius: 5,
    textAlign: 'center',
    marginBottom: 10,
    fontSize: 14,
  },
  statusText: {
      color: '#00529B', // Info blue
      backgroundColor: '#BDE5F8', // Light blue background
      padding: 10,
      borderRadius: 5,
      textAlign: 'center',
      marginBottom: 10,
      fontSize: 14,
  },
  pollingIndicator: {
      position: 'absolute',
      top: Platform.OS === 'ios' ? 45 : 15, // Adjust position
      right: 15,
  },
});
