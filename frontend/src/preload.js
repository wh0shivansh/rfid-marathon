// Preload: expose secure, limited APIs to the renderer.
// - Loads env (.env) for frontend credentials and config
// - Exposes config and file-backed RSA key loading (no local caching; handled on RFID hub)
console.log("[preload] initializing secure bridge");

const { contextBridge } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const fernet = require('fernet');
require("dotenv").config({ path: path.join(__dirname, "../.env") });

function getEnv(name, fallback = "") {
  return process.env[name] || fallback;
}

// Create a wrapper object with the necessary fernet functions
const fernetWrapper = {
  decrypt: (key, token) => {
    try {
      const secret = new fernet.Secret(key);
      const fernetToken = new fernet.Token({
        secret: secret,
        token: token,
        ttl: 0
      });
      return fernetToken.decode();
    } catch (err) {
      console.error('[Fernet] Decryption error:', err);
      throw err;
    }
  },
  encrypt: (key, message) => {
    try {
      const secret = new fernet.Secret(key);
      const fernetToken = new fernet.Token({ secret: secret });
      return fernetToken.encode(message);
    } catch (err) {
      console.error('[Fernet] Encryption error:', err);
      throw err;
    }
  }
};

contextBridge.exposeInMainWorld("secureApi", {
  getConfig: () => ({
    apiBaseUrl: getEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1"),
    // Prefer explicit frontend-specific env vars, but fall back to backend USERNAME/PASSWORD
    username: getEnv("FRONTEND_USERNAME", getEnv("USERNAME", "")),
    password: getEnv("FRONTEND_PASSWORD", getEnv("PASSWORD", "")),
    deviceId: getEnv("FRONTEND_DEVICE_ID", "registration-station"),
  }),
  Fernet: fernetWrapper,
});

console.log("[preload] secureApi exposed");