#!/usr/bin/env python3
"""
banking_assistant.py
====================
Optional AI assistant for the Problem 4 banking model (banking_system.py).
Prepared by: Khizar Rizwan (instructor: Bilal Nadeem, CS2012 Introduction to OOP)

It answers questions about the bank's records ("why was BIL-002 refused?",
"what could Bilal Ahmed do for Ravi Textiles?") and turns requests such as
"deposit 5,000 into CUR-001" into a pre-filled operation form. The assistant
never performs an operation itself: a person checks the form and presses Run,
and the model's own rules still decide.

Class hierarchy (multi-level):

    Assistant (abstract)       keeps the conversation; finds the records a question is about
      -> OfflineAssistant      answers from the records with rules; always available
          -> ClaudeAssistant   the same, but Claude writes the answer; falls back to offline

Like banking_system.py it uses no libraries: requests are read word by word,
and the tests use the model's own TestCase and TestRunner. The only optional
package is Anthropic's client, needed only for Claude:
    pip install anthropic
    set ANTHROPIC_API_KEY=...      (Windows)   export ANTHROPIC_API_KEY=... (macOS/Linux)
Never put the key in the code or the repository.

    python banking_assistant.py            chat in the terminal with the demo bank
    python banking_assistant.py --test     run the assistant's tests
"""
from __future__ import annotations

import sys          # only for the command line (sys.argv) and the exit code

import banking_system as bs

# The forms the assistant may pre-fill, with the fields it may fill. Actor fields
# ("performed by") are never filled by the assistant: the signed-in person acts.
FORMS = {
    "Deposit cash": ["Account", "Amount"],
    "Withdraw cash": ["Account", "Amount", "Presented by"],
    "Transfer to a beneficiary": ["From account", "Beneficiary", "Amount", "Instructed by"],
    "Report a card": ["Card", "Report", "Reported by"],
    "Open a dispute": ["Payment", "Amount", "Reason"],
    "Log a complaint": ["Customer", "Summary", "Category"],
}


def _plain(amount):
    """Money('5000.00') -> '5000', Money('2.50') -> '2.5' (as typed into a form)."""
    return str(bs.Exact(amount))


PUNCTUATION = ".,;:!?()'\""


def words(text):
    """The words of a request in lower case, without the punctuation around them:
    'Deposit 5,000 into CUR-001.' -> ['deposit', '5,000', 'into', 'cur-001']."""
    return [w.strip(PUNCTUATION) for w in text.lower().split() if w.strip(PUNCTUATION)]


def references(text):
    """Every word that could be a reference number, in capitals: letters and digits joined by
    hyphens ("Why was BIL-002's payment refused?" -> [..., 'BIL-002', 'S', ...])."""
    out, word = [], ""
    for ch in text.upper() + " ":
        if ch.isalnum() or ch == "-":
            word += ch
        elif word:
            out.append(word.strip("-"))
            word = ""
    return out


def is_ref(word, prefix, digits=3):
    """True for a reference such as 'cur-001': is_ref(word, 3) accepts any 3-letter prefix,
    is_ref(word, 'card') only 'card-' followed by 3 digits."""
    if isinstance(prefix, int):
        head, _, tail = word.partition("-")
        return len(head) == prefix and head.isalpha() and len(tail) == digits and tail.isdigit()
    return word.startswith(prefix + "-") and len(word) == len(prefix) + 1 + digits and word[-digits:].isdigit()


class FormAction:
    """A suggestion to open one operation form with some fields already filled in."""

    def __init__(self, operation, values):
        if operation not in FORMS:
            raise ValueError(f"the assistant may not prepare '{operation}'")
        unknown = set(values) - set(FORMS[operation])
        if unknown:
            raise ValueError(f"'{operation}' has no field {sorted(unknown)}")
        self.operation, self.values = operation, {k: str(v) for k, v in values.items()}

    def __str__(self):
        return f"{self.operation}: " + ", ".join(f"{k} = {v}" for k, v in self.values.items())


class Reply:
    """What the assistant said, which records it used, an optional form and who answered."""

    def __init__(self, text, facts=(), action=None, source="offline"):
        self.text, self.facts, self.action, self.source = text, list(facts), action, source


class Exchange:
    """One question and its reply, kept in order (the conversation is history, like the bank's)."""

    def __init__(self, on, question, reply):
        self.on, self.question, self.reply = on, question, reply


