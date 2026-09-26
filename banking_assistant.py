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

Nothing to install for the offline assistant. For Claude (optional):
    pip install anthropic
    set ANTHROPIC_API_KEY=...      (Windows)   export ANTHROPIC_API_KEY=... (macOS/Linux)
Never put the key in the code or the repository.

    python banking_assistant.py            chat in the terminal with the demo bank
    python banking_assistant.py --test     run the assistant's tests
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import unittest
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

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
    """Decimal('5000.00') -> '5000', Decimal('2.50') -> '2.5' (as typed into a form)."""
    return format(Decimal(amount).normalize(), "f")


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
class Assistant(ABC):
    """Answers questions about one bank. Subclasses decide how the answer is written."""

    name = "Assistant"
    ID_RE = re.compile(r"\b(?:[A-Z]{2,5}-){1,2}\d{3}\b|\b(?:[A-Z]{2,4}-[A-Z]{2,8}|[A-Z]{2,4}-\d{2}|WCF|FTD-6M)\b")

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

    @abstractmethod
    def answer(self, question, facts):
        """Write the reply (a Reply) from the question and the facts found."""

    # ------------------------------------------------------------------ retrieval
    def find_records(self, question):
        """Every record the question names, by reference number or by name."""
        bank, found = self.bank, []
        registries = (bank.transactions, bank.arrangements, bank.cards, bank.cases, bank.beneficiaries,
                      bank.products, bank.branches, bank.employees)
        for ref in self.ID_RE.findall(question.upper()):
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
    AMOUNT = r"(?:pkr|rs\.?)?\s*([\d][\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lac|m|million)?"
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
        try:
            value = Decimal(number.replace(",", ""))
        except InvalidOperation:
            return None
        return value * self.SCALE.get((scale or "").lower(), 1)

    def parse_action(self, question):
        """Turn a request into a pre-filled form, or None."""
        low = question.lower()
        m = re.search(r"\b(deposit|withdraw)\s+" + self.AMOUNT + r"\s+(?:into|in|to|from)\s+([a-z]{3}-\d{3})", low)
        if m:
            value = self.amount(m.group(2), m.group(3))
            if value is not None:
                op = "Deposit cash" if m.group(1) == "deposit" else "Withdraw cash"
                return FormAction(op, {"Account": m.group(4).upper(), "Amount": _plain(value)})
        m = re.search(r"\b(?:report|block)\b.*?\b(card-\d{3})\b.*?\b(lost|stolen|damaged)\b", low) or \
            re.search(r"\b(?:report|block)\b.*?\b(lost|stolen|damaged)\b.*?\b(card-\d{3})\b", low)
        if m:
            card, kind = sorted(m.groups(), key=lambda g: not g.startswith("card"))
            values = {"Card": card.upper(), "Report": kind.upper()}
            holder = self.bank.cards.get(card.upper())
            if holder is not None:
                values["Reported by"] = holder.cardholder.name
            return FormAction("Report a card", values)
        m = re.search(r"\bdispute\b.*?\b(crd-tx-\d{3})\b", low)
        if m:
            txn = self.bank.transactions.get(m.group(1).upper())
            values = {"Payment": m.group(1).upper()}
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
                    data = json.loads(line.split("ACTION:", 1)[1])
                    action = FormAction(data["operation"], data.get("values", {}))
                except (ValueError, KeyError, TypeError):
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
    with contextlib.redirect_stdout(io.StringIO()):
        return bs.run_demo()


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


class AssistantTests(unittest.TestCase):
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
        result = unittest.main(argv=[sys.argv[0]], exit=False, verbosity=1).result
        return 0 if result.wasSuccessful() else 1
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
