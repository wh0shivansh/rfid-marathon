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
        WidthType,
        VerticalAlign,
        TableLayoutType,
        PageOrientation
      } = docx;

      const colWeights = [5, 12, 10, 20, 6, 12, 12, 12, 9];
      const totalWeight = colWeights.reduce((a, b) => a + b, 0);
      const fontSize = 20;
      const cellMargin = 100;
      const tableWidthTwips = 15840;

      // Helper to create cells with padding and word wrap (margins are in twips for docx)
      const makeCell = (text, bold = false, colIndex = 0) => {
        const weight = colWeights[colIndex] || 10;
        return new TableCell({
          width: { size: Math.round((weight / totalWeight) * tableWidthTwips), type: WidthType.DXA },
          margins: { top: cellMargin, bottom: cellMargin, left: cellMargin, right: cellMargin },
          vAlign: VerticalAlign.CENTER,
          children: [
        new Paragraph({
          wordWrap: true,
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
        layout: TableLayoutType.FIXED,
        rows: [headerRow, ...dataRows]
      },);

      const doc = new Document({
        sections: [
          {
            properties: {
              page: {
                size: {
                  orientation: PageOrientation.LANDSCAPE
                },
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
      const baseRowHeight = lineHeight + 6;

      const landscapeSize = [841.89, 595.28];
      const newPage = () => doc.addPage(landscapeSize);
      let page = newPage();
      let { width, height } = page.getSize();
      let y = height - margin;

      const colWeights = [6, 12, 10, 20, 6, 12, 12, 12, 9];
      const totalWeight = colWeights.reduce((a, b) => a + b, 0);
      const availableWidth = width - margin * 2;
      const colWidths = colWeights.map(w => (availableWidth * w) / totalWeight);

      const splitLongWord = (word, maxWidth) => {
        if (!word) return [''];
        const parts = [];
        let current = '';

        for (const char of word) {
          const next = current + char;
          if (font.widthOfTextAtSize(next, fontSize) <= maxWidth || !current) {
            current = next;
          } else {
            parts.push(current);
            current = char;
          }
        }

        if (current) parts.push(current);
        return parts;
      };

      // Helper to wrap text based on measured column width
      const wrapText = (text, colIndex) => {
        const cellWidth = (colWidths[colIndex] || 60) - 6;
        const value = String(text ?? '');
        if (!value) return [''];

        const words = value.split(/\s+/);
        const lines = [];
        let currentLine = '';

        words.forEach(word => {
          const segments = splitLongWord(word, cellWidth);
          segments.forEach(segment => {
            const candidate = currentLine ? `${currentLine} ${segment}` : segment;
            if (font.widthOfTextAtSize(candidate, fontSize) <= cellWidth) {
              currentLine = candidate;
              return;
            }

            if (currentLine) lines.push(currentLine);
            currentLine = segment;
          });
        });
        if (currentLine) lines.push(currentLine);
        return lines.length > 0 ? lines : [''];
      };

      const getRowMetrics = (cells) => {
        const wrappedCells = cells.map((cell, idx) => wrapText(cell, idx));
        const maxLines = Math.max(...wrappedCells.map(lines => lines.length), 1);
        return {
          wrappedCells,
          rowHeight: baseRowHeight + (maxLines - 1) * lineHeight
        };
      };

      const drawRow = (cells, isHeader = false, metrics = null) => {
        const useFont = isHeader ? fontBold : font;
        const color = rgb(0, 0, 0);
        const { wrappedCells, rowHeight } = metrics || getRowMetrics(cells);
        const rowBottom = y - rowHeight;

        let x = margin;
        wrappedCells.forEach((lines, idx) => {
          const cellWidth = colWidths[idx] || 60;

          page.drawRectangle({
            x,
            y: rowBottom,
            width: cellWidth,
            height: rowHeight,
            borderColor: rgb(0, 0, 0),
            borderWidth: 0.5
          });

          const contentHeight = lines.length * lineHeight;
          let lineY = rowBottom + (rowHeight + contentHeight) / 2 - lineHeight + 1;
          lines.forEach(line => {
            page.drawText(line, {
              x: x + 3,
              y: lineY,
              size: fontSize,
              font: useFont,
              color
            });
            lineY -= lineHeight;
          });

          x += cellWidth;
        });
        y = rowBottom;
      };

      const ensureSpace = (requiredHeight, repeatHeader = false) => {
        if (y >= margin + requiredHeight) return;
        page = newPage();
        ({ width, height } = page.getSize());
        y = height - margin;
        if (repeatHeader) {
          const headerMetrics = getRowMetrics(headers);
          drawRow(headers, true, headerMetrics);
        }
      };

      page.drawText(title, { x: margin, y, size: 12, font: fontBold, color: rgb(0, 0, 0) });
      y -= baseRowHeight + 6;

      const writeHeader = () => {
        const headerMetrics = getRowMetrics(headers);
        ensureSpace(headerMetrics.rowHeight);
        drawRow(headers, true, headerMetrics);
      };

      writeHeader();

      rows.forEach((row) => {
        const rowMetrics = getRowMetrics(row);
        ensureSpace(rowMetrics.rowHeight, true);
        drawRow(row, false, rowMetrics);
      });

      return await doc.save();
    } catch (err) {
      console.error('[preload] buildPdf failed:', err);
      return null;
    }
  },
});

console.log("[preload] secureApi exposed");