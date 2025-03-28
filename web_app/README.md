# Stepper Motor Control - Web Application

This React application provides a web interface for controlling and configuring stepper motors via the backend API.

## Setup

1.  **Install Node.js and npm/yarn:** If you haven't already, install Node.js (which includes npm) from [nodejs.org](https://nodejs.org/). Yarn is an alternative package manager.
2.  **Install Dependencies:** Navigate to this directory (`web_app`) in your terminal and run:
    ```bash
    npm install
    # or
    yarn install
    ```

## Configuration

The application connects to the backend API specified by the `REACT_APP_API_BASE_URL` environment variable during the build process.

Create a `.env` file in the `web_app` directory with the following content, replacing the URL with your actual backend address:
