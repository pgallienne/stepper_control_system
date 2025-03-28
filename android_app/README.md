# Stepper Motor Control - Android Application

This React Native application provides a mobile interface for controlling and configuring stepper motors via the backend API.

## Setup

1.  **React Native Environment:** Follow the official React Native documentation for setting up your development environment. Choose "React Native CLI Quickstart" and the appropriate Development OS (macOS, Windows, Linux) and Target OS (Android).
    *   [React Native Environment Setup](https://reactnative.dev/docs/environment-setup)
    *   You will need Node.js, JDK, Android Studio (including Android SDK and emulator/device).
2.  **Install Dependencies:** Navigate to this directory (`android_app`) in your terminal and run:
    ```bash
    npm install
    # or
    yarn install
    ```

## Configuration

The application determines the backend API URL based on whether it's a development (`__DEV__`) build and the platform (Android emulator uses `10.0.2.2` to access the host's localhost).

Modify the `API_BASE_URL` logic within `src/App.js` if needed, especially the `PROD_API_URL` for release builds.
