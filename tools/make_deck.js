// Viva deck for the Problem 4 banking OOP project.
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const DOCS = path.join(__dirname, "..", "docs") + "/";

const TEAL = "0B4F4A", TEAL2 = "1F6F68", MIST = "E8F0EE", BRASS = "B8862F", INK = "1D2B2A", GREY = "5B6B69", WHITE = "FFFFFF";
const HEAD = "Cambria", BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Problem 4 - Commercial Banking OOP design";

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
function title(slide, text, sub) {
  slide.addText(text, { x: 0.5, y: 0.3, w: 9, h: 0.6, fontFace: HEAD, fontSize: text.length > 40 ? 22 : 28, bold: true, color: TEAL, margin: 0, fit: "shrink", isTextBox: true });
  if (sub) slide.addText(sub, { x: 0.5, y: 0.88, w: 9, h: 0.35, fontFace: BODY, fontSize: 12, italic: true, color: GREY, margin: 0, isTextBox: true });
}
function bullets(slide, items, x, y, w, h, size = 13) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { x, y, w, h, fontFace: BODY, fontSize: size, color: INK, paraSpaceAfter: 6, valign: "top", margin: 0.05, isTextBox: true });
}
function badge(slide, n, x, y) { // numbered brass circle: the deck's motif
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color: BRASS } });
  slide.addText(String(n), { x, y, w: 0.42, h: 0.42, fontFace: HEAD, fontSize: 14, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
function card(slide, x, y, w, h, fill = MIST) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: 0.08, line: { color: fill } });
}

// 1. Title -----------------------------------------------------------------
let s = pres.addSlide();
s.background = { color: TEAL };
s.addText("Problem 4", { x: 0.6, y: 0.9, w: 8.8, h: 0.5, fontFace: BODY, fontSize: 18, color: "CFE3DF", margin: 0, isTextBox: true });
s.addText("Commercial Banking, Lending, Payments and Compliance", { x: 0.6, y: 1.35, w: 8.8, h: 1.3, fontFace: HEAD, fontSize: 36, bold: true, color: WHITE, margin: 0, isTextBox: true });
s.addText("An object model where nothing is deleted and every past state can be rebuilt", { x: 0.6, y: 2.75, w: 8.8, h: 0.5, fontFace: BODY, fontSize: 16, italic: true, color: "E9D3A6", margin: 0, isTextBox: true });
s.addText([{ text: "Name: ____________________", options: { breakLine: true } }, { text: "Roll number: _____________", options: { breakLine: true } }, { text: "Course: __________________" }],
  { x: 0.6, y: 3.7, w: 5, h: 1.2, fontFace: BODY, fontSize: 13, color: WHITE, margin: 0, isTextBox: true });
s.addNotes("Introduce the project: a teaching model of a commercial bank. The assessed concepts are classes and inheritance. The central idea is that history is never overwritten.");

// 2. Scale at a glance -------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "The project at a glance", "One Python file, standard library only - banking_system.py");
const stats = [["73", "domain classes"], ["96", "Bank operations (78 commands)"], ["4", "multi-level hierarchies"], ["16", "complex scenarios"], ["60", "automated tests"], ["0.00", "trial balance total"]];
stats.forEach(([n, label], i) => {
  const x = 0.5 + (i % 3) * 3.05, y = 1.45 + Math.floor(i / 3) * 1.9;
  card(s, x, y, 2.85, 1.65);
  s.addText(n, { x, y: y + 0.15, w: 2.85, h: 0.85, fontFace: HEAD, fontSize: 40, bold: true, color: TEAL, align: "center", margin: 0, isTextBox: true });
  s.addText(label, { x: x + 0.1, y: y + 1.0, w: 2.65, h: 0.5, fontFace: BODY, fontSize: 13, color: GREY, align: "center", margin: 0, isTextBox: true });
});
s.addNotes("The brief asks for at least 30 classes and 30 meaningful operations. Even counting only the 78 state-changing commands we are more than double. The trial balance is zero at the end of the demo, so no scenario created or lost money.");

// 3. Core rule ---------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "Core rule: nothing that happened is ever deleted", "Four techniques answer every question of the form \"what was true on date X?\"");
const tech = [["Periods", "Mandates, officer roles, ownerships, restrictions and RM assignments are valid from-to. Revoking closes the period."],
  ["Status histories", "Every lifecycle keeps each status with date, actor and reason, so status_on(date) is answerable."],
  ["Versions", "Product terms, beneficiary details and repayment schedules change by adding a version, never by editing."],
  ["Counter-records", "Money is never edited: a Reversal posts equal and opposite entries; the original stays."]];
