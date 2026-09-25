// Minimal Markdown -> DOCX converter for the design report (headings, paragraphs,
// tables, fenced code, numbered lists, images, **bold**, *italic*, `code`).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, AlignmentType, LevelFormat,
  Footer, PageNumber,
} = require("docx");

const [src, out] = process.argv.slice(2);
const base = path.dirname(src);
const lines = fs.readFileSync(src, "utf8").split("\n");
const CONTENT = 9026; // A4 width minus 1" margins, in DXA
const FONT = "Calibri";

function inline(text, opts = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...opts }));
    const t = m[0];
    if (t.startsWith("**")) runs.push(new TextRun({ text: t.slice(2, -2), bold: true, ...opts }));
    else if (t.startsWith("`")) runs.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: opts.size || 19, ...opts, font: "Consolas" }));
    else runs.push(new TextRun({ text: t.slice(1, -1), italics: true, ...opts }));
    last = m.index + t.length;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...opts }));
  return runs;
}

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "9AA9B8" };
const borders = { top: border, bottom: border, left: border, right: border };

function table(rows) {
  const cells = rows.map(r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim()));
  const header = cells[0];
  const body = cells.slice(2);
  const n = header.length;
  // column widths proportional to (capped) text length
  const weights = header.map((_, i) => Math.min(60, Math.max(8, ...cells.filter((_, k) => k !== 1).map(r => (r[i] || "").length))));
  const total = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map(w => Math.floor((w / total) * CONTENT));
  widths[n - 1] += CONTENT - widths.reduce((a, b) => a + b, 0);
  const mk = (row, head) => new TableRow({
    tableHeader: head,
    children: row.map((c, i) => new TableCell({
      borders, width: { size: widths[i], type: WidthType.DXA },
      shading: head ? { fill: "DDE7F0", type: ShadingType.CLEAR, color: "auto" } : undefined,
      margins: { top: 50, bottom: 50, left: 90, right: 90 },
      children: [new Paragraph({ children: inline(c, { size: 18, bold: head || undefined }) })],
    })),
  });
  return new Table({
    width: { size: CONTENT, type: WidthType.DXA }, columnWidths: widths,
    rows: [mk(header, true), ...body.map(r => mk(r, false))],
  });
}

const children = [];
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  if (line.startsWith("```")) {
    const code = [];
    for (i++; i < lines.length && !lines[i].startsWith("```"); i++) code.push(lines[i]);
    code.forEach(c => children.push(new Paragraph({
      shading: { fill: "F3F5F7", type: ShadingType.CLEAR, color: "auto" }, spacing: { after: 0 },
      children: [new TextRun({ text: c || " ", font: "Consolas", size: 18 })],
    })));
    children.push(new Paragraph({ children: [] }));
  } else if (line.startsWith("|")) {
    const rows = [];
    for (; i < lines.length && lines[i].startsWith("|"); i++) rows.push(lines[i]);
    i--;
    children.push(table(rows));
    children.push(new Paragraph({ spacing: { after: 60 }, children: [] }));
  } else if (/^#{1,3} /.test(line)) {
    const level = line.match(/^#+/)[0].length;
    const text = line.replace(/^#+ /, "");
    children.push(new Paragraph({
      heading: [HeadingLevel.TITLE, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][level - 1],
      pageBreakBefore: level === 2 && /^\d+\./.test(text),
      children: [new TextRun(text)],
    }));
  } else if (/^!\[.*\]\((.+)\)/.test(line)) {
    const file = path.join(base, line.match(/\((.+)\)/)[1]);
    const { w, h, data } = pngSize(file);
    const scale = Math.min(620 / w, 860 / h);        // fit the text width and one page's height
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new ImageRun({ type: "png", data, transformation: { width: Math.round(w * scale), height: Math.round(h * scale) } })] }));
  } else if (/^\d+\. /.test(line)) {
    children.push(new Paragraph({ numbering: { reference: "num", level: 0 },
      children: inline(line.replace(/^\d+\. /, "")) }));
  } else if (line.trim() === "---" || line.trim() === "") {
    continue;
  } else {
    children.push(new Paragraph({ children: inline(line) }));
  }
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", run: { size: 40, bold: true, color: "1D3B5A" }, paragraph: { spacing: { after: 200 } } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, color: "1D3B5A" }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, color: "1D3B5A" }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, color: "2E5475" }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [{ reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ["Problem 4 design report - page ", PageNumber.CURRENT], size: 16, color: "666666" })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(out, b); console.log("written", out, b.length); });
