// Progress presentation 1 (5 minutes, one presenter) for the Problem 4 banking OOP project.
// Builds docs/Progress_Presentation_1.pptx; the speaker notes on each slide are the speech.
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const DOCS = path.join(__dirname, "..", "docs") + "/";

const TEAL = "0B4F4A", TEAL2 = "1F6F68", MIST = "E8F0EE", BRASS = "B8862F", INK = "1D2B2A", GREY = "5B6B69",
  WHITE = "FFFFFF", GREEN = "2E7D4F", AMBER = "C98A12", LINE = "C9D6D3";
const HEAD = "Cambria", BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Problem 4 - Progress presentation 1";
pres.author = "Khizar Rizwan";

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function fitImage(slide, file, x, y, maxW, maxH) {
  const { w, h } = pngSize(DOCS + file);
  let iw = maxW, ih = (h / w) * maxW;
  if (ih > maxH) { ih = maxH; iw = (w / h) * maxH; }
  slide.addImage({ path: DOCS + file, x: x + (maxW - iw) / 2, y: y + (maxH - ih) / 2, w: iw, h: ih });
}
const STEPS = ["Progress", "Research", "Design", "Build", "Next"];
function header(slide, text, sub, step) {
  slide.addText(text, { x: 0.5, y: 0.38, w: 9, h: 0.55, fontFace: HEAD, fontSize: text.length > 38 ? 23 : 26, bold: true, color: TEAL, margin: 0, isTextBox: true });
  if (sub) slide.addText(sub, { x: 0.5, y: 0.92, w: 9, h: 0.3, fontFace: BODY, fontSize: 12, italic: true, color: GREY, margin: 0, isTextBox: true });
  // where we are in the talk: the sequence is visible on every slide
  slide.addText(STEPS.map((s, i) => ({ text: (i ? "  ›  " : "") + s,
    options: { bold: i === step, color: i === step ? BRASS : "9AAAA7" } })),
    { x: 5.6, y: 0.1, w: 4.0, h: 0.25, fontFace: BODY, fontSize: 10, align: "right", margin: 0, isTextBox: true });
}
function bullets(slide, items, x, y, w, h, size = 13) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { x, y, w, h, fontFace: BODY, fontSize: size, color: INK, paraSpaceAfter: 6, valign: "top", margin: 0.05, isTextBox: true });
}
function card(slide, x, y, w, h, fill = MIST) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: 0.08, line: { color: fill } });
}


// The speaker notes are the Roman Urdu speech, one "### Slide N" section each, read from the speech file
const SPEECH = fs.readFileSync(DOCS + "Progress_Presentation_1_Speech.md", "utf8");
const roman = SPEECH.split("## Speech in Roman Urdu")[1].split("\n## ")[0];
const NOTES = roman.split(/\n### /).slice(1).map(sec => {
  const [heading, ...rest] = sec.split("\n");
  return heading.replace(/^.*\((.*)\)\s*$/, "[$1] ") + rest.join(" ").replace(/\s+/g, " ").trim();
});
if (NOTES.length !== 9) throw new Error("expected 9 speech sections, found " + NOTES.length);

// 1. Title -------------------------------------------------------------------
let s = pres.addSlide();
s.background = { color: TEAL };
s.addText("Project Presentation 1  •  Progress checkpoint", { x: 0.6, y: 0.8, w: 8.8, h: 0.4, fontFace: BODY, fontSize: 16, color: "CFE3DF", margin: 0, isTextBox: true });
s.addText("Problem 4: Commercial Banking, Lending, Payments and Compliance", { x: 0.6, y: 1.25, w: 8.8, h: 1.3, fontFace: HEAD, fontSize: 32, bold: true, color: WHITE, margin: 0, isTextBox: true });
s.addText("Modelling a bank with classes and inheritance, without reducing everything to “account”", { x: 0.6, y: 2.6, w: 8.8, h: 0.45, fontFace: BODY, fontSize: 15, italic: true, color: "E9D3A6", margin: 0, isTextBox: true });
s.addText([{ text: "Khizar Rizwan  •  25L-5668", options: { bold: true, fontSize: 16, breakLine: true } },
  { text: "CS2012 Introduction to Object-Oriented Programming  •  Instructor: Bilal Nadeem" }],
  { x: 0.6, y: 3.7, w: 8.8, h: 0.9, fontFace: BODY, fontSize: 13, color: WHITE, margin: 0, isTextBox: true });
