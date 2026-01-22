const { app, BrowserWindow } = require("electron");
const path = require("node:path");

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "../preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      // Disable sandbox so preload can access required Node APIs (fs, path).
      sandbox: false,
    },
  });

  win.loadFile(path.join(__dirname, "../index.html"));
  win.webContents.openDevTools({ mode: "detach" });

  win.webContents.on("did-fail-load", (_event, errorCode, errorDescription) => {
    console.error("[main] failed to load renderer", { errorCode, errorDescription });
  });
}

app.whenReady().then(createWindow);