# =============================================================================
# Base class: conversation and retrieval shared by every assistant
# =============================================================================
class Assistant(bs.Abstract):
    """Answers questions about one bank. Subclasses decide how the answer is written."""

    name = "Assistant"

    def __init__(self, bank_source):
        # bank_source is a callable returning the current Bank, so "Reset data" in the GUI is followed
        self._bank_source = bank_source if callable(bank_source) else (lambda: bank_source)
        self.conversation = []

    @property
    def bank(self):
        return self._bank_source()

    def ask(self, question):
        """Template method: find the records the question is about, answer, and keep the exchange."""
        question = question.strip()
        facts = self.find_facts(question)
        reply = self.answer(question, facts)
        self.conversation.append(Exchange(self.bank.today, question, reply))
        return reply

    @bs.abstract
    def answer(self, question, facts):
        """Write the reply (a Reply) from the question and the facts found."""

    # ------------------------------------------------------------------ retrieval
    def find_records(self, question):
        """Every record the question names, by reference number or by name."""
        bank, found = self.bank, []
        registries = (bank.transactions, bank.arrangements, bank.cards, bank.cases, bank.beneficiaries,
                      bank.products, bank.branches, bank.employees)
        for ref in references(question):
            for registry in registries:
                if ref in registry and registry[ref] not in found:
                    found.append(registry[ref])
        low = question.lower()
        for party in bank.parties.values():
            name = party.name.lower()
            short = name.replace(" (pvt) ltd", "").replace(" education trust", "")
            if name in low or short in low:
                found.append(party)
        return found

    def find_facts(self, question):
        """Plain-text facts: the named records, plus bank-wide facts the question's words ask for."""
        bank, low = self.bank, question.lower()
        facts = []
        for record in self.find_records(question):
            facts.extend(self.describe(record))
        if any(w in low for w in ("waiting", "approv", "pending", "held", "hold")):
            waiting = [t for t in bank.transactions.values()
                       if t.status.current in ("AWAITING_AUTHORISATION", "HELD_FOR_REVIEW")]
            facts.append(f"Payments waiting: {len(waiting)}")
            facts += [f"  {t.txn_id} {bs.fmt(t.amount)} {t.narrative} [{t.status.current}]" for t in waiting]
        if any(w in low for w in ("refused", "failed", "declined", "rejected")) and not self.find_records(question):
            refused = [t for t in bank.transactions.values() if t.status.current in ("FAILED", "DECLINED")][-5:]
            facts.append("Most recent refused payments:")
            facts += [f"  {t.txn_id} {bs.fmt(t.amount)} [{t.status.current}] because {t.failure_reason}" for t in refused]
        if "case" in low:
            open_cases = [c for c in bank.cases.values() if c.is_open]
            facts.append(f"Open cases: {len(open_cases)}")
            facts += [f"  {c.case_id} {c.kind}: {c.summary}" for c in open_cases]
        if any(w in low for w in ("trial balance", "books", "balance the")):
            facts.append(f"Trial balance total on {bank.today}: {bank.trial_balance()[1]:,.2f} (zero means the books balance)")
        return facts

    def describe(self, record):
        """A few lines about one record, taken from the model's own methods."""
        bank = self.bank
        if isinstance(record, bs.BankTransaction):
            lines = list(bank.transaction_story(record))
            if record.failure_reason:
                lines.append(f"  refused because: {record.failure_reason}")
            return lines
        if isinstance(record, bs.Arrangement):
            amount, meaning = record.position()
            return [f"{record.number} {type(record).__name__} '{record.product.name}' held by "
                    f"{', '.join(h.name for h in record.holders)}; {meaning} {bs.fmt(amount)}; "
                    f"status {record.status.trail()}"]
        if isinstance(record, bs.IssuedCard):
            chain = " -> ".join(f"{c.card_id} [{c.status.current}]" for c in record.lineage())
            return [f"{record.card_id} {record.masked_number} for {record.cardholder.name} on {record.account.number}; "
                    f"status {record.status.trail()}; replacement chain {chain}"]
        if isinstance(record, bs.Case):
            return [f"{record.case_id} {record.kind}: {record.summary}; status {record.status.trail()}"
                    + (f"; outcome {record.outcome}" if record.outcome else "")]
        if isinstance(record, bs.Person):
            lines = [f"{record.name} ({record.party_id}), a Person"]
            lines += [f"  {c}" for c in bank.capacities_of(record)]
            return lines
        if isinstance(record, bs.Organization):
            lines = [f"{record.name} ({record.party_id}), a {type(record).__name__}"]
            lines += [f"  {m}" for m in record.mandates]
            return lines
        if isinstance(record, bs.Employee):
            a = record.role_on(bank.today)
            return [f"{record.person.name} ({record.employee_no}): {a.role + ' at ' + a.branch.code if a else 'no current role'}; "
                    f"employment {record.status.trail()}"]
        return [str(record)]