tech.forEach(([h, t], i) => {
  const x = 0.5 + (i % 2) * 4.6, y = 1.45 + Math.floor(i / 2) * 1.95;
  card(s, x, y, 4.4, 1.75);
  badge(s, i + 1, x + 0.2, y + 0.22);
  s.addText(h, { x: x + 0.8, y: y + 0.2, w: 3.4, h: 0.45, fontFace: HEAD, fontSize: 17, bold: true, color: TEAL, margin: 0, isTextBox: true });
  s.addText(t, { x: x + 0.8, y: y + 0.68, w: 3.45, h: 0.95, fontFace: BODY, fontSize: 12.5, color: INK, margin: 0, valign: "top", isTextBox: true });
});
s.addNotes("This is the answer to the brief's question about deletion. Closing an account, ending a relationship or revoking a mandate are status changes or closed periods. Bank.party_snapshot rebuilds what the bank knew about a customer on any past date.");

// 4-7. Hierarchies -------------------------------------------------------------
const hier = [
  ["Party -> Organization -> Company / Charity", "uml_parties.png",
    ["Party: identity, documents, checks, corrections, restrictions", "Organization adds officers, owners, mandates and a stricter KYC rule (connected persons must be verified too)", "Company needs a director; Charity needs two trustees: structural_gaps() overridden", "Customer, director, signatory are ROLES, not subclasses"],
    "Three levels because each level has a rule that is genuinely true there and not above it. Ayesha is one Person record with five capacities."],
  ["Arrangement -> DepositAccount -> Current / Savings", "uml_arrangements.png",
    ["Arrangement: product, pinned terms, holders, branch history, status, restrictions", "DepositAccount adds what only accounts holding money have: ledger, holds, available balance", "Current overrides overdraft_limit(); Savings and FixedTermDeposit extend check_debit()", "FinancingAgreement sits beside DepositAccount: it holds no customer money"],
    "The middle level exists because holding customer money is a real behavioural difference. A loan inheriting a ledger balance would be meaningless."],
];
hier.forEach(([t, img, pts, note]) => {
  s = pres.addSlide(); s.background = { color: WHITE };
  title(s, t);
  bullets(s, pts, 0.5, 1.2, 4.1, 3.9, 13);
  card(s, 4.85, 1.1, 4.65, 4.15, "F4F8F7");
  fitImage(s, img, 4.95, 1.2, 4.45, 3.95);
  s.addNotes(note);
});

s = pres.addSlide(); s.background = { color: WHITE };
title(s, "BankTransaction -> CustomerPayment / LoanTransaction", "Every movement is double-entry; post() refuses legs that do not sum to zero");
fitImage(s, "uml_transactions.png", 0.4, 1.35, 9.2, 2.6);
bullets(s, ["CustomerPayment adds initiator, channel, mandate used, 2nd signatory, disputes", "Transfer snapshots the beneficiary version; Card the exact card; Bill the biller; OwnAccount the target", "LoanTransaction groups disbursement, repayment and interest capitalisation"], 0.5, 4.05, 9, 1.3, 12.5);
s.addNotes("Only customer payments can be disputed, which is why that level exists. A reversal is a transaction of its own, pointing at the original.");

s = pres.addSlide(); s.background = { color: WHITE };
title(s, "Case -> CustomerCase / RiskCase", "Separate, linked records: the branch complaint and the compliance investigation");
fitImage(s, "uml_cases.png", 0.4, 1.35, 9.2, 2.6);
bullets(s, ["CustomerCase: arrives through a channel from a contact person (dispute, complaint, service request)", "RiskCase: bank-initiated; overrides close() so it cannot close while its restrictions are live", "CollectionsCase: opened by the arrears batch"], 0.5, 4.05, 9, 1.3, 12.5);
s.addNotes("Scenario 5 shows the override: closing the investigation is refused until the debit block is lifted.");

// 8. Rejected ------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "Tempting inheritances we rejected", "Ten in the report; four of the strongest");
const rej = [["Customer(Person)", "One human is customer, director and signatory at once; roles start and end on different dates."],
  ["IssuedCard(DepositAccount)", "A card holds no money and many cards share one account: it is a credential."],
  ["FinancingAgreement(DepositAccount)", "A loan has no ledger of customer funds, holds or available balance."],
  ["reversed = True flag", "A reversal has its own date, amount, approver and reason, and can be partial."]];