s.addNotes(NOTES[0]);

// 2. Progress ------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Where the project stands", "Six planned phases: research and design complete, implementation and GUI under way", 0);
const phases = [["Domain research", "done"], ["Assumptions & requirements", "done"], ["Class & inheritance design", "done"],
  ["Implementation (Python)", "now"], ["GUI (Tkinter)", "now"], ["Final report & viva", "next"]];
const colour = { done: GREEN, now: AMBER, next: "9AAAA7" }, label = { done: "Done", now: "In progress", next: "Next" };
const x0 = 0.75, step = 1.62, yLine = 1.9;
s.addShape(pres.shapes.LINE, { x: x0 + 0.2, y: yLine, w: step * 5, h: 0, line: { color: LINE, width: 2 } });
phases.forEach(([name, st], i) => {
  const x = x0 + i * step;
  s.addShape(pres.shapes.OVAL, { x, y: yLine - 0.2, w: 0.4, h: 0.4, fill: { color: colour[st] }, line: { color: WHITE, width: 2 } });
  s.addText(String(i + 1), { x, y: yLine - 0.2, w: 0.4, h: 0.4, fontFace: HEAD, fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText(name, { x: x - 0.55, y: yLine + 0.3, w: 1.5, h: 0.55, fontFace: BODY, fontSize: 11, bold: true, color: INK, align: "center", valign: "top", margin: 0, isTextBox: true });
  s.addText(label[st], { x: x - 0.55, y: yLine + 0.85, w: 1.5, h: 0.25, fontFace: BODY, fontSize: 10.5, color: colour[st], align: "center", margin: 0, isTextBox: true });
});
const stats = [["8", "sources studied"], ["27", "banking terms defined"], ["36", "documented assumptions"], ["71", "classes designed"], ["4", "multi-level hierarchies"]];
stats.forEach(([n, l], i) => {
  const x = 0.5 + i * 1.84;
  card(s, x, 3.45, 1.7, 1.45);
  s.addText(n, { x, y: 3.55, w: 1.7, h: 0.75, fontFace: HEAD, fontSize: 34, bold: true, color: TEAL, align: "center", margin: 0, isTextBox: true });
  s.addText(l, { x, y: 4.3, w: 1.7, h: 0.4, fontFace: BODY, fontSize: 11.5, color: GREY, align: "center", margin: 0, isTextBox: true });
});
s.addText("The brief asks for at least 30 meaningful classes and one multi-level hierarchy", { x: 0.5, y: 5.05, w: 9, h: 0.3, fontFace: BODY, fontSize: 11, italic: true, color: GREY, margin: 0, isTextBox: true });
s.addNotes(NOTES[1]);

// 3. Research sources ------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Domain research: what I studied", "Eight sources, chosen to cover every research area the brief lists", 1);
const sources = [
  ["FATF Recommendations", "Customer due diligence; beneficial owners (Rec. 10, 24, 25)"],
  ["State Bank of Pakistan", "AML/CFT regulations: local KYC practice"],
  ["Basel Committee", "Managing money-laundering risk in banks"],
  ["ISO 20022", "Payment statuses: pending, held, posted, rejected"],
  ["Visa & Mastercard", "Disputes, reason codes, chargebacks"],
  ["IFRS 9", "Loan modification and restructuring"],
  ["BIAN", "Product catalogue vs customer agreement"],
  ["Fowler, Analysis Patterns", "Party roles and time-dated records"]];
sources.forEach(([t, d], i) => {
  const x = 0.5 + (i % 4) * 2.28, y = 1.4 + Math.floor(i / 4) * 1.85;
  card(s, x, y, 2.12, 1.65);
  s.addText(String(i + 1), { x: x + 0.15, y: y + 0.15, w: 0.4, h: 0.4, fontFace: HEAD, fontSize: 18, bold: true, color: BRASS, margin: 0, isTextBox: true });
  s.addText(t, { x: x + 0.15, y: y + 0.55, w: 1.85, h: 0.45, fontFace: HEAD, fontSize: 13, bold: true, color: TEAL, margin: 0, valign: "top", isTextBox: true });
  s.addText(d, { x: x + 0.15, y: y + 1.0, w: 1.85, h: 0.6, fontFace: BODY, fontSize: 11, color: INK, margin: 0, valign: "top", isTextBox: true });
});
s.addText("Full references and a 27-term glossary are in the design report, section 1", { x: 0.5, y: 5.1, w: 9, h: 0.3, fontFace: BODY, fontSize: 10.5, italic: true, color: GREY, margin: 0, isTextBox: true });
s.addNotes(NOTES[2]);

// 4. Research -> design ----------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "How the research changed my design", "My first idea, what the research showed, and the design I adopted", 1);
const finds = [
  ["One person, many roles", "Customer, Director, Signatory as subclasses of Person",
    "One Person record; roles are dated objects (Mandate, OfficerRole)"],
  ["Nothing is erased", "Mark a wrong payment as “refunded”",
    "Reversal and Chargeback: new transactions linked to the original"],
  ["Offer ≠ what a customer holds", "One class for a product and a customer’s account",
    "ProductDefinition (versioned terms) vs Arrangement (pins its version)"]];
finds.forEach(([t, before, after], i) => {
  const x = 0.5 + i * 3.05;
  card(s, x, 1.4, 2.85, 3.6);
  s.addText(t, { x: x + 0.2, y: 1.55, w: 2.45, h: 0.6, fontFace: HEAD, fontSize: 15, bold: true, color: TEAL, margin: 0, valign: "top", isTextBox: true });
  s.addText("First idea", { x: x + 0.2, y: 2.2, w: 2.45, h: 0.25, fontFace: BODY, fontSize: 10, bold: true, color: GREY, margin: 0, isTextBox: true });
  s.addText(before, { x: x + 0.2, y: 2.45, w: 2.45, h: 0.9, fontFace: BODY, fontSize: 12, color: GREY, strike: "sngStrike", margin: 0, valign: "top", isTextBox: true });
  s.addText("After research", { x: x + 0.2, y: 3.4, w: 2.45, h: 0.25, fontFace: BODY, fontSize: 10, bold: true, color: BRASS, margin: 0, isTextBox: true });
  s.addText(after, { x: x + 0.2, y: 3.65, w: 2.45, h: 1.25, fontFace: BODY, fontSize: 12, bold: true, color: INK, margin: 0, valign: "top", isTextBox: true });
});
s.addNotes(NOTES[3]);

// 5. Class diagram -------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Class model after research", "Four hierarchies (inheritance) plus standalone classes linked by association", 2);
fitImage(s, "class_diagram.png", 0.4, 1.3, 9.2, 3.75);
s.addText("Inheritance only for a true “is-a”; everything else is association", { x: 0.5, y: 5.1, w: 9, h: 0.3, fontFace: BODY, fontSize: 10.5, italic: true, color: GREY, margin: 0, isTextBox: true });
s.addNotes(NOTES[4]);

// 6. Inheritance -----------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Multi-level inheritance, and what I rejected", "UML: shared data sits at the highest level where every subclass needs it", 2);
fitImage(s, "uml_parties.png", 0.4, 1.3, 3.0, 3.1);
fitImage(s, "uml_arrangements.png", 3.5, 1.3, 3.0, 3.1);
s.addText("Party › Organization › Company / Charity", { x: 0.4, y: 4.45, w: 3.0, h: 0.3, fontFace: BODY, fontSize: 10.5, bold: true, color: TEAL, align: "center", margin: 0, isTextBox: true });
s.addText("Arrangement › DepositAccount › Current / Savings / Term", { x: 3.5, y: 4.45, w: 3.0, h: 0.3, fontFace: BODY, fontSize: 10.5, bold: true, color: TEAL, align: "center", margin: 0, isTextBox: true });
card(s, 6.75, 1.3, 2.85, 3.85);
s.addText("Rejected", { x: 6.95, y: 1.4, w: 2.5, h: 0.35, fontFace: HEAD, fontSize: 15, bold: true, color: BRASS, margin: 0, isTextBox: true });
bullets(s, ["Customer(Person): a role that starts and ends, not a kind of person",
  "Card(Account): a card holds no money; it is linked to an account",
  "SoleTrader(Organization): legally the person is liable",
  "MerchantRefund(Reversal): the purchase stays valid"], 6.9, 1.8, 2.6, 3.3, 11.5);
s.addNotes(NOTES[5]);

// 7. Flowchart ----------------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "One workflow end to end: a large transfer", "Flowchart in standard symbols, in the order the rules are checked", 2);
fitImage(s, "flowchart_3_transfer.png", 0.4, 1.25, 3.6, 4.1);
const flow = [["Authority", "Does this person hold a live payments mandate?"], ["Funds and limits", "Enough available balance, within the mandate limit?"],
  ["Dual control", "Above the threshold, a second signatory must approve"], ["Compliance hold", "Very large transfers wait for review, then release"],
  ["Refused?", "Kept on record as FAILED, with the rule that stopped it"]];
flow.forEach(([t, d], i) => {
  const y = 1.3 + i * 0.8;
  s.addShape(pres.shapes.OVAL, { x: 4.4, y: y + 0.05, w: 0.4, h: 0.4, fill: { color: BRASS } });
  s.addText(String(i + 1), { x: 4.4, y: y + 0.05, w: 0.4, h: 0.4, fontFace: HEAD, fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText([{ text: t, options: { bold: true, color: TEAL, breakLine: true } }, { text: d, options: { color: INK } }],
    { x: 5.0, y, w: 4.5, h: 0.72, fontFace: BODY, fontSize: 12, margin: 0, valign: "top", isTextBox: true });
});
s.addNotes(NOTES[6]);

// 8. Implementation and GUI in progress --------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Implementation and GUI: in progress", "Python, standard library only; GUI in Tkinter", 3);
fitImage(s, "screenshots/gui_02_overview.png", 0.4, 1.35, 5.0, 3.2);
s.addText("GUI prototype: staff overview screen", { x: 0.4, y: 4.6, w: 5.0, h: 0.3, fontFace: BODY, fontSize: 10.5, italic: true, color: GREY, align: "center", margin: 0, isTextBox: true });
const work = [["Built", GREEN, ["Party, Arrangement and Transaction hierarchies", "Double-entry ledger: balances derived, never stored", "KYC checks and dated mandates"]],
  ["In progress", AMBER, ["Card and lending workflows", "Exception scenarios from the brief", "GUI screens for staff and customers"]]];
let y = 1.35;
work.forEach(([tag, col, items]) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.7, y, w: 1.3, h: 0.34, fill: { color: col }, rectRadius: 0.08, line: { color: col } });
  s.addText(tag, { x: 5.7, y, w: 1.3, h: 0.34, fontFace: BODY, fontSize: 11.5, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
  bullets(s, items, 5.7, y + 0.42, 3.9, 1.35, 12);
  y += 1.85;
});
s.addNotes(NOTES[7]);

// 9. Next steps -------------------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Next steps to the final submission", "What remains, in order", 4);
const next = [["Now", "Finish the implementation and GUI screens"],
  ["Next", "Test every critical case from the brief with automated tests"],
  ["Next", "Save and load records with files / JSON; review against SOLID (weeks 6, 11)"],
  ["Final", "Complete the design report and diagrams; prepare the viva"]];
next.forEach(([tag, t], i) => {
  const yy = 1.4 + i * 0.85;
  card(s, 0.5, yy, 9.0, 0.7);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.65, y: yy + 0.15, w: 0.9, h: 0.4, fill: { color: tag === "Now" ? AMBER : tag === "Final" ? TEAL : TEAL2 }, rectRadius: 0.08, line: { color: WHITE } });
  s.addText(tag, { x: 0.65, y: yy + 0.15, w: 0.9, h: 0.4, fontFace: BODY, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText(t, { x: 1.8, y: yy, w: 7.5, h: 0.7, fontFace: BODY, fontSize: 14, color: INK, valign: "middle", margin: 0, isTextBox: true });
});
s.addText("Shukriya — questions welcome", { x: 0.5, y: 4.9, w: 9, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: BRASS, margin: 0, isTextBox: true });
s.addNotes(NOTES[8]);

pres.writeFile({ fileName: DOCS + "Progress_Presentation_1.pptx" }).then(f => console.log("written " + f));
