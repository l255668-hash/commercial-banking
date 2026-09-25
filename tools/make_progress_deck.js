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

// 1. Title -------------------------------------------------------------------
let s = pres.addSlide();
s.background = { color: TEAL };
s.addText("Project Presentation 1  •  Progress checkpoint", { x: 0.6, y: 0.8, w: 8.8, h: 0.4, fontFace: BODY, fontSize: 16, color: "CFE3DF", margin: 0, isTextBox: true });
s.addText("Problem 4: Commercial Banking, Lending, Payments and Compliance", { x: 0.6, y: 1.25, w: 8.8, h: 1.3, fontFace: HEAD, fontSize: 32, bold: true, color: WHITE, margin: 0, isTextBox: true });
s.addText("Modelling a bank with classes and inheritance, without reducing everything to “account”", { x: 0.6, y: 2.6, w: 8.8, h: 0.45, fontFace: BODY, fontSize: 15, italic: true, color: "E9D3A6", margin: 0, isTextBox: true });
s.addText([{ text: "Khizar Rizwan", options: { bold: true, fontSize: 16, breakLine: true } },
  { text: "Roll number: ________________", options: { breakLine: true } },
  { text: "CS2012 Introduction to Object-Oriented Programming  •  Instructor: Bilal Nadeem" }],
  { x: 0.6, y: 3.6, w: 8.8, h: 1.2, fontFace: BODY, fontSize: 13, color: WHITE, margin: 0, isTextBox: true });
s.addNotes("[0:00-0:20] Assalam-o-Alaikum. I am Khizar Rizwan, and my project is Problem 4: a commercial bank modelled with classes and inheritance. " +
  "In five minutes I will show where the project stands, the research behind the design, the class and inheritance diagrams, one workflow and one lifecycle, and what I will do next.");

// 2. Progress ------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Where the project stands", "Seven phases, planned from the course outline; five done, two ahead", 0);
const phases = [["Domain research", "done"], ["Assumptions & requirements", "done"], ["Class & inheritance design", "done"],
  ["Core implementation + tests", "done"], ["Scenario demo + GUI", "done"], ["Feedback & refinement", "now"], ["Final report & viva", "next"]];