rej.forEach(([h, t], i) => {
  const x = 0.5 + (i % 2) * 4.6, y = 1.45 + Math.floor(i / 2) * 1.95;
  card(s, x, y, 4.4, 1.75);
  s.addText("x", { x: x + 0.2, y: y + 0.22, w: 0.42, h: 0.42, fontFace: HEAD, fontSize: 16, bold: true, color: WHITE, fill: { color: "9C3D10" }, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText(h, { x: x + 0.8, y: y + 0.2, w: 3.45, h: 0.45, fontFace: "Courier New", fontSize: 11, bold: true, color: TEAL, margin: 0, isTextBox: true });
  s.addText(t, { x: x + 0.8, y: y + 0.7, w: 3.45, h: 0.95, fontFace: BODY, fontSize: 12.5, color: INK, margin: 0, valign: "top", isTextBox: true });
});
s.addNotes("The obvious alternative, 'everything is an account with flags', fails every critical case: a flag change destroys the fact that it was once different.");

// 9. Scenarios -----------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "16 scenarios break the normal workflow", "All ten critical cases in the brief are covered, plus every participant it names");
const sc = ["Document expires mid-onboarding", "Large transfer: dual control, hold, release", "Card stolen, replaced twice, found", "Posted, reversed, re-posted, disputed", "Restricted then cleared", "Financing: limits, arrears, restructure", "Director leaves; authority provable",
  "Beneficiary changes bank details", "Evidence keeps corrected data", "Product withdrawn, terms pinned", "Branch closes; all moves", "Savings limit; closure not deletion", "Staff and customer leave", "Sole trader, private client, term deposits", "Card controls, bills, card search", "Auditor review; archive vs delete"];
sc.forEach((t, i) => {
  const col = i < 8 ? 0 : 1, row = i < 8 ? i : i - 8;
  const x = 0.5 + col * 4.6, y = 1.3 + row * 0.5;
  badge(s, i + 1, x, y);
  s.addText(t, { x: x + 0.55, y, w: 3.9, h: 0.42, fontFace: BODY, fontSize: 12.5, color: INK, valign: "middle", margin: 0, isTextBox: true });
});
s.addNotes("Run python banking_system.py to show them live. Each refusal prints the exact rule, e.g. AuthorityError: the initiator cannot also be the second signatory.");

// 9b. Coverage beyond the critical cases -------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "Everything the brief names is modelled", "Found by rereading Problem 4 line by line; each has a test");
const cov = [["Sole traders & private clients", "Person with a trading name; PRIVATE needs verified source of wealth (EDD)"],
  ["Fixed-term deposits", "Third DepositAccount subclass: no early debits, maturity payout, break penalty"],
  ["Card controls", "Online, international, cash, merchant category - each with a validity period"],
  ["Billers", "BillPayment is a CustomerPayment: same mandates, restrictions, dual control"],
  ["Collections staff", "Collections officer works the case; promise to pay marked kept or broken"],
  ["Auditors & retention", "Approvals audit with role at the time; archive, never delete (10-year retention)"]];
cov.forEach(([h, t], i) => {
  const x = 0.5 + (i % 3) * 3.05, y = 1.4 + Math.floor(i / 3) * 1.95;
  card(s, x, y, 2.85, 1.75);
  s.addText(h, { x: x + 0.15, y: y + 0.12, w: 2.55, h: 0.55, fontFace: HEAD, fontSize: 14, bold: true, color: TEAL, margin: 0, isTextBox: true });
  s.addText(t, { x: x + 0.15, y: y + 0.7, w: 2.55, h: 0.95, fontFace: BODY, fontSize: 12, color: INK, margin: 0, valign: "top", isTextBox: true });
});
s.addNotes("Report section 3.2 maps every participant, research area and scope item in the brief to a class, operation and scenario. Section 3.1 answers the brief's eight open questions one by one.");

// 9b2. Flowcharts -----------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "Behaviour: six flowcharts traced from the code", "Standard symbols (ISO 5807); the diamonds are in the order the code checks the rules");
card(s, 0.5, 1.3, 3.5, 3.95, "F4F8F7");
fitImage(s, "flowchart_3_transfer.png", 0.6, 1.38, 3.3, 3.8);
const sym = [["flowChartTerminator", "Start / end; red = refused"], ["flowChartProcess", "Process: one step"],
  ["flowChartDecision", "Decision: Yes / No"], ["flowChartInputOutput", "Input / output"],
  ["flowChartPredefinedProcess", "A named Bank operation"], ["flowChartMagneticDisk", "Ledger / audit log"]];
sym.forEach(([shape, label], i) => {
  const y = 1.35 + i * 0.47;
  s.addShape(shape, { x: 4.3, y, w: 0.7, h: 0.36, fill: { color: i === 2 ? "FDF1D6" : MIST }, line: { color: TEAL, width: 1 } });
  s.addText(label, { x: 5.1, y, w: 2.05, h: 0.36, fontFace: BODY, fontSize: 11, color: INK, valign: "middle", margin: 0, isTextBox: true });
});
const charts = ["Program overview", "Onboarding", "Transfer payment", "Card purchase", "Financing lifecycle", "Desktop console"];
s.addText(charts.map((t, k) => ({ text: `${k + 1}. ${t}`, options: { breakLine: k < charts.length - 1 } })),
  { x: 7.35, y: 1.35, w: 2.15, h: 2.8, fontFace: BODY, fontSize: 12, color: INK, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
s.addText("Report section 4.1; also on the GUI's Diagrams screen", { x: 4.3, y: 4.45, w: 5.2, h: 0.5, fontFace: BODY, fontSize: 11, italic: true, color: GREY, margin: 0, isTextBox: true });
s.addNotes("The class diagrams show structure; the flowcharts show behaviour. Walk through the transfer: beneficiary, authority (mandate within limit), funds, dual control, then the PKR 1,000,000 compliance hold. Every red terminator is a refusal that is still kept on record.");

// 9c. GUI ----------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "Live demo: the desktop console", "banking_gui.py - pure Python (Tkinter); every button calls one Bank operation");
card(s, 0.5, 1.3, 6.1, 3.95, "F4F8F7");
s.addImage({ path: DOCS + "screenshots/gui_01_overview.png", x: 0.6, y: 1.4, w: 5.9, h: 3.6 });
bullets(s, ["Guided rule checks: 14 real operations, each showing the model's own refusal", "30 forms, including full customer onboarding", "Customer timeline and time machine for any past date", "Card chains, cases, audit log and a zero trial balance", "GUI classes inherit too: Page -> MasterDetailPage -> CustomersPage"], 6.85, 1.35, 2.7, 3.9, 12);
s.addNotes("Run Operations > Guided rule checks in order. Then Customers: Ayesha's roles as ribbons, and the time machine on 11 April 2026. The GUI contains no business rules: refusals come from the model and name its error class.");

// 10. Code review ---------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
title(s, "Code review: 20 defects fixed, each with a test");
card(s, 0.5, 1.2, 2.9, 3.9, TEAL);
s.addText("20", { x: 0.5, y: 1.6, w: 2.9, h: 1.2, fontFace: HEAD, fontSize: 60, bold: true, color: WHITE, align: "center", margin: 0, isTextBox: true });
s.addText("defects found and fixed, each with a regression test", { x: 0.75, y: 2.9, w: 2.4, h: 1.2, fontFace: BODY, fontSize: 14, color: "CFE3DF", align: "center", margin: 0, isTextBox: true });
bullets(s, ["A refused loan overpayment still marked installments as paid", "Resolving a dispute twice refunded the customer twice", "Recording an ACTIVE card as found destroyed it", "Replacement cards blocked once the product was withdrawn", "Bank fees used up customers' savings withdrawals", "Account closure ignored holds and pending payments", "No delegated limit on credit approvals"], 3.8, 1.25, 5.7, 3.9, 13.5);
s.addNotes("Full table in docs/Code_Review.md. Every fix is protected by a test, so it cannot silently come back.");

// 11. Limits and closing ---------------------------------------------------------
s = pres.addSlide(); s.background = { color: TEAL };
s.addText("Limitations and how it would scale", { x: 0.6, y: 0.4, w: 8.8, h: 0.6, fontFace: HEAD, fontSize: 28, bold: true, color: WHITE, margin: 0, isTextBox: true });
const lim = [["Today", ["Single currency (PKR)", "In-memory storage", "Two-signatory dual control only", "Fixed review threshold, simple interest"]],
  ["At scale", ["Period -> valid_from / valid_to columns in a database", "Bank split into services linked by events", "Login supplies the acting person", "Islamic products as new Arrangement subclasses"]]];
lim.forEach(([h, pts], i) => {
  const x = 0.6 + i * 4.5;
  s.addText(h, { x, y: 1.3, w: 4.1, h: 0.45, fontFace: HEAD, fontSize: 19, bold: true, color: "E9D3A6", margin: 0, isTextBox: true });
  s.addText(pts.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < pts.length - 1 } })),
    { x, y: 1.85, w: 4.1, h: 2.5, fontFace: BODY, fontSize: 14, color: WHITE, paraSpaceAfter: 8, valign: "top", margin: 0.05, isTextBox: true });
});
s.addText("Thank you - questions?", { x: 0.6, y: 4.6, w: 8.8, h: 0.5, fontFace: HEAD, fontSize: 20, italic: true, color: WHITE, margin: 0, isTextBox: true });
s.addNotes("The Arrangement level is where the design pays off for new business models: an Ijarah or Murabaha contract is a new kind of arrangement, not a change to existing classes.");

pres.writeFile({ fileName: DOCS + "Viva_Presentation.pptx" }).then(f => console.log("written", f));