# =============================================================================
# Offline assistant: rules only, works anywhere
# =============================================================================
class OfflineAssistant(Assistant):
    """Answers from the records with simple rules. No internet, no key, no package needed."""

    name = "Offline assistant"
    SCALE = {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lac": 100_000, "m": 1_000_000, "million": 1_000_000}

    def answer(self, question, facts):
        action = self.parse_action(question)
        if action:
            return Reply(f"I have prepared the '{action.operation}' form ({action}). Check it and press "
                         f"Run operation; the bank's rules still decide.", facts, action)
        low = question.lower()
        refused = [r for r in self.find_records(question)
                   if isinstance(r, bs.BankTransaction) and r.failure_reason]
        if "why" in low and refused:
            t = refused[0]
            return Reply(f"{t.txn_id} was refused ({t.status.current}) because {t.failure_reason}. "
                         f"It is kept on record, not deleted.", facts)
        if facts:
            return Reply("Here is what the records show:\n" + "\n".join(facts), facts)
        return Reply(self.HELP, facts)

    HELP = ("Ask me about a record by its reference or name, for example: 'Why was BIL-002 refused?', "
            "'Tell me about CARD-001', 'What can Bilal Ahmed do for Ravi Textiles?', "
            "'Which payments are waiting?'. I can also prepare a form: 'Deposit 5,000 into CUR-001', "
            "'Report card CARD-004 stolen'.")

    def amount(self, number, scale):
        """'5,000' -> 5000; '2.5', 'lakh' -> 250000 (None if it is not a number)."""
        if not number[:1].isdigit():
            return None
        try:
            value = bs.Exact(number.replace(",", ""))
        except ValueError:
            return None
        return value * self.SCALE.get(scale, 1)

    def read_amount(self, ws, i):
        """An amount starting at word i: '5,000', 'pkr 5000', 'rs 2.5 lakh', '5k'.
        Returns (amount, index of the next word), or None."""
        if i < len(ws) and ws[i] in ("pkr", "rs"):
            i += 1
        if i >= len(ws):
            return None
        word = ws[i]
        for currency in ("pkr", "rs."):              # written together: 'pkr5000'
            if word.startswith(currency):
                word = word[len(currency):]
        end = 0
        while end < len(word) and (word[end].isdigit() or word[end] in ",."):
            end += 1
        number, scale, i = word[:end], word[end:], i + 1
        if not scale and i < len(ws) and ws[i] in self.SCALE:
            scale, i = ws[i], i + 1
        if scale and scale not in self.SCALE:
            return None
        value = self.amount(number, scale)
        return None if value is None else (value, i)

    def parse_action(self, question):
        """Turn a request into a pre-filled form, or None. The words are read in order:
        'deposit <amount> into <account>', 'report|block ... <card> ... lost|stolen|damaged',
        'dispute ... <card payment>'."""
        ws = words(question)
        for i, word in enumerate(ws):
            if word in ("deposit", "withdraw"):
                found = self.read_amount(ws, i + 1)
                if found:
                    value, j = found
                    if j + 1 < len(ws) and ws[j] in ("into", "in", "to", "from") and is_ref(ws[j + 1], 3):
                        op = "Deposit cash" if word == "deposit" else "Withdraw cash"
                        return FormAction(op, {"Account": ws[j + 1].upper(), "Amount": _plain(value)})
            if word in ("report", "block"):
                later = ws[i + 1:]
                cards = [w for w in later if is_ref(w, "card")]
                kinds = [w for w in later if w in ("lost", "stolen", "damaged")]
                if cards and kinds:
                    card = cards[0].upper()
                    values = {"Card": card, "Report": kinds[0].upper()}
                    holder = self.bank.cards.get(card)
                    if holder is not None:
                        values["Reported by"] = holder.cardholder.name
                    return FormAction("Report a card", values)
            if word == "dispute":
                payments = [w for w in ws[i + 1:] if is_ref(w, "crd-tx")]
                if payments:
                    ref = payments[0].upper()
                    txn = self.bank.transactions.get(ref)
                    values = {"Payment": ref}
                    if txn is not None:
                        values["Amount"] = _plain(txn.amount)
                    return FormAction("Open a dispute", values)
        return None


# =============================================================================
# Claude assistant: the same retrieval and actions, Claude writes the answer
# =============================================================================
class ClaudeAssistant(OfflineAssistant):
    """Sends the question and the facts found in the records to Claude.

    It inherits retrieval and the rule-based answer from OfflineAssistant and uses
    that answer whenever Claude cannot be reached, so the program never depends on
    the internet. Claude only sees the facts retrieved for the question.
    """

    name = "Claude"
    MODEL = "claude-opus-5"
    SYSTEM = (
        "You are the assistant inside Indus Commercial Bank's operations console, a teaching simulation "
        "of a commercial bank. Answer the staff member's question using only the records provided with "
        "each question; if they do not contain the answer, say what is missing. Keep answers short and "
        "use the record reference numbers. Reply in the language of the question (English, Urdu or "
        "Roman Urdu). You cannot change any record. If the user asks for one of these operations: "
        + "; ".join(f"'{op}' (fields: {', '.join(fields)})" for op, fields in FORMS.items())
        + ", end your reply with one line: ACTION: {\"operation\": \"...\", \"values\": {\"Field\": \"value\"}} "
        "using reference numbers or names from the records, and say that the user must check the form "
        "and press Run. Otherwise do not write an ACTION line.")

    def __init__(self, bank_source, client=None):
        super().__init__(bank_source)
        if client is None:
            import anthropic                     # optional package: pip install anthropic
            client = anthropic.Anthropic()       # reads ANTHROPIC_API_KEY (or a saved `ant auth login` profile)
        self.client = client

    @classmethod
    def available(cls):
        """True when the anthropic package is installed and it finds credentials."""
        try:
            import anthropic
            anthropic.Anthropic()
            return True
        except Exception:                        # package missing or no credentials: stay offline
            return False

    def answer(self, question, facts):
        offline = super().answer(question, facts)
        records = "\n".join(facts) or "(no records matched the question)"
        messages = []
        for ex in self.conversation[-4:]:        # a short, append-only history
            messages += [{"role": "user", "content": ex.question}, {"role": "assistant", "content": ex.reply.text}]
        messages.append({"role": "user", "content": f"Records (business date {self.bank.today}):\n{records}\n\n"
                                                    f"Question: {question}"})
        try:
            response = self.client.beta.messages.create(
                model=self.MODEL,
                max_tokens=16000,
                system=self.SYSTEM,
                messages=messages,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"],   # if a request is declined, the API retries
                fallbacks="default",                          # it on a fallback model automatically
            )
        except Exception as error:               # no internet, bad key, rate limit...: answer offline
            offline.text += f"\n(Claude could not be reached: {type(error).__name__}; this is the offline answer.)"
            return offline
        if response.stop_reason == "refusal":
            offline.text += "\n(Claude declined this question; this is the offline answer.)"
            return offline
        text = "\n".join(block.text for block in response.content if block.type == "text").strip()
        action, lines = offline.action, []
        for line in text.splitlines():
            if line.strip().startswith("ACTION:"):
                try:
                    data = bs.Json.loads(line.split("ACTION:", 1)[1])
                    action = FormAction(data["operation"], data.get("values", {}))
                except (ValueError, KeyError, TypeError, AttributeError):
                    pass                         # an unusable suggestion is ignored, never run
            else:
                lines.append(line)
        return Reply("\n".join(lines).strip() or offline.text, facts, action, source=self.MODEL)


def make_assistant(bank_source):
    """Claude when it is installed and has credentials, otherwise the offline assistant."""
    if ClaudeAssistant.available():
        return ClaudeAssistant(bank_source)
    return OfflineAssistant(bank_source)


# =============================================================================
# Tests (python banking_assistant.py --test)
# =============================================================================
def _demo_bank():
    return bs.run_demo(bs.DemoLog(echo=False))


class _FakeClaude:
    """Stands in for the Anthropic client in tests: returns a canned reply, or raises."""

    def __init__(self, text=None, error=None, stop_reason="end_turn"):
        outer = self

        class _Block:
            type = "text"

        class _Response:
            pass

        class _Messages:
            def create(self, **kwargs):
                outer.last_request = kwargs
                if error:
                    raise error
                block, response = _Block(), _Response()
                block.text, response.content, response.stop_reason = text, [block], stop_reason
                return response

        class _Beta:
            messages = _Messages()

        self.beta = _Beta()


class AssistantTests(bs.TestCase):
    bank = None

    @classmethod
    def setUpClass(cls):
        cls.bank = _demo_bank()

    def test_explains_a_refused_payment_from_the_record(self):
        reply = OfflineAssistant(self.bank).ask("Why was BIL-002 refused?")
        self.assertIn("BIL-002", reply.text)
        self.assertIn("mandate", reply.text)

    def test_prepares_forms_but_never_runs_them(self):
        before = len(self.bank.transactions)
        reply = OfflineAssistant(self.bank).ask("Deposit 5k into CUR-001")
        self.assertEqual(reply.action.operation, "Deposit cash")
        self.assertEqual(reply.action.values, {"Account": "CUR-001", "Amount": "5000"})
        self.assertEqual(len(self.bank.transactions), before)       # nothing was posted

    def test_card_report_names_the_cardholder(self):
        reply = OfflineAssistant(self.bank).ask("please block card-004, it was stolen")
        self.assertEqual(reply.action.values["Report"], "STOLEN")
        self.assertEqual(reply.action.values["Reported by"], "Hamza Sheikh")

    def test_finds_people_and_their_mandates(self):
        facts = OfflineAssistant(self.bank).find_facts("What can Bilal Ahmed do for Ravi Textiles?")
        self.assertTrue(any("MND-002" in f for f in facts))

    def test_only_listed_forms_and_fields_are_allowed(self):
        with self.assertRaises(ValueError):
            FormAction("Close a branch", {})
        with self.assertRaises(ValueError):
            FormAction("Deposit cash", {"Teller": "anyone"})

    def test_claude_answer_and_suggested_form(self):
        fake = _FakeClaude('BIL-002 failed: no PAYMENTS mandate.\nACTION: {"operation": "Log a complaint", '
                           '"values": {"Customer": "Ravi Textiles", "Summary": "bill refused"}}')
        reply = ClaudeAssistant(self.bank, client=fake).ask("Why was BIL-002 refused? Log a complaint.")
        self.assertEqual(reply.source, ClaudeAssistant.MODEL)
        self.assertNotIn("ACTION", reply.text)
        self.assertEqual(reply.action.operation, "Log a complaint")
        self.assertIn("BIL-002", fake.last_request["messages"][-1]["content"])   # the facts were sent

    def test_claude_suggestion_outside_the_list_is_ignored(self):
        fake = _FakeClaude('Done.\nACTION: {"operation": "Close a branch", "values": {}}')
        self.assertIsNone(ClaudeAssistant(self.bank, client=fake).ask("close LHR-01").action)

    def test_falls_back_to_the_offline_answer(self):
        fake = _FakeClaude(error=ConnectionError("no internet"))
        reply = ClaudeAssistant(self.bank, client=fake).ask("Why was BIL-002 refused?")
        self.assertEqual(reply.source, "offline")
        self.assertIn("offline answer", reply.text)

    def test_conversation_is_kept(self):
        a = OfflineAssistant(self.bank)
        a.ask("Tell me about CARD-001")
        a.ask("Which payments are waiting?")
        self.assertEqual([e.question for e in a.conversation], ["Tell me about CARD-001", "Which payments are waiting?"])


def main(argv):
    if "--test" in argv:
        return 0 if bs.TestRunner(globals()).run() else 1
    bank = _demo_bank()
    assistant = make_assistant(bank)
    print(f"{assistant.name} for {bank.name} (business date {bank.today}). Empty line to quit.")
    print(OfflineAssistant.HELP)
    while True:
        try:
            question = input("\nYou: ").strip()
        except EOFError:
            break
        if not question:
            break
        reply = assistant.ask(question)
        print(f"\n{assistant.name}: {reply.text}")
        if reply.action:
            print(f"[form prepared: {reply.action}] (open the GUI to check and run it)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