const colour = { done: GREEN, now: AMBER, next: "9AAAA7" }, label = { done: "Done", now: "In progress", next: "Next" };
const x0 = 0.55, step = 1.27, yLine = 1.9;
s.addShape(pres.shapes.LINE, { x: x0 + 0.2, y: yLine, w: step * 6, h: 0, line: { color: LINE, width: 2 } });
phases.forEach(([name, st], i) => {
  const x = x0 + i * step;
  s.addShape(pres.shapes.OVAL, { x, y: yLine - 0.2, w: 0.4, h: 0.4, fill: { color: colour[st] }, line: { color: WHITE, width: 2 } });
  s.addText(String(i + 1), { x, y: yLine - 0.2, w: 0.4, h: 0.4, fontFace: HEAD, fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText(name, { x: x - 0.4, y: yLine + 0.3, w: 1.2, h: 0.55, fontFace: BODY, fontSize: 10.5, bold: true, color: INK, align: "center", valign: "top", margin: 0, isTextBox: true });
  s.addText(label[st], { x: x - 0.4, y: yLine + 0.85, w: 1.2, h: 0.25, fontFace: BODY, fontSize: 10, color: colour[st], align: "center", margin: 0, isTextBox: true });
});
const stats = [["71", "business classes"], ["98", "Bank operations"], ["4", "multi-level hierarchies"], ["16", "exception scenarios"], ["73", "automated tests"]];
stats.forEach(([n, l], i) => {
  const x = 0.5 + i * 1.84;
  card(s, x, 3.45, 1.7, 1.45);
  s.addText(n, { x, y: 3.55, w: 1.7, h: 0.75, fontFace: HEAD, fontSize: 34, bold: true, color: TEAL, align: "center", margin: 0, isTextBox: true });
  s.addText(l, { x, y: 4.3, w: 1.7, h: 0.4, fontFace: BODY, fontSize: 11.5, color: GREY, align: "center", margin: 0, isTextBox: true });
});
s.addText("Brief asks for at least 30 classes, 30 operations and one multi-level hierarchy", { x: 0.5, y: 5.05, w: 9, h: 0.3, fontFace: BODY, fontSize: 11, italic: true, color: GREY, margin: 0, isTextBox: true });
s.addNotes("[0:20-1:05] Here is my progress. I planned seven phases. The first five are complete: research, assumptions, the class design, the core implementation with tests, and a seeded demonstration with a desktop interface. " +
  "The numbers underneath are measured from the code: 71 business classes, 98 operations, four multi-level inheritance hierarchies, 16 scenarios where the normal workflow breaks, and 73 automated tests that all pass. " +
  "The brief asks for at least 30 classes and 30 operations, so the minimum is covered. I am now in phase six, refining the design with your feedback, and phase seven is the final report and viva.");

// 3. Research -> design ----------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Research changed the design", "Three findings from KYC rules, payment lifecycles and card-scheme rules", 1);
const finds = [
  ["One person, many roles", "KYC treats customer, director, owner and signatory as roles of one person.",
    "One Person record; roles are dated objects (Mandate, OfficerRole), not subclasses."],
  ["Nothing is erased", "Banks counteract a wrong payment with a new entry; they never edit history.",
    "Reversal and Chargeback are new transactions linked to the original."],
  ["Product ≠ customer’s product", "A product can close to new customers while old holders keep their terms.",
    "ProductDefinition (the offer) vs Arrangement (what a customer holds, pinned to a terms version)."]];
finds.forEach(([t, found, design], i) => {
  const x = 0.5 + i * 3.05;
  card(s, x, 1.4, 2.85, 3.6);
  s.addText(t, { x: x + 0.2, y: 1.55, w: 2.45, h: 0.6, fontFace: HEAD, fontSize: 15, bold: true, color: TEAL, margin: 0, valign: "top", isTextBox: true });
  s.addText("Found", { x: x + 0.2, y: 2.2, w: 2.45, h: 0.25, fontFace: BODY, fontSize: 10, bold: true, color: BRASS, margin: 0, isTextBox: true });
  s.addText(found, { x: x + 0.2, y: 2.45, w: 2.45, h: 1.0, fontFace: BODY, fontSize: 12, color: INK, margin: 0, valign: "top", isTextBox: true });
  s.addText("So the model has", { x: x + 0.2, y: 3.45, w: 2.45, h: 0.25, fontFace: BODY, fontSize: 10, bold: true, color: BRASS, margin: 0, isTextBox: true });
  s.addText(design, { x: x + 0.2, y: 3.7, w: 2.45, h: 1.2, fontFace: BODY, fontSize: 12, color: INK, margin: 0, valign: "top", isTextBox: true });
});
s.addNotes("[1:05-1:50] Before designing I researched how banks actually work, and three findings changed my design. " +
  "First, know-your-customer rules treat customer, director, owner and signatory as roles of one person. So I have one Person class, and the roles are separate dated objects, not subclasses. " +
  "Second, banks never erase a wrong payment; they post a new entry that counteracts it. So a Reversal, and a card Chargeback, are new transactions linked to the original. " +
  "Third, a bank product can stop being sold while existing customers keep it on their old terms. So I separated the product definition from the customer's own arrangement.");

// 4. Class diagram -------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Class model after research", "Four hierarchies (inheritance) plus standalone classes linked by association", 2);
fitImage(s, "class_diagram.png", 0.4, 1.3, 9.2, 3.75);
s.addText("Full diagram in the design report; generated from the code, so it cannot drift from it", { x: 0.5, y: 5.1, w: 9, h: 0.3, fontFace: BODY, fontSize: 10.5, italic: true, color: GREY, margin: 0, isTextBox: true });
s.addNotes("[1:50-2:30] This is the class diagram. It is generated from the code itself, so it always matches the program. " +
  "There are four hierarchies: parties, arrangements, transactions and cases. Everything else, like cards, mandates, branches and employees, is a standalone class connected by association, because those things are related to each other but are not kinds of each other. " +
  "That distinction was my main rule: inheritance only for an is-a relationship where the parent's data genuinely belongs to every child.");

// 5. Inheritance -----------------------------------------------------------------------
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
s.addNotes("[2:30-3:15] Here are two of the multi-level hierarchies as UML. Party, then Organization, then Company and Charity: an organization adds registration and officers, and each subclass adds its own rule, for example a charity needs two trustees. " +
  "Arrangement, then DepositAccount, then current, savings and term deposit: every deposit account has a ledger and balance, and each subclass changes only one behaviour. " +
  "On the right are tempting inheritances I rejected. A customer is a role with a start and an end, not a kind of person. A card holds no money, so it is not an account. A sole trader is legally the person. And a merchant refund is not a reversal, because the original purchase stays valid.");

// 6. Flowchart ----------------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "One workflow end to end: a large transfer", "Flowchart in standard symbols, in the order the code checks the rules", 3);
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
s.addNotes("[3:15-3:50] This flowchart shows one complete workflow, a large transfer from the company account through digital banking, exactly the case in the brief. " +
  "The code checks the rules in this order: authority, then funds and limits, then dual control, where a second signatory must approve, then the compliance hold for review. " +
  "If any rule fails, the payment is not thrown away; it is kept as a failed transaction with the reason, so the history is complete.");

// 7. State machine + critical case ------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "A lifecycle the code enforces: the card", "UML state machine drawn from the class's own LIFECYCLE declaration", 3);
fitImage(s, "state_2_card.png", 0.4, 1.3, 5.6, 3.3);
card(s, 6.25, 1.3, 3.35, 3.8);
s.addText("Critical case from the brief", { x: 6.45, y: 1.4, w: 3.0, h: 0.35, fontFace: HEAD, fontSize: 14, bold: true, color: TEAL, margin: 0, isTextBox: true });
bullets(s, ["Card reported stolen → blocked", "Replaced, with a different daily limit", "Old card found → destroyed, never re-activated",
  "Every payment still names the physical card used", "Illegal moves (Destroyed → Active) raise an error"], 6.4, 1.85, 3.1, 3.2, 12);
s.addText("Tested: test_stolen_replaced_card_cannot_be_reactivated, test_card_search_covers_the_replacement_chain", { x: 0.5, y: 4.75, w: 5.6, h: 0.3, fontFace: BODY, fontSize: 10.5, italic: true, color: GREY, margin: 0, isTextBox: true });
s.addNotes("[3:50-4:30] Records also change over time, so each class declares its lifecycle. This UML state machine for a card is drawn from that declaration, and the same declaration is enforced in the code. " +
  "It covers the brief's critical case: a card is reported stolen and blocked, replaced with a different limit, and when the old card is found it is destroyed, never re-activated. Every old payment still names the exact card that was used, and an illegal move, like destroyed back to active, is refused.");

// 8. Next steps -------------------------------------------------------------------------------
s = pres.addSlide(); s.background = { color: WHITE };
header(s, "Next steps to the final submission", "What remains, in order", 4);
const next = [["Now", "Refine the model with feedback from this checkpoint"],
  ["Next", "Save and load the bank's records with files / JSON (course weeks 6 and 11)"],
  ["Next", "Review the design against SOLID and the design patterns taught (weeks 10-11)"],
  ["Final", "Complete the design report and diagrams; prepare the viva"]];
next.forEach(([tag, t], i) => {
  const y = 1.4 + i * 0.85;
  card(s, 0.5, y, 9.0, 0.7);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.65, y: y + 0.15, w: 0.9, h: 0.4, fill: { color: tag === "Now" ? AMBER : tag === "Final" ? TEAL : TEAL2 }, rectRadius: 0.08, line: { color: WHITE } });
  s.addText(tag, { x: 0.65, y: y + 0.15, w: 0.9, h: 0.4, fontFace: BODY, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText(t, { x: 1.8, y, w: 7.5, h: 0.7, fontFace: BODY, fontSize: 14, color: INK, valign: "middle", margin: 0, isTextBox: true });
});
s.addText("Thank you — questions welcome", { x: 0.5, y: 4.9, w: 9, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: BRASS, margin: 0, isTextBox: true });
s.addNotes("[4:30-5:00] To finish, my next steps. Now, I will refine the model with your feedback from today. Next, I will add saving and loading the bank's records with files and JSON, which we cover in the course, and review the design against SOLID and the design patterns we will study. " +
  "Finally, I will complete the report and prepare for the viva. Thank you, I am happy to take questions.");

pres.writeFile({ fileName: DOCS + "Progress_Presentation_1.pptx" }).then(f => console.log("written " + f));
