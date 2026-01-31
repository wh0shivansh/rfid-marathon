// Preload: expose secure, limited APIs to the renderer.
// - Loads env (.env) for frontend credentials and config
// - Exposes config and file-backed RSA key loading (no local caching; handled on RFID hub)
console.log("[preload] initializing secure bridge");

const { contextBridge } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const fernet = require('fernet');
const envPath = path.join(__dirname, "../.env");
require("dotenv").config({ path: envPath });

function getEnv(name, fallback = "") {
  return process.env[name] || fallback;
}

function readEnvFile() {
  try {
    if (!fs.existsSync(envPath)) return [];
    const content = fs.readFileSync(envPath, "utf8");
    return content.split(/\r?\n/);
  } catch (err) {
    console.error("[preload] Failed to read .env:", err);
    return [];
  }
}

function writeEnvFile(lines) {
  try {
    fs.writeFileSync(envPath, lines.join("\n"), "utf8");
  } catch (err) {
    console.error("[preload] Failed to write .env:", err);
  }
}

function upsertEnvKey(lines, key, value) {
  const pattern = new RegExp(`^${key}=`, "i");
  let updated = false;
  const next = lines.map((line) => {
    if (pattern.test(line)) {
      updated = true;
      return `${key}=${value}`;
    }
    return line;
  });
  if (!updated) next.push(`${key}=${value}`);
  return next;
}

function removeEnvKey(lines, key) {
  const pattern = new RegExp(`^${key}=`, "i");
  return lines.filter((line) => !pattern.test(line));
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
    apiBaseUrl: getEnv("VITE_API_BASE_URL", "http://localhost:8001/api/v1"),
    // Prefer explicit frontend-specific env vars, but fall back to backend USERNAME/PASSWORD
    username: getEnv("RFID_USERNAME", getEnv("USERNAME", "")),
    password: getEnv("RFID_PASSWORD", getEnv("PASSWORD", "")),
    deviceId: getEnv("FRONTEND_DEVICE_ID", "registration-station"),
  }),
  getStoredCredentials: () => ({
    username: getEnv("RFID_USERNAME", getEnv("USERNAME", "")),
    password: getEnv("RFID_PASSWORD", getEnv("PASSWORD", "")),
  }),
  setStoredCredentials: (username, password) => {
    const lines = readEnvFile();
    let updated = upsertEnvKey(lines, "RFID_USERNAME", username);
    updated = upsertEnvKey(updated, "RFID_PASSWORD", password);
    writeEnvFile(updated);
    process.env.RFID_USERNAME = username;
    process.env.RFID_PASSWORD = password;
  },
  clearStoredCredentials: () => {
    const lines = readEnvFile();
    let updated = removeEnvKey(lines, "RFID_USERNAME");
    updated = removeEnvKey(updated, "RFID_PASSWORD");
    writeEnvFile(updated);
    delete process.env.RFID_USERNAME;
    delete process.env.RFID_PASSWORD;
  },
  Fernet: fernetWrapper,
});

console.log("[preload] secureApi exposed");