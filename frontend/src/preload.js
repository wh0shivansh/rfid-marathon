// Preload: expose secure, limited APIs to the renderer.
// - Loads env (.env) for frontend credentials and config
// - Exposes config and file-backed RSA key loading (no local caching; handled on RFID hub)
console.log("[preload] initializing secure bridge");

const { contextBridge } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const fernet = require('fernet');
let xlsx = null;
try {
  xlsx = require('xlsx');
} catch (err) {
  console.error('[preload] XLSX not available:', err.message);
}
let docx = null;
try {
  docx = require('docx');
} catch (err) {
  console.error('[preload] DOCX not available:', err.message);
}
let pdfLib = null;
try {
  pdfLib = require('pdf-lib');
} catch (err) {
  console.error('[preload] PDF-LIB not available:', err.message);
}
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
    apiBaseUrl: getEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1"),
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
  XLSX: xlsx,
  buildXlsx: (aoa, sheetName = 'Scoreboard') => {
    if (!xlsx) return null;
    try {
      const worksheet = xlsx.utils.aoa_to_sheet(aoa || []);
      const workbook = xlsx.utils.book_new();
      xlsx.utils.book_append_sheet(workbook, worksheet, sheetName);
      return xlsx.write(workbook, { bookType: 'xlsx', type: 'array' });
    } catch (err) {
      console.error('[preload] buildXlsx failed:', err);
      return null;
    }
  },
  buildDocx: async (headers, rows, title = 'Scoreboard Export') => {
    if (!docx) return null;
    try {
      const {
        Document,
        Packer,
        Paragraph,
        Table,
        TableRow,
        TableCell,
        TextRun,
        WidthType
      } = docx;

      const colWeights = [5, 12, 10, 20, 6, 12, 12, 12, 9];
      const totalWeight = colWeights.reduce((a, b) => a + b, 0);
      const fontSize = 20;
      const cellMargin = 100;

      // Helper to create cells with padding (margins are in twips for docx)
      const makeCell = (text, bold = false, colIndex = 0) => {
        const weight = colWeights[colIndex] || 10;
        return new TableCell({
          width: { size: (weight / totalWeight) * 100, type: WidthType.PERCENTAGE },
          margins: { top: cellMargin, bottom: cellMargin, left: cellMargin, right: cellMargin },
          children: [
        new Paragraph({
          children: [new TextRun({ text: String(text ?? ''), bold, size: fontSize })]
        })
          ]
        });
      };


      const headerRow = new TableRow({
        children: headers.map((h, idx) => makeCell(h, true, idx))
      });

      const dataRows = rows.map(row => new TableRow({
        children: row.map((val, idx) => makeCell(val, false, idx))
      }));

      const table = new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows: [headerRow, ...dataRows]
      },);

      const doc = new Document({
        sections: [
          {
            properties: {
              page: {
                margin: {
                  top: 1024,
                  right: 1024,
                  bottom: 1024,
                  left: 1024
                }
              }
            },
            children: [
              new Paragraph({ children: [new TextRun({ text: title, bold: true, size: fontSize })] }),
              new Paragraph(''),
              table
            ]
          }
        ]
      });

      return await Packer.toBuffer(doc);
    } catch (err) {
      console.error('[preload] buildDocx failed:', err);
      return null;
    }
  },
  buildPdf: async (headers, rows, title = 'Scoreboard Export') => {
    if (!pdfLib) return null;
    try {
      const { PDFDocument, StandardFonts, rgb } = pdfLib;
      const doc = await PDFDocument.create();
      const font = await doc.embedFont(StandardFonts.Helvetica);
      const fontBold = await doc.embedFont(StandardFonts.HelveticaBold);

      const margin = 24;
      const fontSize = 10;
      const lineHeight = 12;
      const rowHeight = lineHeight + 6;

      const portraitSize = [595.28, 841.89];
      const newPage = () => doc.addPage(portraitSize);
      let page = newPage();
      let { width, height } = page.getSize();
      let y = height - margin;

      const colWeights = [6, 12, 10, 20, 6, 12, 12, 12, 9];
      const totalWeight = colWeights.reduce((a, b) => a + b, 0);
      const availableWidth = width - margin * 2;
      const colWidths = colWeights.map(w => (availableWidth * w) / totalWeight);

      const drawRow = (cells, isHeader = false) => {
        let x = margin;
        const useFont = isHeader ? fontBold : font;
        const color = rgb(0, 0, 0);
        const rowBottom = y - rowHeight;
        const textY = rowBottom + (rowHeight - fontSize) / 2;

        cells.forEach((cell, idx) => {
          const text = String(cell ?? '');
          const cellWidth = colWidths[idx] || 60;

          page.drawRectangle({
            x,
            y: rowBottom,
            width: cellWidth,
            height: rowHeight,
            borderColor: rgb(0, 0, 0),
            borderWidth: 0.5
          });

          page.drawText(text, {
            x: x + 3,
            y: textY,
            size: fontSize,
            font: useFont,
            color
          });

          x += cellWidth;
        });
        y = rowBottom;
      };

      page.drawText(title, { x: margin, y, size: 12, font: fontBold, color: rgb(0, 0, 0) });
      y -= rowHeight + 6;

      const writeHeader = () => {
        if (y < margin + rowHeight) {
          page = newPage();
          ({ width, height } = page.getSize());
          y = height - margin;
        }
        drawRow(headers, true);
      };

      writeHeader();

      rows.forEach((row) => {
        if (y < margin + rowHeight) {
          page = newPage();
          ({ width, height } = page.getSize());
          y = height - margin;
          writeHeader();
        }
        drawRow(row, false);
      });

      return await doc.save();
    } catch (err) {
      console.error('[preload] buildPdf failed:', err);
      return null;
    }
  },
});

console.log("[preload] secureApi exposed");