#!/usr/bin/env python3
"""
banking_system.py
=================
Problem 4 - Commercial Banking, Lending, Payments and Compliance
(OOP project: assessed concepts are CLASSES and INHERITANCE)

A single, self-contained Python file (standard library only, Python 3.9+)
that contains:

    PART 1  helpers and business-rule errors
    PART 2  time and history building blocks (Period, StatusHistory, audit)
    PART 3  parties, KYC, roles and mandates      Party -> Organization -> Company
    PART 4  bank organisation and staff           Branch, Employee, Approval
    PART 5  products and customer arrangements    Arrangement -> DepositAccount -> Current/Savings/FixedTerm
    PART 6  financing (loans)                     FinancingAgreement, schedules, installments
    PART 7  beneficiaries, standing orders and billers
    PART 8  transactions (double-entry)           BankTransaction -> CustomerPayment -> Transfer/Card/Bill
    PART 9  cards                                 IssuedCard replacement chain, CardControl
    PART 10 cases                                 Case -> RiskCase -> ComplianceInvestigation
    PART 11 statements and notices
    PART 12 Bank: the application service (every operation, rule and audit event)
    PART 13 seeded demonstration: 16 complex scenarios on a simulated calendar
    PART 14 automated tests (unittest)
    PART 15 class and UML diagram generators (SVG, read from the live classes)
    PART 16 command line

How to run
----------
    python banking_system.py              # run the seeded demonstration
    python banking_system.py --test       # run the automated tests
    python banking_system.py --classes    # print the inheritance tree and counts
    python banking_system.py --diagram DIR  # write the class and UML diagrams (SVG) into DIR

Core design rule
----------------
Nothing that has happened is ever deleted or overwritten. Change is recorded
as NEW data: status transitions, closed validity periods, new versions (terms,
beneficiaries, repayment schedules), reversals and corrections. Any past state
can therefore be reconstructed ("what did the bank know / allow on date X?").

Abstraction and lifecycles
--------------------------
The root of every hierarchy (Party, Arrangement, BankTransaction, Case) is an
abstract base class: it cannot be instantiated, and each concrete subclass
must implement its abstract methods (e.g. BankTransaction.counterparty).
Behaviour that differs by class lives in the class (polymorphism), not in
isinstance chains in the Bank. Every record with a status declares its state
machine once, as a LIFECYCLE class constant (a Lifecycle); StatusHistory
refuses any move it does not allow, and subclasses extend their parent's.

Money convention
----------------
Every posting is double-entry: the legs of one transaction sum to zero.
Amounts are signed from the bank's books: positive = credit, negative = debit.
A customer's deposit balance is therefore positive (the bank owes it), while
the bank's vault cash and loans receivable are negative (debit) balances
because they are assets. The trial balance of the whole bank is always zero.
All amounts are Pakistani rupees (PKR) held as Decimal, never float.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from abc import ABC, abstractmethod
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

# =============================================================================
# PART 1 - Helpers and business-rule errors
# =============================================================================
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    """Convert a number or string to a Decimal rounded to paisa (2 places)."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt(amount) -> str:
    """Format an amount for display, e.g. PKR 1,500,000.00."""
    return f"PKR {amount:,.2f}"


def add_months(d: date, n: int) -> date:
    """Add n calendar months. The day is capped at 28 so it exists in every month."""
    idx = d.month - 1 + n
    return date(d.year + idx // 12, idx % 12 + 1, min(d.day, 28))


_counters: dict = {}


def next_id(prefix: str) -> str:
    """Return the next readable business reference for a prefix, e.g. TRF-007."""
    _counters[prefix] = _counters.get(prefix, 0) + 1
    return f"{prefix}-{_counters[prefix]:03d}"


def reset_ids() -> None:
    """Restart every reference counter (used so each demo run is reproducible)."""
    _counters.clear()


# A small, genuine hierarchy: every one of these IS a BankingError, so callers
# can catch the general case while the demo and tests can name the exact rule.
class BankingError(Exception):
    """Base class for every business-rule violation raised by the model."""


class KycIncomplete(BankingError):
    """A party, or a person connected to it, is not verified on the date asked."""


class AuthorityError(BankingError):
    """The person or employee does not hold the authority the action needs."""


class RestrictionViolation(BankingError):
    """A compliance restriction or a blocked card stops the action."""


class ProductNotAvailable(BankingError):
    """The product is not sold (any more), or is the wrong kind for the request."""


class InsufficientFunds(BankingError):
    """Available balance (ledger - holds + overdraft) is below the amount."""


class InvalidStateError(BankingError):
    """The record's current status does not allow the requested change."""


# =============================================================================
# PART 2 - Time and history building blocks (used by COMPOSITION, not inheritance)
# =============================================================================
class Period:
    """A half-open validity window [start, end). end=None means still in force.

    Used for every fact that is true only for a while: mandates, officer roles,
    ownership, restrictions, branch and relationship-manager assignments.
    Closing a period ends the fact without erasing that it was once true.
    """

    def __init__(self, start: date, end: date | None = None):
        self.start, self.end = start, end

    def contains(self, on: date) -> bool:
        """True if the fact was in force on the given date."""
        return self.start <= on and (self.end is None or on < self.end)

    def close(self, on: date):
        """End the period on a date. A period can only be closed once."""
        if self.end is not None:
            raise InvalidStateError(f"period already closed on {self.end}")
        if on < self.start:
            raise InvalidStateError(f"cannot close a period before it started ({self.start})")
        self.end = on

    def __str__(self):
        return f"{self.start} -> {self.end or 'open'}"


class StatusChange:
    """One entry in a status history: what the status became, when, by whom, why."""

    def __init__(self, status, on, by, reason):
        self.status, self.on, self.by, self.reason = status, on, str(by), reason


class Lifecycle:
    """A state machine: the statuses one kind of record can be in and the moves allowed
    between them, each labelled with the operation that causes it.

    Declared ONCE per class as the LIFECYCLE class constant and enforced by
    StatusHistory, so an illegal move (e.g. a DESTROYED card becoming ACTIVE) is
    impossible from anywhere in the code. Subclasses extend() their parent's
    lifecycle, so the state machines are inherited just like attributes, and the
    UML state diagrams are drawn from these declarations.
    """

    def __init__(self, initial, transitions, final=()):
        self.initial = initial
        self.transitions = {frm: dict(moves) for frm, moves in transitions.items()}
        self.final = frozenset(final)

    def allows(self, frm, to):
        return to in self.transitions.get(frm, {})

    def extend(self, transitions, final=()):
        """A new lifecycle with extra moves (and final statuses) added to this one."""
        merged = {frm: dict(moves) for frm, moves in self.transitions.items()}
        for frm, moves in transitions.items():
            merged.setdefault(frm, {}).update(moves)
        return Lifecycle(self.initial, merged, self.final | set(final))

    @property
    def states(self):
        """Every status, in the order it first appears (initial first)."""
        out = [self.initial]
        for frm, moves in self.transitions.items():
            for st in [frm, *moves]:
                if st not in out:
                    out.append(st)
        return out


class StatusHistory:
    """Keeps every status a record has ever had, so 'status on date X' is answerable.
    With a Lifecycle it also refuses any move the record's class does not allow."""

    def __init__(self, initial, on, by="system", reason="", lifecycle=None):
        if lifecycle is not None and initial != lifecycle.initial:
            raise InvalidStateError(f"a new record starts as {lifecycle.initial}, not {initial}")
        self.lifecycle = lifecycle
        self.changes = [StatusChange(initial, on, by, reason)]

    @property
    def current(self):
        """The latest status."""
        return self.changes[-1].status

    def change(self, status, on, by="system", reason="", allowed_from=None):
        """Append a new status. allowed_from lists the statuses it may move from."""
        if allowed_from and self.current not in allowed_from:
            raise InvalidStateError(f"cannot move from {self.current} to {status}")
        if self.lifecycle is not None and not self.lifecycle.allows(self.current, status):
            raise InvalidStateError(f"{self.current} -> {status} is not an allowed transition")
        self.changes.append(StatusChange(status, on, by, reason))

    def on(self, d):
        """The status that applied on a past date (None if the record did not exist)."""
        result = None
        for c in self.changes:
            if c.on <= d:
                result = c.status
        return result

    def trail(self):
        """Readable history, e.g. ACTIVE(2026-01-06) > CLOSED(2027-02-01)."""
        return " > ".join(f"{c.status}({c.on})" for c in self.changes)


class AuditEvent:
    """One line of the bank's append-only audit log (who did what, to what, when)."""

    def __init__(self, on, actor, action, subject, detail):
        self.on, self.actor, self.action, self.subject, self.detail = on, actor, action, subject, detail


# =============================================================================
# PART 3 - Parties, KYC, roles and mandates
#   Party -> Person
#   Party -> Organization -> Company / Charity                (multi-level)
# "Customer", "signatory", "director", "owner" and "employee" are ROLES a party
# plays (separate objects with periods), never subclasses. One real person is
# exactly one Person record, however many capacities they hold.
# =============================================================================
class Party(ABC):
    """Anyone the bank knows about: a legal identity, whether or not a customer.

    Holds what every party shares: identity documents, verification checks,
    corrections to recorded details, restrictions, and (optionally) a customer
    relationship. Recorded details are corrected, never silently overwritten.

    Abstract: nobody is "just a party". kyc_gaps() is a template method; every
    concrete class must say what its own structure requires (structural_gaps)
    and whose identity it depends on (connected_persons).
    """

    id_prefix = "PTY"

    def __init__(self, name, registered_on):
        self.party_id = next_id(self.id_prefix)
        self._details = {"name": name}
        self.registered_on = registered_on
        self.documents: list[IdentityDocument] = []
        self.checks: list[VerificationCheck] = []
        self.corrections: list[Correction] = []
        self.restrictions: list[Restriction] = []
        self.relationship: CustomerRelationship | None = None

    @property
    def name(self):
        return self._details["name"]

    def detail(self, key):
        """The current value of a recorded detail (e.g. registered_address)."""
        return self._details.get(key)

    def record_detail(self, key, value):
        """Record a detail for the first time (not a correction)."""
        self._details[key] = value

    def correct_detail(self, key, value, on, by, reason):
        """Correct a detail. The old value is kept in a Correction record."""
        c = Correction(self, key, self._details.get(key), value, on, by, reason)
        self._details[key] = value
        self.corrections.append(c)
        return c

    def detail_on(self, key, on):
        """What the bank held for this detail on a past date."""
        value = self._details.get(key)
        for c in reversed(self.corrections):          # undo later corrections, newest first
            if c.field == key and c.on > on:
                value = c.old_value
        return value

    def is_verified(self, on):
        """True if a passing check exists against a document that is valid on that date."""
        return any(c.result == "PASS" and c.performed_on <= on and c.document.valid_on(on)
                   for c in self.checks)

    @abstractmethod
    def structural_gaps(self, on):
        """Rules about the party's own make-up (e.g. a company needs a director)."""

    @abstractmethod
    def connected_persons(self, on):
        """People whose verification this party's verification depends on."""

    def kyc_gaps(self, on):
        """Template method: every reason this party cannot be onboarded on a date
        (empty = ok). Own verification, then the subclass's structural rules, then
        each connected person's own gaps."""
        gaps = [] if self.is_verified(on) else [
            f"{self.name}: no passing check against a document valid on {on}"]
        gaps += self.structural_gaps(on)
        for person in self.connected_persons(on):
            gaps += person.kyc_gaps(on)
        return gaps

    def __str__(self):
        return f"{self.name} [{self.party_id}]"


class Person(Party):
    """A natural person. May be a customer, director, owner, signatory and employee at once."""

    id_prefix = "PER"

    def __init__(self, name, registered_on, date_of_birth):
        super().__init__(name, registered_on)
        self.date_of_birth = date_of_birth

    def structural_gaps(self, on):
        return []                       # a person has no governance structure

    def connected_persons(self, on):
        return []                       # a person answers only for themselves


class Organization(Party):
    """A non-human legal identity controlled by people through roles.

    Adds officers, beneficial owners and mandates, and extends KYC: the
    organisation is only verified if its connected persons (active officers
    and owners at or above the threshold) are verified too.

    Still abstract: structural_gaps() is left to Company and Charity, whose
    governance rules differ.
    """

    id_prefix = "ORG"
    officer_title = "OFFICER"
    OWNERSHIP_THRESHOLD = Decimal("25")      # assumption A2: FATF-style 25% threshold

    def __init__(self, name, registered_on, registration_no, address):
        super().__init__(name, registered_on)
        self.registration_no = registration_no
        self.record_detail("registered_address", address)
        self.officers: list[OfficerRole] = []
        self.owners: list[BeneficialOwnership] = []
        self.mandates: list[Mandate] = []

    def connected_persons(self, on):
        """Active officers plus owners at/above the threshold, each listed once."""
        people = [r.person for r in self.officers if r.period.contains(on)]
        people += [o.person for o in self.owners
                   if o.period.contains(on) and o.percent >= self.OWNERSHIP_THRESHOLD]
        unique = []
        for p in people:
            if p not in unique:
                unique.append(p)
        return unique

    def find_mandate(self, person, capability, amount, on):
        """Return the mandate that lets a person do something on a date, or raise."""
        candidates = [m for m in self.mandates if m.person is person
                      and m.period.contains(on) and capability in m.capabilities]
        if not candidates:
            raise AuthorityError(f"{person.name} holds no active '{capability}' mandate "
                                 f"for {self.name} on {on}")
        for m in candidates:
            if m.limit is None or amount <= m.limit:
                return m
        raise AuthorityError(f"{person.name}'s '{capability}' mandate limit is below {fmt(amount)}")


class Company(Organization):
    """A limited company: governed by directors; needs at least one active director."""

    officer_title = "DIRECTOR"

    def __init__(self, name, registered_on, registration_no, address, incorporated_on):
        super().__init__(name, registered_on, registration_no, address)
        self.incorporated_on = incorporated_on

    def structural_gaps(self, on):
        if not any(r.period.contains(on) for r in self.officers):
            return [f"{self.name}: no active director"]
        return []


class Charity(Organization):
    """A charity or trust: governed by trustees; needs at least two (assumption A4)."""

    officer_title = "TRUSTEE"
    MIN_TRUSTEES = 2

    def structural_gaps(self, on):
        active = sum(1 for r in self.officers if r.period.contains(on))
        if active < self.MIN_TRUSTEES:
            return [f"{self.name}: needs {self.MIN_TRUSTEES} trustees, has {active}"]
        return []


class IdentityDocument:
    """An identity or registration document (CNIC, passport, incorporation certificate)."""

    def __init__(self, party, doc_type, number, issued_on, expires_on=None):
        self.document_id = next_id("DOC")
        self.party, self.doc_type, self.number = party, doc_type, number
        self.issued_on, self.expires_on = issued_on, expires_on

    def valid_on(self, on):
        """True if the document had been issued and had not expired on that date."""
        return self.issued_on <= on and (self.expires_on is None or on <= self.expires_on)

    def __str__(self):
        return f"{self.doc_type} {self.number} (expires {self.expires_on or 'never'})"


class VerificationCheck:
    """One KYC check of a party against one document, by one employee, on one date."""

    def __init__(self, party, document, performed_on, performed_by, result, note=""):
        self.check_id = next_id("CHK")
        self.party, self.document = party, document
        self.performed_on, self.performed_by = performed_on, performed_by
        self.result, self.note = result, note


class Correction:
    """Keeps the value a detail had before it was corrected, with who and why."""

    def __init__(self, party, field, old_value, new_value, on, by, reason):
        self.party, self.field = party, field
        self.old_value, self.new_value = old_value, new_value
        self.on, self.by, self.reason = on, str(by), reason


class OfficerRole:
    """A person's office in an organisation (director / trustee) for a period."""

    def __init__(self, organization, person, title, start):
        self.organization, self.person, self.title = organization, person, title
        self.period = Period(start)
        self.end_reason = None


class BeneficialOwnership:
    """A person's ownership share of an organisation for a period."""

    def __init__(self, organization, person, percent, start):
        percent = Decimal(str(percent))
        if not ZERO < percent <= 100:
            raise BankingError(f"ownership percentage {percent} out of range")
        self.organization, self.person = organization, person
        self.percent = percent
        self.period = Period(start)


class Mandate:
    """Time-bounded banking authority a person holds on behalf of an organisation.

    Capabilities are PAYMENTS, BORROWING, CARD and VIEW. A limit of None means
    unlimited. dual_control_above makes larger payments need a second signatory.
    Revoking closes the period, so past payments still show valid authority.
    """

    CAPABILITIES = {"PAYMENTS", "BORROWING", "CARD", "VIEW"}

    def __init__(self, organization, person, capabilities, limit, start, granted_by,
                 dual_control_above=None):
        unknown = set(capabilities) - self.CAPABILITIES
        if unknown:
            raise BankingError(f"unknown mandate capability {sorted(unknown)}")
        self.mandate_id = next_id("MND")
        self.organization, self.person = organization, person
        self.capabilities = frozenset(capabilities)
        self.limit = money(limit) if limit is not None else None
        self.period = Period(start)
        self.granted_by = str(granted_by)
        self.revocation_reason = None
        self.dual_control_above = money(dual_control_above) if dual_control_above is not None else None

    def needs_second_signatory(self, amount):
        """True if a payment of this amount needs dual control under this mandate."""
        return self.dual_control_above is not None and amount > self.dual_control_above

    def revoke(self, on, reason):
        """End the mandate. The record and its period stay for history."""
        self.period.close(on)
        self.revocation_reason = reason

    def __str__(self):
        lim = fmt(self.limit) if self.limit is not None else "unlimited"
        dual = f", 2nd signatory above {fmt(self.dual_control_above)}" if self.dual_control_above else ""
        return (f"{self.mandate_id} {self.person.name} for {self.organization.name}: "
                f"{','.join(sorted(self.capabilities))} up to {lim}{dual}, valid {self.period}")


class PaymentAuthorisation:
    """A second signatory's approval of a customer payment (dual control)."""

    def __init__(self, transaction, person, mandate, on):
        self.transaction, self.person, self.mandate, self.on = transaction, person, mandate, on

    def __str__(self):
        return f"authorised by {self.person.name} under {self.mandate.mandate_id} on {self.on}"


class CustomerRelationship:
    """Being a customer is a relationship a Party has with the bank, not a subclass.

    Keeps the home-branch history and the relationship-manager history as
    periods, so a branch closure or an RM change never rewrites the past.
    """

    LIFECYCLE = Lifecycle("ACTIVE", {"ACTIVE": {"ENDED": "end_relationship"}}, final={"ENDED"})

    def __init__(self, party, since, home_branch, segment, relationship_manager=None):
        self.party, self.since, self.segment = party, since, segment
        self.branch_history = [(Period(since), home_branch)]
        self.rm_history = []                     # [(Period, Employee)]
        self.status = StatusHistory("ACTIVE", since, "system", "onboarded", lifecycle=self.LIFECYCLE)
        self.archived_on = None                  # set when moved to the retention archive
        if relationship_manager:
            self.set_manager(relationship_manager, since)

    def set_manager(self, employee, on):
        """Hand the customer to a new relationship manager from a date."""
        if self.rm_history and self.rm_history[-1][0].end is None:
            self.rm_history[-1][0].close(on)
        self.rm_history.append((Period(on), employee))

    def manager_on(self, d):
        for period, emp in self.rm_history:
            if period.contains(d):
                return emp
        return None

    def home_branch_on(self, d):
        for period, branch in self.branch_history:
            if period.contains(d):
                return branch
        return None

    def move(self, branch, on):
        """Move the customer's home branch from a date (e.g. branch closure)."""
        self.branch_history[-1][0].close(on)
        self.branch_history.append((Period(on), branch))


# =============================================================================
# PART 4 - Bank organisation and staff
# =============================================================================
class Branch:
    """A branch of the bank. Closed branches are kept, with a pointer to their successor."""

    LIFECYCLE = Lifecycle("OPEN", {"OPEN": {"CLOSED": "close_branch"}}, final={"CLOSED"})

    def __init__(self, code, name, city, opened_on):
        self.code, self.name, self.city = code, name, city
        self.status = StatusHistory("OPEN", opened_on, lifecycle=self.LIFECYCLE)
        self.merged_into = None
        self.vault = None                        # GeneralLedgerAccount, set by Bank.open_branch

    @property
    def is_open(self):
        return self.status.current == "OPEN"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Employee:
    """An employment record. It points to a Person, so an employee may also be a customer.

    The job role is NOT a subclass: roles change over time and are kept as
    RoleAssignment periods, so an old approval still shows the role held then.
    """

    LIFECYCLE = Lifecycle("EMPLOYED", {"EMPLOYED": {"LEFT": "record_employee_exit"}}, final={"LEFT"})

    def __init__(self, person, hired_on):
        self.employee_no = next_id("EMP")
        self.person, self.hired_on = person, hired_on
        self.assignments: list[RoleAssignment] = []
        self.status = StatusHistory("EMPLOYED", hired_on, lifecycle=self.LIFECYCLE)

    def current_assignment(self):
        for a in reversed(self.assignments):
            if a.period.end is None:
                return a
        return None

    def assign(self, role, branch, on):
        """Start a new role/branch assignment, closing the current one."""
        current = self.current_assignment()
        if current:
            current.period.close(on)
        a = RoleAssignment(self, role, branch, on)
        self.assignments.append(a)
        return a

    def role_on(self, d):
        """The assignment (role and branch) that applied on a date, or None."""
        for a in self.assignments:
            if a.period.contains(d):
                return a
        return None

    def __str__(self):
        return self.person.name


class RoleAssignment:
    """An employee holding one role at one branch for a period."""

    def __init__(self, employee, role, branch, start):
        self.employee, self.role, self.branch = employee, role, branch
        self.period = Period(start)


class Approval:
    """Freezes WHO decided and in WHAT capacity at the moment of decision.

    Copying the role and branch (rather than pointing at the employee's
    current role) is what keeps old credit decisions and reversals truthful
    after the employee is promoted, moved or leaves.
    """

    def __init__(self, approver, decided_on, decision, subject, notes=""):
        assignment = approver.role_on(decided_on)
        if assignment is None:
            raise AuthorityError(f"{approver} had no role on {decided_on}")
        self.approval_id = next_id("APR")
        self.approver, self.decided_on = approver, decided_on
        self.decision, self.subject, self.notes = decision, subject, notes
        self.role_at_time = assignment.role
        self.branch_at_time = assignment.branch.code

    def __str__(self):
        return (f"{self.approval_id}: {self.decision} by {self.approver} acting as "
                f"{self.role_at_time} @ {self.branch_at_time} on {self.decided_on}")


# =============================================================================
# PART 5 - Products and customer arrangements
#   ProductDefinition = what the bank SELLS (with versioned terms)
#   Arrangement       = a customer's ACTUAL instance of a product
#   Arrangement -> DepositAccount -> CurrentAccount / SavingsAccount   (multi-level)
#   Arrangement -> FinancingAgreement
# =============================================================================
class ProductDefinition:
    """A product the bank offers. Terms are versioned; sale status has a history."""

    CATEGORIES = {"CURRENT", "SAVINGS", "TERM_DEPOSIT", "FINANCING", "DEBIT_CARD"}

    SALE_LIFECYCLE = Lifecycle("ON_SALE", {"ON_SALE": {"CLOSED_TO_NEW": "withdraw_from_sale"}}, final={"CLOSED_TO_NEW"})

    def __init__(self, code, name, category, launched_on):
        if category not in self.CATEGORIES:
            raise BankingError(f"unknown product category {category}")
        self.code, self.name, self.category = code, name, category
        self.terms_versions: list[ProductTermsVersion] = []
        self.sale_status = StatusHistory("ON_SALE", launched_on, lifecycle=self.SALE_LIFECYCLE)

    def add_terms(self, effective_from, **terms):
        """Publish a new terms version (older versions are kept)."""
        v = ProductTermsVersion(self, len(self.terms_versions) + 1, effective_from, terms)
        self.terms_versions.append(v)
        return v

    def terms_on(self, d):
        """The newest terms version already effective on a date."""
        valid = [v for v in self.terms_versions if v.effective_from <= d]
        return max(valid, key=lambda v: (v.effective_from, v.version_no)) if valid else None

    def can_sell(self, on):
        """True if the product may be sold to a NEW customer on that date."""
        return self.sale_status.on(on) == "ON_SALE"


class ProductTermsVersion:
    """One immutable version of a product's terms (fees, rates, limits)."""

    def __init__(self, product, version_no, effective_from, terms):
        self.product, self.version_no = product, version_no
        self.effective_from, self.terms = effective_from, dict(terms)

    def get(self, key, default=0):
        return self.terms.get(key, default)

    def __str__(self):
        return f"{self.product.code} v{self.version_no} (from {self.effective_from}) {self.terms}"


class Arrangement(ABC):
    """A customer's actual instance of a product (an account or a financing agreement).

    Shared by every arrangement: the product, the terms version PINNED at
    opening (old customers do not silently inherit new terms), the holders,
    the branch it was opened at (fixed) and the servicing branch (can change),
    a status history, and restrictions.

    Abstract: every concrete arrangement must say what its headline position
    is (position()): money the bank holds for the customer, or money owed.
    """

    prefix = "ARR"
    PRODUCT_CATEGORY = None
    USABLE_STATUSES = {"ACTIVE"}

    LIFECYCLE = Lifecycle("ACTIVE", {"ACTIVE": {"CLOSED": "close_account / maturity payout"}}, final={"CLOSED"})

    def __init__(self, product, holders, opened_on, branch, opened_by, terms_date=None):
        terms_date = terms_date or opened_on
        if product.category != self.PRODUCT_CATEGORY:
            raise ProductNotAvailable(f"{product.name} cannot be opened as {type(self).__name__}")
        if not product.can_sell(terms_date):
            raise ProductNotAvailable(f"{product.name} is not sold to new customers since "
                                      f"{product.sale_status.changes[-1].on}")
        self.number = next_id(self.prefix)
        self.product = product
        self.terms = product.terms_on(terms_date)              # pinned at opening
        self.terms_history = [(opened_on, self.terms)]
        self.holders = list(holders)
        self.opened_on = opened_on
        self.opened_at_branch = branch                          # never changes
        self.servicing_history = [(Period(opened_on), branch)]  # can change
        self.status = StatusHistory("ACTIVE", opened_on, opened_by, "opened", lifecycle=self.LIFECYCLE)
        self.restrictions: list[Restriction] = []
        self.archived_on = None                  # set when moved to the retention archive

    def terms_on(self, d):
        """The terms version this arrangement was on for a past date."""
        result = None
        for start, version in self.terms_history:
            if start <= d:
                result = version
        return result

    def migrate_terms(self, version, on):
        """Move to a newer terms version from a date (history keeps the old one)."""
        self.terms = version
        self.terms_history.append((on, version))

    def servicing_branch_on(self, d):
        for period, branch in self.servicing_history:
            if period.contains(d):
                return branch
        return None

    def move_servicing(self, branch, on):
        self.servicing_history[-1][0].close(on)
        self.servicing_history.append((Period(on), branch))

    def ensure_usable(self, direction, on):
        """Raise if the arrangement is not active or a restriction blocks this direction."""
        if self.status.current not in self.USABLE_STATUSES:
            raise InvalidStateError(f"{self.number} is {self.status.current}")
        for r in self.restrictions + [r for h in self.holders for r in h.restrictions]:
            if r.blocks(direction, on):
                raise RestrictionViolation(f"{r.scope} on {r.target_label} since "
                                           f"{r.period.start}: {r.reason}")

    @abstractmethod
    def position(self, on=None):
        """The headline figure as (amount, meaning), e.g. (Decimal('500.00'), 'held')."""

    def __str__(self):
        return f"{self.number} {self.product.name} ({', '.join(h.name for h in self.holders)})"


class DepositAccount(Arrangement):
    """An account holding customer money. Balances are DERIVED from ledger entries.

    Adds the ledger, holds, available balance and the debit check. Abstract: a
    deposit is always a current, savings or term account, and each must state
    its own overdraft policy (overdraft_limit).
    """

    prefix = "DEP"

    def __init__(self, product, holders, opened_on, branch, opened_by):
        super().__init__(product, holders, opened_on, branch, opened_by)
        self.entries: list[LedgerEntry] = []
        self.holds: list[AccountHold] = []

    def ledger_balance(self, on=None):
        """Sum of posted entries (optionally up to and including a date)."""
        return sum((e.amount for e in self.entries if on is None or e.posted_on <= on), ZERO)

    def held_amount(self, on):
        return sum((h.amount for h in self.holds if h.active_on(on)), ZERO)

    @abstractmethod
    def overdraft_limit(self):
        """How far below zero this account may go."""

    def position(self, on=None):
        return self.ledger_balance(on), "held"

    def available_balance(self, on):
        """Ledger balance minus active holds plus any overdraft limit."""
        return self.ledger_balance(on) - self.held_amount(on) + self.overdraft_limit()

    def check_debit(self, amount, on):
        """Raise if this account cannot be debited by the amount today."""
        self.ensure_usable("DEBIT", on)
        if amount > self.available_balance(on):
            raise InsufficientFunds(f"{self.number}: available {fmt(self.available_balance(on))}, "
                                    f"requested {fmt(amount)}")


class CurrentAccount(DepositAccount):
    """Transaction account: unlimited movements; may have an overdraft from its terms."""

    prefix = "CUR"
    PRODUCT_CATEGORY = "CURRENT"

    def overdraft_limit(self):
        return money(self.terms.get("overdraft_limit", 0))


class SavingsAccount(DepositAccount):
    """Interest-bearing account with a monthly limit on customer withdrawals."""

    prefix = "SAV"
    PRODUCT_CATEGORY = "SAVINGS"

    def overdraft_limit(self):
        return ZERO                     # savings never go overdrawn

    def withdrawals_in_month(self, on):
        """Count CUSTOMER-initiated debits this month. Bank fees and reversals do not
        use up the customer's withdrawal allowance."""
        return sum(1 for e in self.entries if e.amount < 0
                   and isinstance(e.transaction, (CashTransaction, CustomerPayment))
                   and e.posted_on.year == on.year and e.posted_on.month == on.month)

    def check_debit(self, amount, on):
        limit = self.terms.get("max_monthly_withdrawals", 99)
        if self.withdrawals_in_month(on) >= limit:
            raise BankingError(f"{self.number}: savings withdrawal limit of {limit}/month reached")
        super().check_debit(amount, on)


class FixedTermDeposit(DepositAccount):
    """Money placed for a fixed term at a fixed rate (the closest thing to an investment
    product in this model). No withdrawals before maturity: the deposit is either paid
    out at maturity with interest, or broken early with interest forfeited and a penalty.
    """

    prefix = "FTD"
    PRODUCT_CATEGORY = "TERM_DEPOSIT"

    def __init__(self, product, holders, opened_on, branch, opened_by):
        super().__init__(product, holders, opened_on, branch, opened_by)
        self.term_months = int(self.terms.get("term_months", 12))
        self.annual_rate = Decimal(str(self.terms.get("annual_rate", 0)))
        self.maturity_on = add_months(opened_on, self.term_months)
        self.payout_account: DepositAccount | None = None

    def overdraft_limit(self):
        return ZERO                     # the money is locked in, never overdrawn

    def principal(self):
        """The amount placed (the balance before any maturity payout)."""
        return self.ledger_balance()

    def maturity_interest(self):
        """Simple interest for the whole term on the amount placed."""
        return money(self.principal() * self.annual_rate * self.term_months / 12)

    def ensure_usable(self, direction, on):
        super().ensure_usable(direction, on)
        if direction == "CREDIT" and self.entries:
            raise BankingError(f"{self.number} is funded once, at placement")

    def check_debit(self, amount, on):
        if on < self.maturity_on:
            raise BankingError(f"{self.number} is fixed until {self.maturity_on}; "
                               f"break the deposit instead of withdrawing")
        super().check_debit(amount, on)


class LedgerEntry:
    """One immutable posting to one account. Balances are always derived from these."""

    def __init__(self, account, amount, posted_on, transaction):
        self.account, self.amount = account, amount
        self.posted_on, self.transaction = posted_on, transaction


class GeneralLedgerAccount:
    """The bank's OWN books (vault cash, clearing, income, receivables).

    Deliberately not an Arrangement: nobody holds it, it has no product,
    terms or restrictions. It only shares the idea of a ledger balance.
    """

    TYPES = {"ASSET", "LIABILITY", "INCOME", "EXPENSE"}

    def __init__(self, code, name, gl_type):
        if gl_type not in self.TYPES:
            raise BankingError(f"unknown GL type {gl_type}")
        self.number, self.name, self.gl_type = code, name, gl_type
        self.entries: list[LedgerEntry] = []

    def ledger_balance(self, on=None):
        return sum((e.amount for e in self.entries if on is None or e.posted_on <= on), ZERO)

    def __str__(self):
        return f"{self.number} {self.name}"


class AccountHold:
    """Funds reserved on an account without being posted (reduces available balance)."""

    def __init__(self, account, amount, reason, placed_on, source):
        self.account, self.amount, self.reason = account, money(amount), reason
        self.placed_on, self.source = placed_on, source
        self.released_on = None

    def active_on(self, d):
        return self.placed_on <= d and (self.released_on is None or d < self.released_on)

    def release(self, on):
        if self.released_on is not None:
            raise InvalidStateError("hold already released")
        self.released_on = on


class Restriction:
    """A compliance restriction on a party or an arrangement, for a period.

    Lifting closes the period; the record stays, so "was this customer
    restricted on 11 April?" is always answerable.
    """

    SCOPES = {"DEBIT_BLOCK": {"DEBIT"}, "FULL_FREEZE": {"DEBIT", "CREDIT"}}

    def __init__(self, target, scope, reason, imposed_on, imposed_by, case=None):
        if scope not in self.SCOPES:
            raise BankingError(f"unknown restriction scope {scope}")
        self.restriction_id = next_id("RST")
        self.target, self.scope, self.reason = target, scope, reason
        self.target_label = getattr(target, "name", None) or getattr(target, "number", "?")
        self.period = Period(imposed_on)
        self.imposed_by, self.case = str(imposed_by), case
        self.lifted_by = self.lift_reason = None

    def blocks(self, direction, on):
        """True if this restriction stopped DEBIT/CREDIT movements on a date."""
        return self.period.contains(on) and direction in self.SCOPES[self.scope]

    def lift(self, on, by, reason):
        self.period.close(on)
        self.lifted_by, self.lift_reason = str(by), reason


# =============================================================================
# PART 6 - Financing
# =============================================================================
class FinancingAgreement(Arrangement):
    """A working-capital or term financing agreement created from an approved application.

    Adds the principal, the settlement account, VERSIONED repayment schedules
    (a restructure supersedes the schedule rather than editing installments),
    allocation of repayments and the settlement quote.
    """

    prefix = "FIN"
    PRODUCT_CATEGORY = "FINANCING"
    USABLE_STATUSES = {"ACTIVE", "IN_ARREARS"}

    LIFECYCLE = Lifecycle("ACTIVE", {                # replaces Arrangement's
        "ACTIVE": {"IN_ARREARS": "arrears batch: installment overdue", "SETTLED": "settle_financing"},
        "IN_ARREARS": {"ACTIVE": "arrears cleared / restructure_financing", "SETTLED": "settle_financing"},
    }, final={"SETTLED"})

    def __init__(self, application, opened_on, branch, opened_by, settlement_account):
        super().__init__(application.product, [application.applicant], opened_on, branch,
                         opened_by, terms_date=application.submitted_on)
        self.application = application
        self.principal = application.approved_amount
        self.settlement_account = settlement_account
        self.schedules: list[RepaymentSchedule] = []
        self.transactions: list[LoanTransaction] = []
        self.restructure_approvals: list[Approval] = []

    @property
    def current_schedule(self):
        return self.schedules[-1]

    def outstanding_principal(self):
        return sum((i.principal - i.principal_paid for i in self.current_schedule.installments), ZERO)

    def position(self, on=None):
        return self.outstanding_principal(), "owed"

    def outstanding_total(self):
        """Everything still payable on the current schedule (principal + interest)."""
        return sum((i.outstanding for i in self.current_schedule.installments), ZERO)

    def overdue_installments(self, on):
        return [i for i in self.current_schedule.installments if i.status_on(on) == "OVERDUE"]

    def overdue_interest(self, on):
        return sum((i.interest - i.interest_paid - i.interest_waived
                    for i in self.overdue_installments(on)), ZERO)

    def build_schedule(self, principal, annual_rate, months, first_due, created_on, reason,
                       capitalised_interest=ZERO):
        """Create a new schedule version (equal principal, interest on the balance).
        Any active schedule is SUPERSEDED, never edited."""
        if months < 1:
            raise BankingError("a schedule needs at least one installment")
        for s in self.schedules:
            if s.status.current == "ACTIVE":
                s.status.change("SUPERSEDED", created_on, "system", reason)
        sched = RepaymentSchedule(self, len(self.schedules) + 1, created_on, reason,
                                  principal, annual_rate, capitalised_interest)
        base, remaining = money(principal / months), principal
        for n in range(months):
            p = base if n < months - 1 else remaining       # last installment absorbs rounding
            interest = money(remaining * annual_rate / 12)
            sched.installments.append(Installment(sched, n + 1, add_months(first_due, n), p, interest))
            remaining -= p
        self.schedules.append(sched)
        return sched

    def allocate(self, amount):
        """Apply a payment: oldest installment first, interest before principal."""
        allocations, remaining = [], amount
        for inst in self.current_schedule.installments:
            if remaining <= 0:
                break
            if inst.outstanding == 0:
                continue
            i_pay = min(inst.interest - inst.interest_paid - inst.interest_waived, remaining)
            inst.interest_paid += i_pay
            remaining -= i_pay
            p_pay = min(inst.principal - inst.principal_paid, remaining)
            inst.principal_paid += p_pay
            remaining -= p_pay
            allocations.append((inst, i_pay, p_pay))
        return allocations, remaining

    def settlement_quote(self, on):
        """(principal, interest) to settle today: all principal plus interest already due."""
        interest = sum((i.interest - i.interest_paid - i.interest_waived
                        for i in self.current_schedule.installments if i.due_on <= on), ZERO)
        return self.outstanding_principal(), interest


class RepaymentSchedule:
    """One version of a financing agreement's installment plan."""

    LIFECYCLE = Lifecycle("ACTIVE", {"ACTIVE": {"SUPERSEDED": "restructure_financing", "CLOSED": "settle_financing"}},
                          final={"SUPERSEDED", "CLOSED"})

    def __init__(self, agreement, version, created_on, reason, principal, annual_rate,
                 capitalised_interest):
        self.agreement, self.version = agreement, version
        self.created_on, self.reason = created_on, reason
        self.principal, self.annual_rate = principal, annual_rate
        self.capitalised_interest = capitalised_interest
        self.installments: list[Installment] = []
        self.status = StatusHistory("ACTIVE", created_on, "system", reason, lifecycle=self.LIFECYCLE)


class Installment:
    """One scheduled repayment with its principal, interest and what was paid or waived."""

    def __init__(self, schedule, seq, due_on, principal, interest):
        self.schedule, self.seq, self.due_on = schedule, seq, due_on
        self.principal, self.interest = principal, interest
        self.principal_paid = self.interest_paid = self.interest_waived = ZERO

    @property
    def outstanding(self):
        return (self.principal + self.interest - self.principal_paid
                - self.interest_paid - self.interest_waived)

    def status_on(self, on):
        """PAID, SUPERSEDED/CLOSED (schedule replaced), OVERDUE, DUE or SCHEDULED."""
        if self.outstanding == 0:
            return "PAID"
        if self.schedule.status.current in ("SUPERSEDED", "CLOSED"):
            return self.schedule.status.current
        if self.due_on < on:
            return "OVERDUE"
        return "DUE" if self.due_on == on else "SCHEDULED"


class FinancingApplication:
    """A request for financing and everything decided about it.

    Kept permanently, separately from the agreement: the application, its
    documents, the credit decision (an Approval) and its conditions are the
    evidence of why the bank lent.
    """

    LIFECYCLE = Lifecycle("SUBMITTED", {
        "SUBMITTED": {"APPROVED": "decide_application", "APPROVED_WITH_CONDITIONS": "decide_application",
                      "DECLINED": "decide_application"},
        "APPROVED": {"DISBURSED": "disburse_financing"},
        "APPROVED_WITH_CONDITIONS": {"DISBURSED": "disburse_financing (conditions met)"},
    }, final={"DECLINED", "DISBURSED"})

    def __init__(self, applicant, product, amount, term_months, purpose, submitted_on, submitted_by):
        if money(amount) <= 0 or term_months < 1:
            raise BankingError("amount and term must be positive")
        self.application_id = next_id("APP")
        self.applicant, self.product = applicant, product
        self.requested_amount, self.term_months = money(amount), term_months
        self.purpose, self.submitted_on, self.submitted_by = purpose, submitted_on, submitted_by
        self.status = StatusHistory("SUBMITTED", submitted_on, submitted_by.name, purpose, lifecycle=self.LIFECYCLE)
        self.decision: Approval | None = None
        self.approved_amount = self.annual_rate = None
        self.conditions: list[ApprovalCondition] = []
        self.agreement = None
        self.supporting_documents: list[tuple] = []   # (received_on, description, received_by)

    def outstanding_conditions(self):
        return [c for c in self.conditions if not c.is_met()]


class ApprovalCondition:
    """A condition attached to a credit approval that must be met before disbursement."""

    def __init__(self, application, description):
        self.condition_id = next_id("CON")
        self.application, self.description = application, description
        self.satisfied_on = self.satisfied_by = self.evidence = None

    def is_met(self):
        return self.satisfied_on is not None


# =============================================================================
# PART 7 - Beneficiaries and standing instructions
# =============================================================================
class Beneficiary:
    """A saved payee. Changing its bank details creates a new VERSION."""

    LIFECYCLE = Lifecycle("ACTIVE", {"ACTIVE": {"INACTIVE": "deactivate_beneficiary", "DELETED": "delete_beneficiary"},
                           "INACTIVE": {"DELETED": "delete_beneficiary"}}, final={"DELETED"})

    def __init__(self, owner, nickname, bank_name, account_no, title, created_on):
        self.beneficiary_id = next_id("BEN")
        self.owner, self.nickname = owner, nickname
        self.versions = [BeneficiaryVersion(self, 1, bank_name, account_no, title, created_on)]
        self.status = StatusHistory("ACTIVE", created_on, lifecycle=self.LIFECYCLE)

    @property
    def current_version(self):
        return self.versions[-1]

    def amend(self, bank_name, account_no, title, on):
        v = BeneficiaryVersion(self, len(self.versions) + 1, bank_name, account_no, title, on)
        self.versions.append(v)
        return v


class BeneficiaryVersion:
    """The payee's bank details as they were from a date. Payments point at a version."""

    def __init__(self, beneficiary, version, bank_name, account_no, title, effective_from):
        self.beneficiary, self.version = beneficiary, version
        self.bank_name, self.account_no, self.title = bank_name, account_no, title
        self.effective_from = effective_from

    def __str__(self):
        return f"v{self.version}: {self.title} / {self.bank_name} / ****{self.account_no[-4:]}"


class StandingOrder:
    """A recurring monthly transfer. Authority is checked once, when it is set up."""

    LIFECYCLE = Lifecycle("ACTIVE", {"ACTIVE": {"CANCELLED": "cancel_standing_order / account closed"}},
                          final={"CANCELLED"})

    def __init__(self, account, beneficiary, amount, day_of_month, start, created_by, mandate):
        if not 1 <= day_of_month <= 28:
            raise BankingError("standing orders run on day 1-28 so the day exists every month")
        if money(amount) <= 0:
            raise BankingError("standing order amount must be positive")
        self.order_id = next_id("SO")
        self.account, self.beneficiary, self.amount = account, beneficiary, money(amount)
        self.day_of_month, self.created_by, self.mandate_used = day_of_month, created_by, mandate
        first = start.replace(day=day_of_month)
        self.next_due = first if first >= start else add_months(first, 1)
        self.status = StatusHistory("ACTIVE", start, created_by.name, "created", lifecycle=self.LIFECYCLE)
        self.payments: list[TransferPayment] = []


class Biller:
    """An external organisation customers pay bills to (utility, telecom, tax authority).

    A counterparty, not a Party: the bank holds no KYC or relationship with it,
    only the collection arrangement. Deactivating it keeps past bill payments intact.
    """

    CATEGORIES = {"UTILITY", "TELECOM", "TAX", "EDUCATION", "INSURANCE"}

    LIFECYCLE = Lifecycle("ACTIVE", {"ACTIVE": {"INACTIVE": "deactivate_biller"}}, final={"INACTIVE"})

    def __init__(self, code, name, category, registered_on):
        if category not in self.CATEGORIES:
            raise BankingError(f"unknown biller category {category}")
        self.code, self.name, self.category = code, name, category
        self.status = StatusHistory("ACTIVE", registered_on, lifecycle=self.LIFECYCLE)

    def __str__(self):
        return f"{self.name} ({self.category})"


# =============================================================================
# PART 8 - Transactions (double-entry)
#   BankTransaction -> CustomerPayment -> TransferPayment / CardPayment    (multi-level)
#   BankTransaction -> LoanTransaction -> LoanDisbursement / LoanRepayment /
#                                         InterestCapitalisation           (multi-level)
#   BankTransaction -> CashTransaction / FeeCharge / InterestCredit / Reversal /
#                      InternalTransfer
# A reversal never deletes the original; it is a new, counter-posting record.
# =============================================================================
class BankTransaction(ABC):
    """Any movement of money the bank records.

    Shared by all: amount, dates, narrative, status history, the ledger
    entries it produced, reversals against it and correction links.
    post() refuses legs that do not sum to zero (double-entry).

    Abstract: every concrete transaction must name its counterparty (who or
    what is on the other side). story_lines() is a template method whose
    hooks, detail_lines() and case_lines(), subclasses extend.
    """

    prefix = "TXN"

    LIFECYCLE = Lifecycle("INITIATED", {
        "INITIATED": {"POSTED": "post()", "FAILED": "a rule refuses it"},
        "POSTED": {"PARTIALLY_REVERSED": "reverse_transaction (part)", "REVERSED": "reverse_transaction (all)"},
        "PARTIALLY_REVERSED": {"PARTIALLY_REVERSED": "reverse_transaction (part)",
                               "REVERSED": "reverse_transaction (rest)"},
    }, final={"FAILED", "REVERSED"})

    def __init__(self, amount, initiated_on, narrative):
        amount = money(amount)
        if amount <= 0:
            raise BankingError("transaction amount must be positive")
        self.txn_id = next_id(self.prefix)
        self.amount = amount
        self.initiated_on, self.narrative = initiated_on, narrative
        self.status = StatusHistory("INITIATED", initiated_on, "system", narrative, lifecycle=self.LIFECYCLE)
        self.entries: list[LedgerEntry] = []
        self.reversals: list[Reversal] = []
        self.failure_reason = None
        self.supersedes = self.superseded_by = None

    @property
    def kind(self):
        return type(self).__name__

    def post(self, legs, on, by="system"):
        """Write balanced ledger entries: legs is [(account, signed amount), ...]."""
        legs = [(account, money(signed)) for account, signed in legs]
        if sum((signed for _, signed in legs), ZERO) != 0:
            raise BankingError(f"{self.txn_id}: posting legs do not balance")
        for account, signed in legs:
            entry = LedgerEntry(account, signed, on, self)
            account.entries.append(entry)
            self.entries.append(entry)
        self.status.change("POSTED", on, by, "posted to ledger")

    @property
    def reversed_amount(self):
        return sum((r.amount for r in self.reversals if r.status.current == "POSTED"), ZERO)

    @property
    def net_amount(self):
        """Amount still standing after reversals."""
        return self.amount - self.reversed_amount

    def summary(self):
        return f"{self.txn_id} {self.kind} {fmt(self.amount)} [{self.status.current}] {self.narrative}"

    @abstractmethod
    def counterparty(self):
        """Who or what is on the other side of this movement, in words."""

    def detail_lines(self):
        """Hook: facts only this kind of transaction has (extended by subclasses)."""
        return []

    def case_lines(self):
        """Hook: cases raised about this transaction (only customer payments have any)."""
        return []

    def story_lines(self):
        """Template method: the full, unedited story of this transaction."""
        out = [self.summary(), f"  status trail: {self.status.trail()}"]
        out += self.detail_lines()
        if self.supersedes:
            out.append(f"  corrects {self.supersedes.txn_id}")
        if self.superseded_by:
            out.append(f"  superseded by {self.superseded_by.txn_id}")
        for r in self.reversals:
            out.append(f"  reversal {r.txn_id} {fmt(r.amount)}: {r.approval}")
        return out + self.case_lines()


class CustomerPayment(BankTransaction):
    """A payment a customer (or someone acting for one) instructed.

    Adds who initiated it, through which channel, the mandate used (the
    authority at that moment), second-signatory authorisations and disputes.
    Only customer payments can be disputed.
    """

    LIFECYCLE = BankTransaction.LIFECYCLE.extend({
        "INITIATED": {"AWAITING_AUTHORISATION": "needs a second signatory"},
        "AWAITING_AUTHORISATION": {"AUTHORISED": "authorise_payment", "CANCELLED": "cancel_pending_payment"},
        "AUTHORISED": {"POSTED": "post()", "FAILED": "funds re-check fails"},
    }, final={"CANCELLED"})

    def __init__(self, amount, initiated_on, narrative, source_account, initiated_by, channel):
        super().__init__(amount, initiated_on, narrative)
        self.source_account, self.initiated_by, self.channel = source_account, initiated_by, channel
        self.mandate_used: Mandate | None = None
        self.authorisations: list[PaymentAuthorisation] = []
        self.disputes: list[Dispute] = []

    def detail_lines(self):
        return super().detail_lines() + [
            f"  initiated by {self.initiated_by.name} via {self.channel}",
            f"  authority: {self.mandate_used or 'account holder'}",
        ] + [f"  {a}" for a in self.authorisations]

    def case_lines(self):
        return [f"  dispute {d.case_id}: {d.outcome or 'open'}" for d in self.disputes]


class TransferPayment(CustomerPayment):
    """A transfer to a beneficiary. Snapshots the beneficiary VERSION it was sent to."""

    prefix = "TRF"

    LIFECYCLE = CustomerPayment.LIFECYCLE.extend({
        "INITIATED": {"HELD_FOR_REVIEW": "amount >= review threshold"},
        "AUTHORISED": {"HELD_FOR_REVIEW": "amount >= review threshold"},
        "HELD_FOR_REVIEW": {"RELEASED": "release_transaction", "REJECTED": "reject_held_transaction",
                            "FAILED": "funds re-check fails"},
        "RELEASED": {"POSTED": "post()"},
    }, final={"REJECTED"})

    def __init__(self, amount, initiated_on, source_account, beneficiary, initiated_by, channel):
        super().__init__(amount, initiated_on, f"transfer to {beneficiary.nickname}",
                         source_account, initiated_by, channel)
        self.beneficiary = beneficiary
        self.beneficiary_version = beneficiary.current_version   # snapshot at initiation
        self.hold: AccountHold | None = None
        self.standing_order: StandingOrder | None = None

    def counterparty(self):
        return str(self.beneficiary_version)

    def detail_lines(self):
        return super().detail_lines() + [f"  beneficiary as sent: {self.beneficiary_version}"]


class CardPayment(CustomerPayment):
    """A purchase with an issued card. Remembers the exact card used, forever."""

    prefix = "CRD-TX"

    LIFECYCLE = CustomerPayment.LIFECYCLE.extend({"INITIATED": {"DECLINED": "card_purchase refused"}},
                                               final={"DECLINED"})

    def __init__(self, amount, initiated_on, card, merchant, channel="POS", country="PK",
                 merchant_category="RETAIL"):
        super().__init__(amount, initiated_on, f"card purchase at {merchant}",
                         card.account, card.cardholder, "CARD")
        self.card, self.merchant = card, merchant
        self.card_channel, self.country, self.merchant_category = channel, country, merchant_category

    def counterparty(self):
        return f"{self.merchant} ({self.country})"

    def detail_lines(self):
        return super().detail_lines() + [f"  card used: {self.card}"]


class BillPayment(CustomerPayment):
    """A payment to a registered biller against the customer's consumer reference."""

    prefix = "BIL"

    def __init__(self, amount, initiated_on, source_account, biller, consumer_reference,
                 initiated_by, channel):
        super().__init__(amount, initiated_on, f"bill {biller.name} ref {consumer_reference}",
                         source_account, initiated_by, channel)
        self.biller, self.consumer_reference = biller, consumer_reference

    def counterparty(self):
        return f"{self.biller.name} ref {self.consumer_reference}"


class OwnAccountTransfer(CustomerPayment):
    """A transfer between two accounts at this bank that the same customer controls
    (for example funding a term deposit from a current account)."""

    prefix = "OAT"

    def __init__(self, amount, initiated_on, source_account, target_account, initiated_by, channel):
        super().__init__(amount, initiated_on, f"transfer to own account {target_account.number}",
                         source_account, initiated_by, channel)
        self.target_account = target_account

    def counterparty(self):
        return f"own account {self.target_account.number}"


class CashTransaction(BankTransaction):
    """A cash deposit or withdrawal at a branch counter, handled by a teller."""

    prefix = "CSH"

    def __init__(self, amount, initiated_on, account, direction, teller, presented_by):
        super().__init__(amount, initiated_on, f"cash {direction.lower()}")
        self.account, self.direction = account, direction
        self.teller, self.presented_by = teller, presented_by
        self.branch = teller.role_on(initiated_on).branch

    def counterparty(self):
        return f"cash at {self.branch.name}"


class FeeCharge(BankTransaction):
    """A fee, recording the terms version it was charged under."""

    prefix = "FEE"

    def __init__(self, amount, initiated_on, account, fee_code, terms_version):
        super().__init__(amount, initiated_on, f"fee {fee_code}")
        self.account, self.fee_code, self.terms_version = account, fee_code, terms_version

    def counterparty(self):
        return f"bank fee income ({self.fee_code})"


class InterestCredit(BankTransaction):
    """Month-end savings interest paid to the customer."""

    prefix = "INT"

    def __init__(self, amount, initiated_on, account, annual_rate, month_label):
        super().__init__(amount, initiated_on, f"savings interest {month_label}")
        self.account, self.annual_rate = account, annual_rate

    def counterparty(self):
        return "bank interest expense"


class Reversal(BankTransaction):
    """Counter-posts all or part of an original transaction, with an approval."""

    prefix = "REV"

    def __init__(self, amount, initiated_on, original, reason, approval):
        super().__init__(amount, initiated_on, f"reversal of {original.txn_id}: {reason}")
        self.original, self.reason, self.approval = original, reason, approval

    def counterparty(self):
        return f"reverses {self.original.txn_id} ({self.original.counterparty()})"


class InternalTransfer(BankTransaction):
    """A bank-initiated movement no customer instructed: vault cash on branch closure,
    or a term deposit paid out at maturity."""

    prefix = "INTL"

    def counterparty(self):
        return "bank internal accounts"


class LoanTransaction(BankTransaction):
    """Any movement on a financing agreement. Adds the agreement it belongs to.
    Still abstract: each kind of loan movement names its own counterparty."""

    def __init__(self, amount, initiated_on, narrative, agreement):
        super().__init__(amount, initiated_on, narrative)
        self.agreement = agreement


class LoanDisbursement(LoanTransaction):
    """Pays approved financing into the customer's settlement account."""

    prefix = "DSB"

    def __init__(self, amount, initiated_on, agreement, credit_account, approval):
        super().__init__(amount, initiated_on, f"disbursement of {agreement.number}", agreement)
        self.credit_account, self.approval = credit_account, approval

    def counterparty(self):
        return f"paid into {self.credit_account.number}"


class InterestCapitalisation(LoanTransaction):
    """Overdue interest added to principal on restructuring. Moves no customer cash,
    but must still be booked so loans receivable stays correct."""

    prefix = "CAP"

    def __init__(self, amount, initiated_on, agreement, approval):
        super().__init__(amount, initiated_on, f"overdue interest capitalised on {agreement.number}", agreement)
        self.approval = approval

    def counterparty(self):
        return f"interest receivable on {self.agreement.number}"


class LoanRepayment(LoanTransaction):
    """A repayment, with how it was split across installments (interest first)."""

    prefix = "RPY"

    def __init__(self, amount, initiated_on, agreement, debit_account, purpose="installment"):
        super().__init__(amount, initiated_on, f"{purpose} on {agreement.number}", agreement)
        self.debit_account = debit_account
        self.allocations = []

    def counterparty(self):
        return f"paid from {self.debit_account.number}"


# =============================================================================
# PART 9 - Cards: an issued card is a CREDENTIAL linked to an account, not an account
# =============================================================================
class IssuedCard:
    """One physical card with its own number, limits and status.

    Replacement creates a NEW card linked both ways (replaces / replaced_by),
    so the full chain is searchable and each card keeps its own payments.
    """

    LIFECYCLE = Lifecycle("ACTIVE", {
        "ACTIVE": {"BLOCKED_LOST": "report_card LOST", "BLOCKED_STOLEN": "report_card STOLEN",
                   "BLOCKED_DAMAGED": "report_card DAMAGED", "CANCELLED": "close_account"},
        "BLOCKED_LOST": {"ACTIVE": "reactivate_card", "DESTROYED": "record_card_found"},
        "BLOCKED_STOLEN": {"DESTROYED": "record_card_found"},
        "BLOCKED_DAMAGED": {"DESTROYED": "record_card_found"},
    }, final={"DESTROYED", "CANCELLED"})

    def __init__(self, product, account, cardholder, issued_on, daily_limit, replaces=None):
        self.card_id = next_id("CARD")
        seq = int(self.card_id.split("-")[1])
        self.masked_number = f"4213 **** **** {(seq * 7919) % 9000 + 1000}"
        self.product, self.account, self.cardholder = product, account, cardholder
        self.issued_on, self.expires_on = issued_on, add_months(issued_on, 60)
        self.status = StatusHistory("ACTIVE", issued_on, "card-ops", "issued", lifecycle=self.LIFECYCLE)
        self.limit_history = [(issued_on, money(daily_limit))]
        self.replaces, self.replaced_by = replaces, None
        self.payments: list[CardPayment] = []
        self.events: list[tuple] = []
        self.controls: list[CardControl] = []

    def daily_limit_on(self, d):
        result = None
        for start, limit in self.limit_history:
            if start <= d:
                result = limit
        return result

    def spent_on(self, d):
        """Net amount spent on a day, counting only payments that went through."""
        return sum((p.net_amount for p in self.payments if p.initiated_on == d
                    and p.status.current in ("POSTED", "PARTIALLY_REVERSED")), ZERO)

    def lineage(self):
        """Every card in this card's replacement chain, oldest first."""
        first = self
        while first.replaces:
            first = first.replaces
        chain = []
        while first:
            chain.append(first)
            first = first.replaced_by
        return chain

    def __str__(self):
        return f"{self.card_id} {self.masked_number} ({self.cardholder.name})"


class CardControl:
    """A usage control on one card (online, international, cash, a merchant category),
    in force for a period. Turning it off closes the period, so "was this card blocked
    for online use on the day of the disputed purchase?" stays answerable.
    """

    TYPES = {"ONLINE", "INTERNATIONAL", "CASH_WITHDRAWAL", "MERCHANT_CATEGORY"}

    def __init__(self, card, control_type, value, start, set_by):
        if control_type not in self.TYPES:
            raise BankingError(f"unknown card control {control_type}")
        if control_type == "MERCHANT_CATEGORY" and not value:
            raise BankingError("a merchant-category control needs a category")
        self.control_id = next_id("CTL")
        self.card, self.control_type, self.value = card, control_type, value
        self.period = Period(start)
        self.set_by, self.removed_by = str(set_by), None

    def blocks(self, channel, country, merchant_category, on):
        """True if this control stopped such a card payment on that date."""
        if not self.period.contains(on):
            return False
        return {"ONLINE": channel == "ONLINE",
                "INTERNATIONAL": country != "PK",
                "CASH_WITHDRAWAL": channel == "ATM",
                "MERCHANT_CATEGORY": merchant_category == self.value}[self.control_type]

    def __str__(self):
        what = self.control_type + (f"={self.value}" if self.value else "")
        return f"{self.control_id} block {what} ({self.period})"


# =============================================================================
# PART 10 - Cases
#   Case -> CustomerCase -> Dispute / Complaint / ServiceRequest          (multi-level)
#   Case -> RiskCase -> FraudAlert / ComplianceInvestigation              (multi-level)
#   Case -> CollectionsCase
# =============================================================================
class Case(ABC):
    """Any piece of tracked work: owner assignments, notes, evidence, links, outcome.

    Abstract: every concrete case must say which staff roles may work it
    (handler_roles), so the rule lives with the case, not in the Bank.
    """

    prefix = "CASE"

    LIFECYCLE = Lifecycle("OPEN", {"OPEN": {"CLOSED": "close_case"}}, final={"CLOSED"})

    def __init__(self, subject, opened_on, opened_by, summary):
        self.case_id = next_id(self.prefix)
        self.subject, self.summary = subject, summary
        self.opened_on, self.opened_by = opened_on, str(opened_by)
        self.status = StatusHistory("OPEN", opened_on, opened_by, summary, lifecycle=self.LIFECYCLE)
        self.assignments: list[tuple] = []
        self.notes: list[CaseNote] = []
        self.evidence: list[CaseEvidence] = []
        self.linked_cases: list[Case] = []
        self.outcome = None
        self.archived_on = None                  # set when moved to the retention archive

    @property
    def kind(self):
        return type(self).__name__

    @property
    def is_open(self):
        return self.status.current != "CLOSED"

    @abstractmethod
    def handler_roles(self):
        """The staff roles allowed to be assigned this case."""

    def assign(self, employee, on):
        self.assignments.append((on, employee))

    def add_note(self, text, on, by):
        self.notes.append(CaseNote(text, on, by))

    def link(self, other):
        """Link two related cases in both directions (e.g. an alert and an investigation)."""
        if other is not self and other not in self.linked_cases:
            self.linked_cases.append(other)
            other.linked_cases.append(self)

    def close(self, outcome, on, by):
        if not self.is_open:
            raise InvalidStateError(f"{self.case_id} already closed")
        self.outcome = outcome
        self.status.change("CLOSED", on, by, outcome)


class CaseNote:
    """A dated note written on a case."""

    def __init__(self, text, on, by):
        self.text, self.on, self.by = text, on, str(by)


class CaseEvidence:
    """Captures a SNAPSHOT, so later corrections to the source do not rewrite the evidence."""

    def __init__(self, description, captured_on, captured_by, source, snapshot):
        self.evidence_id = next_id("EVD")
        self.description, self.captured_on, self.captured_by = description, captured_on, str(captured_by)
        self.source, self.snapshot = source, dict(snapshot)


class CustomerCase(Case):
    """Raised BY or ON BEHALF OF a customer through a service channel."""

    def __init__(self, subject, opened_on, opened_by, summary, channel, contact_person):
        super().__init__(subject, opened_on, opened_by, summary)
        self.channel, self.contact_person = channel, contact_person

    def handler_roles(self):
        return Bank.BRANCH_ROLES | Bank.CARD_ROLES      # front-line service staff


class Dispute(CustomerCase):
    """A customer challenges a payment; may end with a (partial) refund reversal."""

    prefix = "DSP"

    def __init__(self, subject, opened_on, opened_by, transaction, disputed_amount, channel, contact):
        super().__init__(subject, opened_on, opened_by,
                         f"dispute of {transaction.txn_id}", channel, contact)
        self.transaction, self.disputed_amount = transaction, money(disputed_amount)
        self.refund: Reversal | None = None


class Complaint(CustomerCase):
    """An expression of dissatisfaction about service (no money necessarily in question)."""

    prefix = "CMP"

    def __init__(self, subject, opened_on, opened_by, summary, channel, contact, category):
        super().__init__(subject, opened_on, opened_by, summary, channel, contact)
        self.category = category


class ServiceRequest(CustomerCase):
    """Routine customer instruction (block a card, request a statement, update details)."""

    prefix = "SR"

    def __init__(self, subject, opened_on, opened_by, request_type, channel, contact, related=None):
        super().__init__(subject, opened_on, opened_by, request_type, channel, contact)
        self.request_type, self.related = request_type, related


class RiskCase(Case):
    """Bank-initiated risk work. Cannot close while its own restrictions are in force."""

    def __init__(self, subject, opened_on, opened_by, summary, risk_level):
        super().__init__(subject, opened_on, opened_by, summary)
        self.risk_level = risk_level
        self.restrictions: list[Restriction] = []

    def handler_roles(self):
        return Bank.COMPLIANCE_ROLES

    def close(self, outcome, on, by):
        live = [r for r in self.restrictions if r.period.contains(on)]
        if live:
            raise InvalidStateError(f"{self.case_id} still has {len(live)} restriction(s) in force")
        super().close(outcome, on, by)


class FraudAlert(RiskCase):
    """Raised automatically by a monitoring rule; may point at a transaction."""

    prefix = "ALERT"

    def __init__(self, subject, opened_on, rule, transaction=None):
        super().__init__(subject, opened_on, "monitoring-system", f"rule {rule}", "MEDIUM")
        self.rule, self.transaction = rule, transaction


class ComplianceInvestigation(RiskCase):
    """An investigation opened by a compliance analyst; the only case that restricts."""

    prefix = "CMPL"


class CollectionsCase(Case):
    """Opened by the arrears batch when a financing installment becomes overdue."""

    prefix = "COL"

    def __init__(self, subject, opened_on, agreement, overdue_amount):
        super().__init__(subject, opened_on, "arrears-batch",
                         f"{agreement.number} overdue {fmt(overdue_amount)}")
        self.agreement, self.overdue_at_opening = agreement, overdue_amount
        self.promises: list[PromiseToPay] = []

    def handler_roles(self):
        return Bank.COLLECTIONS_ROLES


class PromiseToPay:
    """A customer's promise, recorded by collections staff, to pay an amount by a date.
    The arrears batch later marks it KEPT or BROKEN; the promise itself is never edited."""

    LIFECYCLE = Lifecycle("OPEN", {"OPEN": {"KEPT": "arrears batch: paid in time", "BROKEN": "arrears batch: not paid"}},
                          final={"KEPT", "BROKEN"})

    def __init__(self, case, amount, due_on, recorded_on, recorded_by):
        self.case, self.amount, self.due_on = case, money(amount), due_on
        self.recorded_on, self.recorded_by = recorded_on, str(recorded_by)
        self.status = StatusHistory("OPEN", recorded_on, recorded_by, f"promise {fmt(self.amount)}", lifecycle=self.LIFECYCLE)


# =============================================================================
# PART 11 - Customer communications
# =============================================================================
class Statement:
    """A statement of one account for a period, rendered from its ledger entries."""

    def __init__(self, account, start, end, generated_on):
        if end < start:
            raise BankingError("statement end is before its start")
        self.statement_id = next_id("STM")
        self.account, self.start, self.end, self.generated_on = account, start, end, generated_on
        self.opening = account.ledger_balance(start - timedelta(days=1))
        self.lines = [e for e in account.entries if start <= e.posted_on <= end]
        self.closing = account.ledger_balance(end)

    def render(self):
        out = [f"Statement {self.statement_id} for {self.account} {self.start} to {self.end}",
               f"  Opening balance {fmt(self.opening)}"]
        for e in self.lines:
            out.append(f"  {e.posted_on}  {e.amount:>15,.2f}  {e.transaction.txn_id:<11} "
                       f"{e.transaction.narrative}")
        out.append(f"  Closing balance {fmt(self.closing)}")
        return out


class Notice:
    """A letter or message sent to a party (arrears, terms change, branch change)."""

    def __init__(self, party, notice_type, sent_on, text):
        self.notice_id = next_id("NTC")
        self.party, self.notice_type, self.sent_on, self.text = party, notice_type, sent_on, text


# =============================================================================
# PART 12 - Bank: the application service
# Every public operation checks the rules, records the change as NEW data and
# writes an audit event. Refused money movements are kept as FAILED/DECLINED
# transactions (with the reason) rather than being thrown away.
# =============================================================================
class Bank:
    """The bank: registries of every record, the simulated clock and all operations."""

    LARGE_TRANSFER_REVIEW = money(1_000_000)
    BRANCH_ROLES = {"TELLER", "RELATIONSHIP_MANAGER", "OPERATIONS_OFFICER", "BRANCH_MANAGER"}
    COMPLIANCE_ROLES = {"COMPLIANCE_ANALYST", "COMPLIANCE_MANAGER"}
    CREDIT_ROLES = {"CREDIT_OFFICER", "CREDIT_MANAGER"}
    CARD_ROLES = {"CARD_OPERATIONS"}
    COLLECTIONS_ROLES = {"COLLECTIONS_OFFICER"}
    AUDIT_ROLES = {"AUDITOR", "BRANCH_MANAGER"}
    SEGMENTS = {"RETAIL", "SOLE_TRADER", "PRIVATE", "SME", "CORPORATE", "NON_PROFIT"}
    RETENTION_YEARS = 10          # assumption A31: records kept at least 10 years after closure
    REVERSAL_ROLES = CARD_ROLES | COMPLIANCE_ROLES | {"OPERATIONS_OFFICER"}
    # Delegated credit authority: the largest amount each role may approve (assumption A24).
    CREDIT_LIMITS = {"CREDIT_OFFICER": money(5_000_000), "CREDIT_MANAGER": money(25_000_000)}

    def __init__(self, name, today):
        self.name, self.today = name, today
        self.parties, self.branches, self.employees, self.products = {}, {}, {}, {}
        self.arrangements, self.transactions, self.cards, self.beneficiaries = {}, {}, {}, {}
        self.standing_orders, self.applications, self.cases = {}, {}, {}
        self.statements, self.notices, self.audit = [], [], []
        self.approvals, self.billers = [], {}
        self.gl = {}
        for code, gl_name, gl_type in [
                ("1100", "Loans receivable", "ASSET"),
                ("2100", "Outgoing payments clearing", "LIABILITY"),
                ("2200", "Card scheme settlement", "LIABILITY"),
                ("2300", "Biller settlement", "LIABILITY"),
                ("4000", "Fee income", "INCOME"),
                ("4100", "Financing interest income", "INCOME"),
                ("5000", "Deposit interest expense", "EXPENSE")]:
            self.gl[code] = GeneralLedgerAccount(code, gl_name, gl_type)

    # ---------------------------------------------------------------- plumbing
    def _log(self, actor, action, subject, detail=""):
        self.audit.append(AuditEvent(self.today, str(actor), action, subject, detail))

    def _require_role(self, employee, roles, action):
        """Return the employee's current assignment, or raise if the role is not allowed."""
        a = employee.role_on(self.today) if isinstance(employee, Employee) else None
        if a is None or a.role not in roles:
            raise AuthorityError(f"{employee} ({a.role if a else 'no role'}) may not {action}")
        return a

    def _notify(self, party, notice_type, text):
        n = Notice(party, notice_type, self.today, text)
        self.notices.append(n)
        return n

    def _fail(self, txn, err, status="FAILED"):
        """Keep a refused transaction with its reason instead of discarding it."""
        txn.failure_reason = str(err)
        txn.status.change(status, self.today, "system", str(err))
        self._log("system", f"TXN_{status}", txn.txn_id, str(err))
        return txn

    def _check_authority(self, account, person, capability, amount=ZERO):
        """Who may move money on an account: a holder, or someone with a live mandate.
        Returns the mandate used (None for a holder acting on their own account)."""
        for r in person.restrictions:
            if r.blocks("DEBIT", self.today):
                raise RestrictionViolation(f"{person.name} personally restricted: {r.reason}")
        if person in account.holders:
            return None
        for holder in account.holders:
            if isinstance(holder, Organization):
                return holder.find_mandate(person, capability, amount, self.today)
        raise AuthorityError(f"{person.name} has no authority over {account.number}")

    def advance_to(self, target):
        """Move the simulated clock forward, running the end-of-day batch each day."""
        while self.today < target:
            self.today += timedelta(days=1)
            self.run_standing_orders()
            self.run_arrears_check()
            self.run_term_deposit_maturity()
            if (self.today + timedelta(days=1)).month != self.today.month:
                self.charge_monthly_fees()
                self.credit_savings_interest()

    # ---------------------------------------------------------------- branches & staff
    def open_branch(self, code, name, city):
        """Operation: open a branch (with its own vault-cash ledger)."""
        if code in self.branches:
            raise InvalidStateError(f"branch code {code} already used")
        b = Branch(code, name, city, self.today)
        b.vault = GeneralLedgerAccount(f"1000-{code}", f"Vault cash {code}", "ASSET")
        self.gl[b.vault.number] = b.vault
        self.branches[code] = b
        self._log("system", "OPEN_BRANCH", code, name)
        return b

    def hire_employee(self, person, role, branch):
        """Operation: hire a person into a role at an open branch."""
        if not branch.is_open:
            raise InvalidStateError(f"{branch} is {branch.status.current}")
        e = Employee(person, self.today)
        e.assign(role, branch, self.today)
        self.employees[e.employee_no] = e
        self._log("HR", "HIRE", e.employee_no, f"{person.name} as {role} at {branch.code}")
        return e

    def change_role(self, employee, role, branch=None):
        """Operation: promote/move an employee. Old assignments stay for history."""
        current = employee.current_assignment()
        if current is None:
            raise InvalidStateError(f"{employee} is not currently employed")
        branch = branch or current.branch
        employee.assign(role, branch, self.today)
        self._log("HR", "ROLE_CHANGE", employee.employee_no, f"{employee} -> {role} at {branch.code}")

    def record_employee_exit(self, employee, reason):
        """Operation: end employment. Blocked while the person still manages customers."""
        current = employee.current_assignment()
        if current is None:
            raise InvalidStateError(f"{employee} has already left ({employee.status.current})")
        managed = [p.name for p in self.parties.values() if p.relationship
                   and p.relationship.status.current == "ACTIVE"
                   and p.relationship.manager_on(self.today) is employee]
        if managed:
            raise InvalidStateError(f"{employee} still manages {len(managed)} customer(s): "
                                    + ", ".join(managed))
        current.period.close(self.today)
        employee.status.change("LEFT", self.today, "HR", reason)
        self._log("HR", "EMPLOYEE_EXIT", employee.employee_no, reason)

    def close_branch(self, branch, into, by):
        """Operation: close a branch, moving customers, accounts, staff and vault cash.
        The branch record, and where everything used to be, are kept."""
        if branch is into:
            raise InvalidStateError("a branch cannot be merged into itself")
        if not branch.is_open or not into.is_open:
            raise InvalidStateError("both branches must be open")
        moved = {"customers": 0, "accounts": 0, "staff": 0}
        for party in self.parties.values():
            rel = party.relationship
            if rel and rel.home_branch_on(self.today) is branch:
                rel.move(into, self.today)
                self._notify(party, "BRANCH_CHANGE", f"{branch} closed; now served by {into}")
                moved["customers"] += 1
        for acct in self.arrangements.values():
            if acct.status.current not in ("CLOSED", "SETTLED") and acct.servicing_branch_on(self.today) is branch:
                acct.move_servicing(into, self.today)
                moved["accounts"] += 1
        for emp in self.employees.values():
            cur = emp.current_assignment()
            if cur and cur.branch is branch:
                emp.assign(cur.role, into, self.today)
                moved["staff"] += 1
        cash = -branch.vault.ledger_balance()            # vault is an asset (debit balance)
        if cash > 0:
            t = InternalTransfer(cash, self.today, f"vault cash {branch.code} -> {into.code}")
            t.post([(into.vault, -cash), (branch.vault, cash)], self.today, by)
            self.transactions[t.txn_id] = t
        branch.status.change("CLOSED", self.today, by, f"merged into {into.code}")
        branch.merged_into = into
        self._log(by, "CLOSE_BRANCH", branch.code, f"into {into.code}: {moved}")
        return moved

    # ---------------------------------------------------------------- parties & KYC
    def _register(self, party, by, action):
        self.parties[party.party_id] = party
        self._log(by, action, party.party_id, party.name)
        return party

    def register_person(self, name, dob, by):
        """Operation: record a natural person (once, whatever roles they later hold)."""
        return self._register(Person(name, self.today, dob), by, "REGISTER_PERSON")

    def register_company(self, name, reg_no, address, incorporated_on, by):
        """Operation: record a company."""
        return self._register(Company(name, self.today, reg_no, address, incorporated_on), by,
                              "REGISTER_COMPANY")

    def register_charity(self, name, reg_no, address, by):
        """Operation: record a charity or trust."""
        return self._register(Charity(name, self.today, reg_no, address), by, "REGISTER_CHARITY")

    def add_identity_document(self, party, doc_type, number, issued_on, expires_on, by):
        """Operation: file an identity or registration document for a party."""
        if expires_on is not None and expires_on < issued_on:
            raise BankingError("document expires before it was issued")
        d = IdentityDocument(party, doc_type, number, issued_on, expires_on)
        party.documents.append(d)
        self._log(by, "ADD_DOCUMENT", party.party_id, str(d))
        return d

    def verify_party(self, party, document, by):
        """Operation: KYC-check a party against a document (PASS only if valid today)."""
        self._require_role(by, self.BRANCH_ROLES | self.COMPLIANCE_ROLES, "verify identity")
        if document.party is not party:
            raise BankingError(f"{document} does not belong to {party.name}")
        ok = document.valid_on(self.today)
        chk = VerificationCheck(party, document, self.today, by, "PASS" if ok else "FAIL",
                                "" if ok else "document not valid today")
        party.checks.append(chk)
        self._log(by, "VERIFY", party.party_id, f"{chk.result} against {document}")
        return chk

    def appoint_officer(self, org, person, by):
        """Operation: appoint a director/trustee (title comes from the organisation type)."""
        if any(r.person is person and r.period.end is None for r in org.officers):
            raise InvalidStateError(f"{person.name} already holds office at {org.name}")
        r = OfficerRole(org, person, org.officer_title, self.today)
        org.officers.append(r)
        self._log(by, "APPOINT_OFFICER", org.party_id, f"{person.name} as {r.title}")
        return r

    def end_officer_role(self, org, person, reason, by):
        """Operation: end an office (resignation). The role record stays."""
        for r in org.officers:
            if r.person is person and r.period.end is None:
                r.period.close(self.today)
                r.end_reason = reason
                self._log(by, "END_OFFICER", org.party_id, f"{person.name}: {reason}")
                return r
        raise InvalidStateError(f"{person.name} holds no active office at {org.name}")

    def record_beneficial_owner(self, org, person, percent, by):
        """Operation: record a beneficial owner and their percentage."""
        o = BeneficialOwnership(org, person, percent, self.today)
        org.owners.append(o)
        self._log(by, "BENEFICIAL_OWNER", org.party_id, f"{person.name} {percent}%")
        return o

    def grant_mandate(self, org, person, capabilities, limit, by, dual_control_above=None):
        """Operation: give a person banking authority for an organisation."""
        m = Mandate(org, person, capabilities, limit, self.today, by, dual_control_above)
        org.mandates.append(m)
        self._log(by, "GRANT_MANDATE", m.mandate_id, str(m))
        return m

    def revoke_mandate(self, mandate, reason, by):
        """Operation: withdraw authority from today. Past use stays valid and provable."""
        mandate.revoke(self.today, reason)
        self._log(by, "REVOKE_MANDATE", mandate.mandate_id, reason)

    def authority_on(self, org, person, on):
        """Query: which mandates a person held for an organisation on a date."""
        return [m for m in org.mandates if m.person is person and m.period.contains(on)]

    def correct_party_detail(self, party, key, value, reason, by):
        """Operation: correct a recorded detail; the old value is kept."""
        c = party.correct_detail(key, value, self.today, by, reason)
        self._log(by, "CORRECT_DETAIL", party.party_id, f"{key}: '{c.old_value}' -> '{value}'")
        return c

    def become_customer(self, party, by, segment, trading_name=None):
        """Operation: onboard a party. Refused if the party or its connected persons
        are not verified TODAY (documents can expire while onboarding is pending).
        A sole trader is a Person trading under a name (no separate legal entity);
        a PRIVATE (high-value) customer also needs a verified source-of-wealth document."""
        assignment = self._require_role(by, self.BRANCH_ROLES, "onboard customers")
        if segment not in self.SEGMENTS:
            raise BankingError(f"unknown segment {segment}")
        if party.relationship and party.relationship.status.current == "ACTIVE":
            raise InvalidStateError(f"{party.name} is already a customer")
        if segment in ("SOLE_TRADER", "PRIVATE", "RETAIL") and not isinstance(party, Person):
            raise BankingError(f"segment {segment} is for individuals; {party.name} is an organisation")
        if segment == "SOLE_TRADER" and not trading_name:
            raise BankingError("a sole trader must state the trading name")
        gaps = party.kyc_gaps(self.today)
        if segment == "PRIVATE" and not any(
                c.result == "PASS" and c.document.doc_type == "SOURCE_OF_WEALTH"
                and c.document.valid_on(self.today) for c in party.checks):
            gaps.append(f"{party.name}: enhanced due diligence needs a verified source-of-wealth document")
        if gaps:
            self._log(by, "ONBOARDING_BLOCKED", party.party_id, "; ".join(gaps))
            raise KycIncomplete("; ".join(gaps))
        rm = by if assignment.role == "RELATIONSHIP_MANAGER" else None
        party.relationship = CustomerRelationship(party, self.today, assignment.branch, segment, rm)
        if trading_name:
            party.record_detail("trading_name", trading_name)
        self._log(by, "ONBOARD", party.party_id, f"{segment} customer at {assignment.branch.code}")
        return party.relationship

    def assign_relationship_manager(self, party, employee, by):
        """Operation: hand a customer to a relationship manager (history kept)."""
        self._require_role(employee, {"RELATIONSHIP_MANAGER"}, "manage customers")
        if not party.relationship:
            raise InvalidStateError(f"{party.name} is not a customer")
        party.relationship.set_manager(employee, self.today)
        self._log(by, "ASSIGN_RM", party.party_id, str(employee))

    def end_relationship(self, party, reason, by):
        """Operation: a customer leaves. Everything they did stays; only the relationship closes."""
        if not party.relationship:
            raise InvalidStateError(f"{party.name} is not a customer")
        live = [a.number for a in self.arrangements.values()
                if party in a.holders and a.status.current not in ("CLOSED", "SETTLED")]
        if live:
            raise InvalidStateError(f"{party.name} still holds {', '.join(live)}")
        rel = party.relationship
        rel.status.change("ENDED", self.today, by, reason, allowed_from={"ACTIVE"})
        if rel.rm_history and rel.rm_history[-1][0].end is None:
            rel.rm_history[-1][0].close(self.today)
        self._log(by, "END_RELATIONSHIP", party.party_id, reason)

    # ---------------------------------------------------------------- products
    def define_product(self, code, name, category, **terms):
        """Operation: add a product to the catalogue with its first terms version."""
        if code in self.products:
            raise InvalidStateError(f"product code {code} already used")
        p = ProductDefinition(code, name, category, self.today)
        p.add_terms(self.today, **terms)
        self.products[code] = p
        self._log("product-team", "DEFINE_PRODUCT", code, name)
        return p

    def revise_product_terms(self, product, effective_from, **changes):
        """Operation: publish new terms. Existing customers stay on their pinned version."""
        merged = dict(product.terms_versions[-1].terms, **changes)
        v = product.add_terms(effective_from, **merged)
        self._log("product-team", "REVISE_TERMS", product.code, str(v))
        return v

    def withdraw_from_sale(self, product, reason):
        """Operation: stop selling a product to NEW customers; existing ones keep it."""
        product.sale_status.change("CLOSED_TO_NEW", self.today, "product-team", reason,
                                   allowed_from={"ON_SALE"})
        self._log("product-team", "WITHDRAW_PRODUCT", product.code, reason)

    def migrate_terms(self, arrangement, by):
        """Operation: move an arrangement to the latest terms, with a notice to holders."""
        latest = arrangement.product.terms_on(self.today)
        old = arrangement.terms
        if latest is old:
            raise InvalidStateError(f"{arrangement.number} is already on v{old.version_no}")
        arrangement.migrate_terms(latest, self.today)
        for h in arrangement.holders:
            self._notify(h, "TERMS_CHANGE", f"{arrangement.number} moved from v{old.version_no} "
                                            f"to v{latest.version_no}")
        self._log(by, "MIGRATE_TERMS", arrangement.number, f"v{old.version_no} -> v{latest.version_no}")

    # ---------------------------------------------------------------- accounts & cash
    def open_deposit_account(self, account_class, product, holders, by, payout_account=None):
        """Operation: open a current, savings or fixed-term deposit account for onboarded,
        verified holders. A term deposit names the account it pays out to."""
        if not (isinstance(account_class, type) and issubclass(account_class, DepositAccount)
                and account_class is not DepositAccount):
            raise ProductNotAvailable("choose CurrentAccount, SavingsAccount or FixedTermDeposit")
        if account_class is FixedTermDeposit and (
                payout_account is None or set(payout_account.holders) != set(holders)):
            raise BankingError("a term deposit needs a payout account with the same holders")
        assignment = self._require_role(by, self.BRANCH_ROLES, "open accounts")
        for h in holders:
            if not h.relationship or h.relationship.status.current != "ACTIVE":
                raise KycIncomplete(f"{h.name} is not an onboarded customer")
            gaps = h.kyc_gaps(self.today)
            if gaps:
                raise KycIncomplete("; ".join(gaps))
        acct = account_class(product, holders, self.today, assignment.branch, by)
        if payout_account is not None and isinstance(acct, FixedTermDeposit):
            acct.payout_account = payout_account
        self.arrangements[acct.number] = acct
        self._log(by, "OPEN_ACCOUNT", acct.number, f"{product.name} terms v{acct.terms.version_no}")
        return acct

    def close_account(self, account, reason, by):
        """Operation: close a deposit account. Needs a zero balance, no holds, no payment
        waiting, and no live financing settling into it. The account and its entries stay."""
        if not isinstance(account, DepositAccount):
            raise InvalidStateError(f"{account.number} is not a deposit account; settle financing instead")
        if account.status.current != "ACTIVE":
            raise InvalidStateError(f"{account.number} is {account.status.current}")
        if account.ledger_balance() != 0:
            raise InvalidStateError(f"{account.number} balance is {fmt(account.ledger_balance())}")
        if account.held_amount(self.today) > 0:
            raise InvalidStateError(f"{account.number} has funds on hold")
        waiting = [t.txn_id for t in self.transactions.values() if isinstance(t, CustomerPayment)
                   and t.source_account is account
                   and t.status.current in ("AWAITING_AUTHORISATION", "AUTHORISED", "HELD_FOR_REVIEW")]
        if waiting:
            raise InvalidStateError(f"{account.number} has payments in progress: {', '.join(waiting)}")
        loans = [f.number for f in self.arrangements.values() if isinstance(f, FinancingAgreement)
                 and f.settlement_account is account and f.status.current in f.USABLE_STATUSES]
        if loans:
            raise InvalidStateError(f"{account.number} settles live financing {', '.join(loans)}")
        for c in self.cards.values():
            if c.account is account and c.status.current == "ACTIVE":
                c.status.change("CANCELLED", self.today, by, "account closed")
        for so in self.standing_orders.values():
            if so.account is account and so.status.current == "ACTIVE":
                so.status.change("CANCELLED", self.today, by, "account closed")
        account.status.change("CLOSED", self.today, by, reason, allowed_from={"ACTIVE"})
        self._log(by, "CLOSE_ACCOUNT", account.number, reason)

    def deposit_cash(self, account, amount, teller, presented_by=None):
        """Operation: cash paid in at the counter (vault cash up, customer balance up)."""
        self._require_role(teller, {"TELLER"}, "handle cash")
        txn = CashTransaction(amount, self.today, account, "DEPOSIT", teller, presented_by)
        self.transactions[txn.txn_id] = txn
        try:
            account.ensure_usable("CREDIT", self.today)
        except BankingError as e:
            return self._fail(txn, e)
        txn.post([(account, txn.amount), (txn.branch.vault, -txn.amount)], self.today, teller)
        self._log(teller, "CASH_DEPOSIT", account.number, fmt(txn.amount))
        return txn

    def withdraw_cash(self, account, amount, teller, presented_by):
        """Operation: cash paid out, only to a holder or someone with a PAYMENTS mandate."""
        self._require_role(teller, {"TELLER"}, "handle cash")
        txn = CashTransaction(amount, self.today, account, "WITHDRAWAL", teller, presented_by)
        self.transactions[txn.txn_id] = txn
        try:
            if presented_by is None:
                raise AuthorityError("a withdrawal must be presented by an identified person")
            self._check_authority(account, presented_by, "PAYMENTS", txn.amount)
            account.check_debit(txn.amount, self.today)
        except BankingError as e:
            return self._fail(txn, e)
        txn.post([(account, -txn.amount), (txn.branch.vault, txn.amount)], self.today, teller)
        self._log(teller, "CASH_WITHDRAWAL", account.number, fmt(txn.amount))
        return txn

    def charge_fee(self, account, fee_code, amount, by="system"):
        """Operation: charge a fee under the account's pinned terms.
        Bank-originated debits are not blocked by customer restrictions (assumption A9)."""
        txn = FeeCharge(amount, self.today, account, fee_code, account.terms)
        self.transactions[txn.txn_id] = txn
        txn.post([(account, -txn.amount), (self.gl["4000"], txn.amount)], self.today, by)
        self._log(by, "FEE", account.number, f"{fee_code} {fmt(txn.amount)} (terms v{account.terms.version_no})")
        return txn

    def charge_monthly_fees(self):
        """Batch: month-end maintenance fee on every active deposit account."""
        for acct in list(self.arrangements.values()):
            if isinstance(acct, DepositAccount) and acct.status.current == "ACTIVE":
                fee = money(acct.terms.get("monthly_fee", 0))
                if fee > 0:
                    self.charge_fee(acct, "MONTHLY_MAINTENANCE", fee)

    def credit_savings_interest(self):
        """Batch: month-end interest on savings = lowest balance in the month x rate / 12."""
        for acct in list(self.arrangements.values()):
            if not isinstance(acct, SavingsAccount) or acct.status.current != "ACTIVE":
                continue
            rate = Decimal(str(acct.terms.get("annual_rate", 0)))
            first = max(self.today.replace(day=1), acct.opened_on)
            lowest = min(acct.ledger_balance(first + timedelta(days=n))
                         for n in range((self.today - first).days + 1))
            interest = money(max(lowest, ZERO) * rate / 12)
            if interest > 0:
                txn = InterestCredit(interest, self.today, acct, rate, self.today.strftime("%b %Y"))
                txn.post([(acct, interest), (self.gl["5000"], -interest)], self.today)
                self.transactions[txn.txn_id] = txn
                self._log("system", "SAVINGS_INTEREST", acct.number, fmt(interest))

    def generate_statement(self, account, start, end):
        """Operation: produce a statement for a period."""
        s = Statement(account, start, end, self.today)
        self.statements.append(s)
        self._log("system", "STATEMENT", account.number, f"{start} to {end}")
        return s

    # ---------------------------------------------------------------- payments
    def add_beneficiary(self, owner, nickname, bank_name, account_no, title, by):
        """Operation: save a payee for a customer."""
        b = Beneficiary(owner, nickname, bank_name, account_no, title, self.today)
        self.beneficiaries[b.beneficiary_id] = b
        self._log(by, "ADD_BENEFICIARY", b.beneficiary_id, str(b.current_version))
        return b

    def amend_beneficiary(self, beneficiary, bank_name, account_no, title, by):
        """Operation: change a payee's details as a new version (old payments keep theirs)."""
        if beneficiary.status.current != "ACTIVE":
            raise InvalidStateError(f"{beneficiary.nickname} is {beneficiary.status.current}")
        v = beneficiary.amend(bank_name, account_no, title, self.today)
        self._log(by, "AMEND_BENEFICIARY", beneficiary.beneficiary_id, str(v))
        return v

    def deactivate_beneficiary(self, beneficiary, reason, by):
        """Operation: stop a payee being used (the record stays)."""
        beneficiary.status.change("INACTIVE", self.today, by, reason, allowed_from={"ACTIVE"})
        self._log(by, "DEACTIVATE_BENEFICIARY", beneficiary.beneficiary_id, reason)

    def initiate_transfer(self, account, beneficiary, amount, initiated_by, channel="DIGITAL",
                          standing_order=None):
        """Operation: start a transfer. It may post, wait for a second signatory,
        be held for review, or fail - and every outcome is kept."""
        txn = TransferPayment(amount, self.today, account, beneficiary, initiated_by, channel)
        self.transactions[txn.txn_id] = txn
        try:
            if beneficiary.status.current != "ACTIVE" or beneficiary.owner not in account.holders:
                raise BankingError(f"beneficiary {beneficiary.nickname} not usable on {account.number}")
            if standing_order:   # authority was checked when the instruction was given
                txn.standing_order, txn.mandate_used = standing_order, standing_order.mandate_used
            else:
                txn.mandate_used = self._check_authority(account, initiated_by, "PAYMENTS", txn.amount)
            account.check_debit(txn.amount, self.today)
        except BankingError as e:
            return self._fail(txn, e)
        if txn.mandate_used and not standing_order and txn.mandate_used.needs_second_signatory(txn.amount):
            txn.status.change("AWAITING_AUTHORISATION", self.today, initiated_by.name,
                              f"above {fmt(txn.mandate_used.dual_control_above)}: second signatory needed")
            self._log(initiated_by.name, "TXN_PENDING_2ND_SIGNATORY", txn.txn_id, fmt(txn.amount))
            return txn
        return self._complete_transfer(txn)

    def authorise_payment(self, txn, person):
        """Operation: a second signatory approves a pending payment (dual control)."""
        if txn.status.current != "AWAITING_AUTHORISATION":
            raise InvalidStateError(f"{txn.txn_id} is {txn.status.current}")
        if person is txn.initiated_by:
            raise AuthorityError("the initiator cannot also be the second signatory")
        mandate = self._check_authority(txn.source_account, person, "PAYMENTS", txn.amount)
        if mandate is None:
            raise AuthorityError(f"{person.name} holds no signing mandate for this organisation")
        txn.authorisations.append(PaymentAuthorisation(txn, person, mandate, self.today))
        txn.status.change("AUTHORISED", self.today, person.name, "second signatory")
        self._log(person.name, "AUTHORISE_PAYMENT", txn.txn_id, mandate.mandate_id)
        try:
            txn.source_account.check_debit(txn.amount, self.today)
        except BankingError as e:
            return self._fail(txn, e)
        if isinstance(txn, BillPayment):
            return self._complete_bill(txn)
        return self._complete_transfer(txn)

    def cancel_pending_payment(self, txn, person, reason):
        """Operation: withdraw a payment still waiting for its second signatory.
        Only the initiator or another signatory with a live mandate may cancel."""
        if txn.status.current != "AWAITING_AUTHORISATION":
            raise InvalidStateError(f"{txn.txn_id} is {txn.status.current}")
        if person is not txn.initiated_by:
            self._check_authority(txn.source_account, person, "PAYMENTS", txn.amount)
        txn.status.change("CANCELLED", self.today, person.name, reason)
        self._log(person.name, "CANCEL_PAYMENT", txn.txn_id, reason)

    def _complete_transfer(self, txn):
        """Post the transfer, or hold it for review if it is large."""
        account, standing_order = txn.source_account, txn.standing_order
        if txn.amount >= self.LARGE_TRANSFER_REVIEW and not standing_order:
            txn.hold = AccountHold(account, txn.amount, "large transfer under review", self.today, txn)
            account.holds.append(txn.hold)
            txn.status.change("HELD_FOR_REVIEW", self.today, "monitoring", "above review threshold")
            alert = self.raise_fraud_alert(account.holders[0], "LARGE_FIRST_TIME_TRANSFER", txn)
            self._log("monitoring", "TXN_HELD", txn.txn_id, f"{fmt(txn.amount)}; {alert.case_id}")
            return txn
        txn.post([(account, -txn.amount), (self.gl["2100"], txn.amount)], self.today, txn.initiated_by.name)
        self._log(txn.initiated_by.name, "TRANSFER", txn.txn_id,
                  f"{fmt(txn.amount)} to {txn.beneficiary.nickname}")
        return txn

    def release_transaction(self, txn, by, note):
        """Operation: compliance releases a held transfer, which then posts."""
        self._require_role(by, self.COMPLIANCE_ROLES, "release held payments")
        if txn.status.current != "HELD_FOR_REVIEW":
            raise InvalidStateError(f"{txn.txn_id} is {txn.status.current}")
        txn.hold.release(self.today)
        try:
            txn.source_account.check_debit(txn.amount, self.today)
        except BankingError as e:
            return self._fail(txn, e)
        txn.status.change("RELEASED", self.today, by, note)
        txn.post([(txn.source_account, -txn.amount), (self.gl["2100"], txn.amount)], self.today, by)
        self._log(by, "RELEASE_TXN", txn.txn_id, note)
        return txn

    def reject_held_transaction(self, txn, by, reason):
        """Operation: compliance rejects a held transfer; the hold is released."""
        self._require_role(by, self.COMPLIANCE_ROLES, "reject held payments")
        if txn.status.current != "HELD_FOR_REVIEW":
            raise InvalidStateError(f"{txn.txn_id} is {txn.status.current}")
        txn.hold.release(self.today)
        txn.status.change("REJECTED", self.today, by, reason)
        self._log(by, "REJECT_TXN", txn.txn_id, reason)

    def reverse_transaction(self, original, amount, reason, by):
        """Operation: reverse all or part of a posted transaction with NEW counter-entries.
        The original stays, marked REVERSED or PARTIALLY_REVERSED."""
        self._require_role(by, self.REVERSAL_ROLES, "reverse transactions")
        if isinstance(original, Reversal):
            raise InvalidStateError("a reversal cannot itself be reversed; post a new transaction")
        if original.status.current not in ("POSTED", "PARTIALLY_REVERSED"):
            raise InvalidStateError(f"{original.txn_id} is {original.status.current}")
        amount = money(amount if amount is not None else original.net_amount)
        if amount <= 0:
            raise BankingError("reversal amount must be positive")
        if amount > original.net_amount:
            raise BankingError(f"only {fmt(original.net_amount)} of {original.txn_id} is reversible")
        approval = Approval(by, self.today, "REVERSE", original.txn_id, reason)
        self.approvals.append(approval)
        rev = Reversal(amount, self.today, original, reason, approval)
        ratio = amount / original.amount
        legs = [(e.account, money(-e.amount * ratio)) for e in original.entries]
        drift = sum((x for _, x in legs), ZERO)
        legs[-1] = (legs[-1][0], legs[-1][1] - drift)      # absorb rounding in the bank-side leg
        rev.post(legs, self.today, by)
        original.reversals.append(rev)
        self.transactions[rev.txn_id] = rev
        new_status = "REVERSED" if original.net_amount == 0 else "PARTIALLY_REVERSED"
        original.status.change(new_status, self.today, by, reason)
        self._log(by, "REVERSE", original.txn_id, f"{fmt(amount)} via {rev.txn_id}: {reason}")
        return rev

    def repost_card_payment(self, original, corrected_amount, reason, by):
        """Operation: correct a card payment = full reversal + a NEW linked record.
        The original is never edited."""
        if not isinstance(original, CardPayment):
            raise BankingError("only card payments are re-presented by the card scheme")
        self.reverse_transaction(original, None, reason, by)
        new = CardPayment(corrected_amount, original.initiated_on, original.card, original.merchant)
        new.mandate_used, new.supersedes = original.mandate_used, original
        original.superseded_by = new
        new.post([(original.source_account, -new.amount), (self.gl["2200"], new.amount)], self.today, by)
        original.card.payments.append(new)
        self.transactions[new.txn_id] = new
        self._log(by, "REPOST", new.txn_id, f"replaces {original.txn_id}: {reason}")
        return new

    def create_standing_order(self, account, beneficiary, amount, day, created_by):
        """Operation: set up a monthly transfer (authority checked now, once)."""
        if beneficiary.owner not in account.holders:
            raise BankingError(f"beneficiary {beneficiary.nickname} not usable on {account.number}")
        mandate = self._check_authority(account, created_by, "PAYMENTS", money(amount))
        so = StandingOrder(account, beneficiary, amount, day, self.today, created_by, mandate)
        self.standing_orders[so.order_id] = so
        self._log(created_by.name, "CREATE_SO", so.order_id, f"{fmt(so.amount)} on day {day}")
        return so

    def cancel_standing_order(self, so, by, reason):
        """Operation: stop a standing order (its past payments stay)."""
        so.status.change("CANCELLED", self.today, by, reason, allowed_from={"ACTIVE"})
        self._log(by, "CANCEL_SO", so.order_id, reason)

    def run_standing_orders(self):
        """Batch: pay every standing order due today; failures notify the customer."""
        for so in self.standing_orders.values():
            if so.status.current == "ACTIVE" and so.next_due <= self.today:
                txn = self.initiate_transfer(so.account, so.beneficiary, so.amount,
                                             so.created_by, "STANDING_ORDER", standing_order=so)
                so.payments.append(txn)
                if txn.status.current == "FAILED":
                    for h in so.account.holders:
                        self._notify(h, "SO_FAILED", f"{so.order_id} not paid: {txn.failure_reason}")
                so.next_due = add_months(so.next_due, 1)

    # ---------------------------------------------------------------- cards
    def issue_card(self, product, account, cardholder, by, daily_limit=None, replaces=None):
        """Operation: issue a debit card to a holder or a person with a CARD mandate.
        A replacement for an existing customer is allowed even if the card product
        is no longer sold to new customers."""
        self._require_role(by, self.CARD_ROLES | self.BRANCH_ROLES, "issue cards")
        if product.category != "DEBIT_CARD":
            raise ProductNotAvailable(f"{product.name} is not a card product")
        if replaces is None and not product.can_sell(self.today):
            raise ProductNotAvailable(f"{product.name} not available to new cardholders")
        if account.status.current != "ACTIVE":
            raise InvalidStateError(f"{account.number} is {account.status.current}")
        self._check_authority(account, cardholder, "CARD")
        limit = daily_limit or product.terms_on(self.today).get("default_daily_limit")
        card = IssuedCard(product, account, cardholder, self.today, limit, replaces)
        self.cards[card.card_id] = card
        self._log(by, "ISSUE_CARD", card.card_id, f"{card} limit {fmt(money(limit))}")
        return card

    def card_purchase(self, card, merchant, amount, channel="POS", country="PK", merchant_category="RETAIL"):
        """Operation: a card payment from the card network; declined ones are kept.
        channel is POS, ONLINE or ATM; country is where the merchant is."""
        txn = CardPayment(amount, self.today, card, merchant, channel, country, merchant_category)
        card.payments.append(txn)
        self.transactions[txn.txn_id] = txn
        try:
            if card.status.current != "ACTIVE":
                raise RestrictionViolation(f"card {card.card_id} is {card.status.current}")
            if self.today > card.expires_on:
                raise RestrictionViolation(f"card {card.card_id} expired on {card.expires_on}")
            for control in card.controls:
                if control.blocks(channel, country, merchant_category, self.today):
                    raise RestrictionViolation(f"card control {control}")
            if card.spent_on(self.today) + txn.amount > card.daily_limit_on(self.today):
                raise BankingError(f"daily limit {fmt(card.daily_limit_on(self.today))} exceeded")
            txn.mandate_used = self._check_authority(card.account, card.cardholder, "CARD")
            card.account.check_debit(txn.amount, self.today)
        except BankingError as e:
            return self._fail(txn, e, status="DECLINED")
        txn.post([(card.account, -txn.amount), (self.gl["2200"], txn.amount)], self.today, "card-network")
        self._log(card.cardholder.name, "CARD_PAYMENT", txn.txn_id, f"{fmt(txn.amount)} at {merchant}")
        return txn

    def report_card(self, card, kind, reported_by):
        """Operation: block a card as LOST / STOLEN / DAMAGED, opening a service request."""
        statuses = {"LOST": "BLOCKED_LOST", "STOLEN": "BLOCKED_STOLEN", "DAMAGED": "BLOCKED_DAMAGED"}
        if kind not in statuses:
            raise BankingError(f"unknown card report {kind}")
        card.status.change(statuses[kind], self.today, reported_by.name, f"reported {kind.lower()}",
                           allowed_from={"ACTIVE"})
        card.events.append((self.today, f"reported {kind} by {reported_by.name}"))
        request = self.raise_service_request(card.account.holders[0], f"BLOCK_CARD_{kind}",
                                             reported_by, "PHONE", "card-hotline", related=card)
        self._log(reported_by.name, "CARD_REPORTED", card.card_id, f"{kind}; {request.case_id}")
        return request

    def replace_card(self, old, by, daily_limit=None):
        """Operation: issue a new card for a blocked one, linked both ways."""
        if old.status.current == "ACTIVE":
            raise InvalidStateError("block or report the card before replacing it")
        if old.replaced_by:
            raise InvalidStateError(f"{old.card_id} already replaced by {old.replaced_by.card_id}")
        new = self.issue_card(old.product, old.account, old.cardholder, by, daily_limit, replaces=old)
        old.replaced_by = new
        old.events.append((self.today, f"replaced by {new.card_id}"))
        for case in self.cases.values():
            if isinstance(case, ServiceRequest) and case.related is old and case.is_open:
                case.close(f"replacement {new.card_id} issued", self.today, by)
        self._log(by, "REPLACE_CARD", old.card_id, f"-> {new.card_id}")
        return new

    def record_card_found(self, card, by, note):
        """Operation: a lost/stolen card turned up; it is destroyed, never reused."""
        card.status.change("DESTROYED", self.today, by, note,
                           allowed_from={"BLOCKED_LOST", "BLOCKED_STOLEN", "BLOCKED_DAMAGED"})
        card.events.append((self.today, f"found: {note}"))
        self._log(by, "CARD_FOUND", card.card_id, note)

    def reactivate_card(self, card, by):
        """Operation: unblock a card reported LOST that was not replaced. Anything else is refused."""
        if card.replaced_by or card.status.current not in ("BLOCKED_LOST",):
            raise InvalidStateError(f"{card.card_id} is {card.status.current}"
                                    + (f" and replaced by {card.replaced_by.card_id}" if card.replaced_by else ""))
        card.status.change("ACTIVE", self.today, by, "reactivated")
        self._log(by, "REACTIVATE_CARD", card.card_id)

    def change_card_limit(self, card, new_limit, by):
        """Operation: change a card's daily limit from today (old limits kept)."""
        self._require_role(by, self.CARD_ROLES, "change card limits")
        if money(new_limit) <= 0:
            raise BankingError("card limit must be positive")
        card.limit_history.append((self.today, money(new_limit)))
        self._log(by, "CARD_LIMIT", card.card_id, fmt(money(new_limit)))

    # ---------------------------------------------------------------- financing
    def submit_financing_application(self, applicant, product, amount, months, purpose, submitted_by):
        """Operation: apply for financing (an organisation needs a BORROWING mandate)."""
        if not applicant.relationship or applicant.relationship.status.current != "ACTIVE":
            raise KycIncomplete(f"{applicant.name} is not a customer")
        if product.category != "FINANCING":
            raise ProductNotAvailable(f"{product.name} is not a financing product")
        if isinstance(applicant, Organization):
            applicant.find_mandate(submitted_by, "BORROWING", money(amount), self.today)
        elif submitted_by is not applicant:
            raise AuthorityError("an individual applies for their own financing")
        if not product.can_sell(self.today):
            raise ProductNotAvailable(product.name)
        app = FinancingApplication(applicant, product, amount, months, purpose, self.today, submitted_by)
        self.applications[app.application_id] = app
        self._log(submitted_by.name, "APPLY_FINANCING", app.application_id, f"{fmt(app.requested_amount)}")
        return app

    def decide_application(self, app, by, approve, amount=None, annual_rate=None, conditions=()):
        """Operation: credit decision within the decider's delegated limit."""
        assignment = self._require_role(by, self.CREDIT_ROLES, "decide credit")
        if app.status.current != "SUBMITTED":
            raise InvalidStateError(f"{app.application_id} is {app.status.current}")
        if approve:
            approved = money(amount or app.requested_amount)
            if approved > app.requested_amount:
                raise BankingError("cannot approve more than was requested")
            if annual_rate is None:
                raise BankingError("an approval needs an annual rate")
            limit = self.CREDIT_LIMITS[assignment.role]
            if approved > limit:
                raise AuthorityError(f"{by} ({assignment.role}) may approve up to {fmt(limit)}; "
                                     f"{fmt(approved)} needs a higher authority")
        app.decision = Approval(by, self.today, "APPROVE" if approve else "DECLINE", app.application_id)
        self.approvals.append(app.decision)
        if not approve:
            app.status.change("DECLINED", self.today, by, "declined")
        else:
            app.approved_amount = approved
            app.annual_rate = Decimal(str(annual_rate))
            app.conditions = [ApprovalCondition(app, c) for c in conditions]
            status = "APPROVED_WITH_CONDITIONS" if conditions else "APPROVED"
            app.status.change(status, self.today, by, f"{fmt(app.approved_amount)} @ {annual_rate}")
        self._log(by, "CREDIT_DECISION", app.application_id, str(app.decision))
        return app.decision

    def satisfy_condition(self, condition, evidence, by):
        """Operation: record that an approval condition has been met."""
        if condition.is_met():
            raise InvalidStateError(f"{condition.condition_id} already met on {condition.satisfied_on}")
        condition.satisfied_on, condition.satisfied_by, condition.evidence = self.today, str(by), evidence
        self._log(by, "CONDITION_MET", condition.condition_id, condition.description)

    def attach_application_document(self, app, description, by):
        """Operation: file a supporting document on an application."""
        app.supporting_documents.append((self.today, description, str(by)))
        self._log(by, "APP_DOCUMENT", app.application_id, description)

    def disburse_financing(self, app, settlement_account, first_due, by):
        """Operation: create the agreement and pay out, once every condition is met."""
        assignment = self._require_role(by, self.CREDIT_ROLES | {"OPERATIONS_OFFICER"}, "disburse")
        if app.status.current not in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
            raise InvalidStateError(f"{app.application_id} is {app.status.current}")
        pending = app.outstanding_conditions()
        if pending:
            self._log(by, "DISBURSE_BLOCKED", app.application_id, "; ".join(c.description for c in pending))
            raise BankingError("conditions outstanding: " + "; ".join(c.description for c in pending))
        if app.applicant not in settlement_account.holders:
            raise BankingError(f"{settlement_account.number} is not held by {app.applicant.name}")
        if first_due <= self.today:
            raise BankingError("the first installment must fall after disbursement")
        settlement_account.ensure_usable("CREDIT", self.today)
        fin = FinancingAgreement(app, self.today, assignment.branch, by, settlement_account)
        fin.build_schedule(fin.principal, app.annual_rate, app.term_months, first_due, self.today, "original")
        approval = Approval(by, self.today, "DISBURSE", fin.number)
        self.approvals.append(approval)
        dsb = LoanDisbursement(fin.principal, self.today, fin, settlement_account, approval)
        dsb.post([(settlement_account, dsb.amount), (self.gl["1100"], -dsb.amount)], self.today, by)
        fin.transactions.append(dsb)
        app.agreement = fin
        app.status.change("DISBURSED", self.today, by, fin.number)
        self.arrangements[fin.number] = fin
        self.transactions[dsb.txn_id] = dsb
        self._log(by, "DISBURSE", fin.number, f"{fmt(fin.principal)} to {settlement_account.number}")
        return fin

    def repay_financing(self, agreement, amount, from_account, purpose="installment"):
        """Operation: repay financing (interest first). Every check runs BEFORE any
        installment is touched, so a refused repayment changes nothing."""
        txn = LoanRepayment(amount, self.today, agreement, from_account, purpose)
        self.transactions[txn.txn_id] = txn
        try:
            agreement.ensure_usable("CREDIT", self.today)
            if txn.amount > agreement.outstanding_total():
                raise BankingError(f"overpayment: only {fmt(agreement.outstanding_total())} is outstanding")
            from_account.check_debit(txn.amount, self.today)
        except BankingError as e:
            return self._fail(txn, e)
        txn.allocations, _ = agreement.allocate(txn.amount)
        principal = sum((p for _, _, p in txn.allocations), ZERO)
        interest = sum((i for _, i, _ in txn.allocations), ZERO)
        txn.post([(from_account, -txn.amount), (self.gl["1100"], principal),
                  (self.gl["4100"], interest)], self.today)
        agreement.transactions.append(txn)
        self._log("system", "REPAYMENT", agreement.number, fmt(txn.amount))
        return txn

    def run_arrears_check(self):
        """Batch: move agreements into/out of arrears and open collections cases."""
        for fin in self.arrangements.values():
            if not isinstance(fin, FinancingAgreement) or fin.status.current not in fin.USABLE_STATUSES:
                continue
            overdue = fin.overdue_installments(self.today)
            if overdue and fin.status.current == "ACTIVE":
                fin.status.change("IN_ARREARS", self.today, "arrears-batch", f"{len(overdue)} overdue")
                case = CollectionsCase(fin.holders[0], self.today, fin,
                                       sum((i.outstanding for i in overdue), ZERO))
                self.cases[case.case_id] = case
                self._notify(fin.holders[0], "ARREARS", f"{fin.number} has an overdue installment")
                self._log("arrears-batch", "ARREARS", fin.number, case.case_id)
            elif not overdue and fin.status.current == "IN_ARREARS":
                fin.status.change("ACTIVE", self.today, "arrears-batch", "arrears cleared")
        for case in self.cases.values():
            if not isinstance(case, CollectionsCase):
                continue
            for promise in case.promises:
                if promise.status.current == "OPEN" and promise.due_on < self.today:
                    kept = not case.agreement.overdue_installments(self.today)
                    promise.status.change("KEPT" if kept else "BROKEN", self.today, "arrears-batch",
                                          "arrears cleared" if kept else "still overdue after promised date")
                    if not kept:
                        self._notify(case.subject, "BROKEN_PROMISE",
                                     f"{case.agreement.number}: promised payment not received")
                    self._log("arrears-batch", "PROMISE_" + promise.status.current, case.case_id,
                              fmt(promise.amount))

    def restructure_financing(self, fin, months, annual_rate, first_due, reason, by):
        """Operation: supersede the schedule. Paid installments stay PAID on the old
        version; overdue interest is capitalised and booked."""
        self._require_role(by, self.CREDIT_ROLES, "restructure financing")
        if fin.status.current not in fin.USABLE_STATUSES:
            raise InvalidStateError(f"{fin.number} is {fin.status.current}")
        if first_due <= self.today:
            raise BankingError("the first restructured installment must be in the future")
        capitalised = fin.overdue_interest(self.today)
        principal = fin.outstanding_principal() + capitalised
        if principal <= 0:
            raise InvalidStateError(f"{fin.number} has nothing left to restructure")
        approval = Approval(by, self.today, "RESTRUCTURE", fin.number, reason)
        self.approvals.append(approval)
        fin.restructure_approvals.append(approval)
        sched = fin.build_schedule(principal, Decimal(str(annual_rate)), months, first_due,
                                   self.today, reason, capitalised)
        if capitalised > 0:
            cap = InterestCapitalisation(capitalised, self.today, fin, approval)
            cap.post([(self.gl["1100"], -capitalised), (self.gl["4100"], capitalised)], self.today, by)
            fin.transactions.append(cap)
            self.transactions[cap.txn_id] = cap
        if fin.status.current == "IN_ARREARS":
            fin.status.change("ACTIVE", self.today, by, "restructured")
        for case in self.cases.values():
            if isinstance(case, CollectionsCase) and case.agreement is fin and case.is_open:
                case.close("RESTRUCTURED", self.today, by)
        self._log(by, "RESTRUCTURE", fin.number, f"v{sched.version}: {fmt(principal)} over {months}m")
        return sched

    def settle_financing(self, fin, from_account, by):
        """Operation: early settlement - principal plus interest already due; future interest waived."""
        self._require_role(by, self.CREDIT_ROLES | {"OPERATIONS_OFFICER"}, "settle financing")
        if fin.status.current not in fin.USABLE_STATUSES:
            raise InvalidStateError(f"{fin.number} is {fin.status.current}")
        principal, interest = fin.settlement_quote(self.today)
        from_account.check_debit(principal + interest, self.today)   # fail before changing anything
        waived = []
        for inst in fin.current_schedule.installments:
            if inst.due_on > self.today and inst.outstanding > 0:
                inst.interest_waived = inst.interest - inst.interest_paid
                waived.append(inst)
        txn = self.repay_financing(fin, principal + interest, from_account, "early settlement")
        if txn.status.current != "POSTED":
            for inst in waived:                                   # undo the waiver
                inst.interest_waived = ZERO
            return txn
        fin.current_schedule.status.change("CLOSED", self.today, by, "settled")
        fin.status.change("SETTLED", self.today, by, "early settlement")
        for case in self.cases.values():
            if isinstance(case, CollectionsCase) and case.agreement is fin and case.is_open:
                case.close("SETTLED", self.today, by)
        self._log(by, "SETTLE", fin.number, fmt(txn.amount))
        return txn

    # ---------------------------------------------------------------- cases
    def raise_fraud_alert(self, subject, rule, transaction=None):
        """Operation (monitoring): raise an automatic alert."""
        alert = FraudAlert(subject, self.today, rule, transaction)
        self.cases[alert.case_id] = alert
        self._log("monitoring", "FRAUD_ALERT", alert.case_id, rule)
        return alert

    def open_investigation(self, subject, summary, by, linked=()):
        """Operation: compliance opens an investigation, optionally linked to alerts."""
        self._require_role(by, self.COMPLIANCE_ROLES, "open investigations")
        inv = ComplianceInvestigation(subject, self.today, by, summary, "HIGH")
        inv.assign(by, self.today)
        for c in linked:
            inv.link(c)
        self.cases[inv.case_id] = inv
        self._log(by, "OPEN_INVESTIGATION", inv.case_id, summary)
        return inv

    def add_evidence(self, case, description, source, snapshot, by):
        """Operation: attach a frozen snapshot of facts to a case."""
        if not case.is_open:
            raise InvalidStateError(f"{case.case_id} is closed")
        ev = CaseEvidence(description, self.today, by, source, snapshot)
        case.evidence.append(ev)
        self._log(by, "EVIDENCE", case.case_id, description)
        return ev

    def impose_restriction(self, target, scope, reason, by, case=None):
        """Operation: compliance restricts a party or an account from today."""
        self._require_role(by, self.COMPLIANCE_ROLES, "restrict customers")
        if case is not None and not isinstance(case, RiskCase):
            raise BankingError("only a risk case can impose a restriction")
        r = Restriction(target, scope, reason, self.today, by, case)
        target.restrictions.append(r)
        if case:
            case.restrictions.append(r)
        self._log(by, "RESTRICT", r.restriction_id, f"{scope} on {r.target_label}: {reason}")
        return r

    def lift_restriction(self, restriction, reason, by):
        """Operation: lift a restriction from today; its period stays on record."""
        self._require_role(by, self.COMPLIANCE_ROLES, "lift restrictions")
        restriction.lift(self.today, by, reason)
        self._log(by, "LIFT_RESTRICTION", restriction.restriction_id, reason)

    def raise_service_request(self, party, request_type, contact, channel, by, related=None):
        """Operation: record a routine customer request."""
        sr = ServiceRequest(party, self.today, by, request_type, channel, contact, related)
        self.cases[sr.case_id] = sr
        self._log(by, "SERVICE_REQUEST", sr.case_id, request_type)
        return sr

    def log_complaint(self, party, summary, channel, contact, category, by):
        """Operation: record a customer complaint."""
        c = Complaint(party, self.today, by, summary, channel, contact, category)
        self.cases[c.case_id] = c
        self._log(by, "COMPLAINT", c.case_id, summary)
        return c

    def open_dispute(self, txn, amount, contact, channel, by):
        """Operation: a customer disputes a posted payment (one open dispute at a time)."""
        if not isinstance(txn, CustomerPayment):
            raise BankingError(f"{txn.txn_id} is not a customer payment and cannot be disputed")
        if txn.status.current not in ("POSTED", "PARTIALLY_REVERSED"):
            raise InvalidStateError(f"{txn.txn_id} is {txn.status.current}")
        if money(amount) <= 0 or money(amount) > txn.net_amount:
            raise BankingError(f"disputed amount must be between 0 and {fmt(txn.net_amount)}")
        if any(d.is_open for d in txn.disputes):
            raise InvalidStateError(f"{txn.txn_id} already has an open dispute")
        d = Dispute(txn.source_account.holders[0], self.today, by, txn, amount, channel, contact)
        txn.disputes.append(d)
        self.cases[d.case_id] = d
        self._log(by, "OPEN_DISPUTE", d.case_id, f"{txn.txn_id} {fmt(d.disputed_amount)}")
        return d

    def resolve_dispute(self, dispute, outcome, refund, by):
        """Operation: close a dispute, refunding (reversing) up to the disputed amount."""
        if not dispute.is_open:
            raise InvalidStateError(f"{dispute.case_id} already closed")
        if refund:
            if money(refund) > dispute.disputed_amount:
                raise BankingError(f"refund exceeds the disputed {fmt(dispute.disputed_amount)}")
            dispute.refund = self.reverse_transaction(dispute.transaction, refund,
                                                      f"dispute {dispute.case_id} {outcome}", by)
        dispute.close(outcome, self.today, by)
        self._log(by, "RESOLVE_DISPUTE", dispute.case_id, outcome)

    def close_case(self, case, outcome, by):
        """Operation: close any case (a risk case refuses while its restrictions are live)."""
        case.close(outcome, self.today, by)
        self._log(by, "CLOSE_CASE", case.case_id, outcome)

    # ---------------------------------------------------------------- own-account transfers & term deposits
    def transfer_between_accounts(self, source, target, amount, initiated_by, channel="DIGITAL"):
        """Operation: move money between two accounts at this bank that the same customer
        controls. Needs PAYMENTS authority on the source; the target must accept credits."""
        txn = OwnAccountTransfer(amount, self.today, source, target, initiated_by, channel)
        self.transactions[txn.txn_id] = txn
        try:
            if set(source.holders) != set(target.holders):
                raise BankingError("own-account transfers need the same holders on both accounts")
            txn.mandate_used = self._check_authority(source, initiated_by, "PAYMENTS", txn.amount)
            source.check_debit(txn.amount, self.today)
            target.ensure_usable("CREDIT", self.today)
        except BankingError as e:
            return self._fail(txn, e)
        txn.post([(source, -txn.amount), (target, txn.amount)], self.today, initiated_by.name)
        self._log(initiated_by.name, "OWN_TRANSFER", txn.txn_id,
                  f"{fmt(txn.amount)} {source.number} -> {target.number}")
        return txn

    def _pay_out_term_deposit(self, deposit, by, reason):
        """Move a term deposit's balance to its payout account and close it."""
        balance = deposit.ledger_balance()
        if balance > 0:
            t = InternalTransfer(balance, self.today, f"payout of {deposit.number}: {reason}")
            t.post([(deposit, -balance), (deposit.payout_account, balance)], self.today, by)
            self.transactions[t.txn_id] = t
        deposit.status.change("CLOSED", self.today, by, reason)

    def run_term_deposit_maturity(self):
        """Batch: on maturity pay principal plus term interest to the payout account."""
        for dep in list(self.arrangements.values()):
            if (isinstance(dep, FixedTermDeposit) and dep.status.current == "ACTIVE"
                    and dep.maturity_on <= self.today):
                interest = dep.maturity_interest()
                if interest > 0:
                    txn = InterestCredit(interest, self.today, dep.payout_account, dep.annual_rate,
                                         f"term deposit {dep.number} at maturity")
                    txn.post([(dep.payout_account, interest), (self.gl["5000"], -interest)], self.today)
                    self.transactions[txn.txn_id] = txn
                self._pay_out_term_deposit(dep, "system", "matured")
                self._log("system", "TERM_DEPOSIT_MATURED", dep.number, f"interest {fmt(interest)}")

    def break_term_deposit(self, deposit, by, reason):
        """Operation: break a term deposit early - interest is forfeited, a penalty is
        charged under the pinned terms, and the rest goes to the payout account."""
        self._require_role(by, self.BRANCH_ROLES, "break term deposits")
        if not isinstance(deposit, FixedTermDeposit) or deposit.status.current != "ACTIVE":
            raise InvalidStateError(f"{deposit.number} is not an active term deposit")
        if self.today >= deposit.maturity_on:
            raise InvalidStateError(f"{deposit.number} has matured; it pays out automatically")
        penalty = money(deposit.ledger_balance()
                        * Decimal(str(deposit.terms.get("early_break_penalty", "0.01"))))
        if penalty > 0:
            self.charge_fee(deposit, "EARLY_BREAK_PENALTY", penalty, by)
        self._pay_out_term_deposit(deposit, by, f"broken early: {reason}")
        self._log(by, "BREAK_TERM_DEPOSIT", deposit.number, f"penalty {fmt(penalty)}")
        return penalty

    # ---------------------------------------------------------------- bill payments
    def register_biller(self, code, name, category):
        """Operation: add a biller the bank collects payments for."""
        if code in self.billers:
            raise InvalidStateError(f"biller code {code} already used")
        b = Biller(code, name, category, self.today)
        self.billers[code] = b
        self._log("payments-ops", "REGISTER_BILLER", code, str(b))
        return b

    def deactivate_biller(self, biller, reason):
        """Operation: stop accepting payments for a biller; past payments stay."""
        biller.status.change("INACTIVE", self.today, "payments-ops", reason, allowed_from={"ACTIVE"})
        self._log("payments-ops", "DEACTIVATE_BILLER", biller.code, reason)

    def pay_bill(self, account, biller, consumer_reference, amount, initiated_by, channel="DIGITAL"):
        """Operation: pay a bill. Same authority, restriction and dual-control rules as a
        transfer; refused payments are kept as FAILED."""
        txn = BillPayment(amount, self.today, account, biller, consumer_reference, initiated_by, channel)
        self.transactions[txn.txn_id] = txn
        try:
            if biller.status.current != "ACTIVE":
                raise BankingError(f"{biller.name} no longer accepts payments")
            if not str(consumer_reference).strip():
                raise BankingError("a bill payment needs the consumer reference")
            txn.mandate_used = self._check_authority(account, initiated_by, "PAYMENTS", txn.amount)
            account.check_debit(txn.amount, self.today)
        except BankingError as e:
            return self._fail(txn, e)
        if txn.mandate_used and txn.mandate_used.needs_second_signatory(txn.amount):
            txn.status.change("AWAITING_AUTHORISATION", self.today, initiated_by.name,
                              "second signatory needed")
            self._log(initiated_by.name, "TXN_PENDING_2ND_SIGNATORY", txn.txn_id, fmt(txn.amount))
            return txn
        return self._complete_bill(txn)

    def _complete_bill(self, txn):
        txn.post([(txn.source_account, -txn.amount), (self.gl["2300"], txn.amount)], self.today,
                 txn.initiated_by.name)
        self._log(txn.initiated_by.name, "BILL_PAYMENT", txn.txn_id,
                  f"{fmt(txn.amount)} to {txn.biller.name} ref {txn.consumer_reference}")
        return txn

    # ---------------------------------------------------------------- card controls
    def add_card_control(self, card, control_type, by, value=None):
        """Operation: switch on a card control. The cardholder or card operations may do it."""
        if isinstance(by, Employee):
            self._require_role(by, self.CARD_ROLES, "set card controls")
        elif by is not card.cardholder:
            raise AuthorityError(f"only the cardholder or card operations may control {card.card_id}")
        if card.status.current != "ACTIVE":
            raise InvalidStateError(f"{card.card_id} is {card.status.current}")
        if any(c.control_type == control_type and c.value == value and c.period.end is None
               for c in card.controls):
            raise InvalidStateError(f"{control_type} is already on for {card.card_id}")
        control = CardControl(card, control_type, value, self.today, by)
        card.controls.append(control)
        self._log(by, "CARD_CONTROL_ON", card.card_id, str(control))
        return control

    def remove_card_control(self, control, by):
        """Operation: switch a card control off from today (its period stays on record)."""
        if isinstance(by, Employee):
            self._require_role(by, self.CARD_ROLES, "set card controls")
        elif by is not control.card.cardholder:
            raise AuthorityError("only the cardholder or card operations may change card controls")
        control.period.close(self.today)
        control.removed_by = str(by)
        self._log(by, "CARD_CONTROL_OFF", control.card.card_id, str(control))

    # ---------------------------------------------------------------- collections
    def assign_case(self, case, employee, by):
        """Operation: give a case to an employee whose role fits the case type."""
        self._require_role(employee, case.handler_roles(), f"work {case.kind} cases")
        if not case.is_open:
            raise InvalidStateError(f"{case.case_id} is closed")
        case.assign(employee, self.today)
        self._log(by, "ASSIGN_CASE", case.case_id, str(employee))

    def record_collections_contact(self, case, by, outcome, promise_amount=None, promise_date=None):
        """Operation: collections staff record a call with the customer and, optionally,
        a promise to pay that the arrears batch later marks KEPT or BROKEN."""
        self._require_role(by, self.COLLECTIONS_ROLES, "record collections contacts")
        if not isinstance(case, CollectionsCase) or not case.is_open:
            raise InvalidStateError("contacts are recorded on an open collections case")
        case.add_note(outcome, self.today, by)
        promise = None
        if promise_amount is not None:
            if promise_date is None or promise_date <= self.today:
                raise BankingError("a promise to pay needs a future date")
            promise = PromiseToPay(case, promise_amount, promise_date, self.today, by)
            case.promises.append(promise)
        self._log(by, "COLLECTIONS_CONTACT", case.case_id,
                  outcome + (f"; promise {fmt(promise.amount)} by {promise.due_on}" if promise else ""))
        return promise

    # ---------------------------------------------------------------- retention, archive, deletion
    def archive_record(self, record, by):
        """Operation: move a finished record (closed account, settled financing, closed case,
        ended relationship) out of the working lists. Nothing is removed."""
        finished = {Arrangement: ("CLOSED", "SETTLED"), Case: ("CLOSED",), CustomerRelationship: ("ENDED",)}
        kind = next((k for k in finished if isinstance(record, k)), None)
        if kind is None:
            raise BankingError(f"{type(record).__name__} records are not archived")
        if record.status.current not in finished[kind]:
            raise InvalidStateError(f"only finished records can be archived; this one is {record.status.current}")
        if record.archived_on is not None:
            raise InvalidStateError(f"already archived on {record.archived_on}")
        record.archived_on = self.today
        self._log(by, "ARCHIVE", self._label(record), f"retain until {self.retention_until(record)}")

    def retention_until(self, record):
        """Query: the earliest date the record could ever be destroyed (None while live)."""
        finished = [c.on for c in record.status.changes if c.status in ("CLOSED", "SETTLED", "ENDED")]
        if not finished:
            return None
        end = finished[-1]
        return date(end.year + self.RETENTION_YEARS, end.month, min(end.day, 28 if end.month == 2 else end.day))

    def request_deletion(self, record, by):
        """Operation: a request to delete a financial record is always refused and logged;
        the answer says what to do instead and how long the record must be kept."""
        until = self.retention_until(record)
        reason = ("still in use; close it first" if until is None
                  else f"must be retained until {until}; archive it instead")
        self._log(by, "DELETION_REFUSED", self._label(record), reason)
        raise InvalidStateError(f"{self._label(record)} cannot be deleted: {reason}")

    def delete_beneficiary(self, beneficiary, by):
        """Operation: delete a saved payee. Allowed only if no payment or standing order ever
        used it (nothing refers to it); otherwise it must be deactivated so history stays."""
        uses = [t.txn_id for t in self.transactions.values()
                if getattr(t, "beneficiary", None) is beneficiary]
        uses += [so.order_id for so in self.standing_orders.values() if so.beneficiary is beneficiary]
        if uses:
            raise InvalidStateError(f"{beneficiary.nickname} is used by {', '.join(uses)}; deactivate it instead")
        beneficiary.status.change("DELETED", self.today, by, "never used")
        self._log(by, "DELETE_BENEFICIARY", beneficiary.beneficiary_id, beneficiary.nickname)

    @staticmethod
    def _label(record):
        for attr in ("number", "case_id", "txn_id", "beneficiary_id"):
            if hasattr(record, attr):
                return getattr(record, attr)
        return f"relationship of {record.party.name}" if isinstance(record, CustomerRelationship) else str(record)

    def active_customers(self):
        """Query: customers in the working list (relationship active and not archived)."""
        return [p for p in self.parties.values() if p.relationship
                and p.relationship.status.current == "ACTIVE" and p.relationship.archived_on is None]

    def active_arrangements(self):
        """Query: arrangements in the working list (archived ones are kept but hidden)."""
        return [a for a in self.arrangements.values() if a.archived_on is None]

    # ---------------------------------------------------------------- audit and search
    def approvals_and_authority_audit(self, by, start, end):
        """Report for auditors and management: every staff approval with the role held at the
        time, and every change of customer-side authority, between two dates."""
        self._require_role(by, self.AUDIT_ROLES, "run audit reports")
        out = [f"Approvals by staff {start} to {end}:"]
        out += [f"  {a}" for a in self.approvals if start <= a.decided_on <= end]
        out.append("Authority changes (mandates, officers, second signatories, staff roles):")
        actions = {"GRANT_MANDATE", "REVOKE_MANDATE", "APPOINT_OFFICER", "END_OFFICER",
                   "AUTHORISE_PAYMENT", "ROLE_CHANGE"}
        out += [f"  {e.on} {e.action:<17} {e.subject:<9} by {e.actor}: {e.detail}"
                for e in self.audit if e.action in actions and start <= e.on <= end]
        self._log(by, "AUDIT_REVIEW", "approvals", f"{start} to {end}")
        return out

    def search_transactions(self, card=None, account=None, merchant=None, start=None, end=None,
                            kind=None, include_card_chain=True):
        """Query: find transactions. A card search covers every card in its replacement
        chain by default, so old cards' payments stay searchable after replacement."""
        cards = set(card.lineage() if include_card_chain else [card]) if card else None
        found = []
        for t in self.transactions.values():
            if cards is not None and getattr(t, "card", None) not in cards:
                continue
            if account is not None and account not in (getattr(t, "source_account", None),
                                                       getattr(t, "account", None),
                                                       getattr(t, "target_account", None)):
                continue
            if merchant and merchant.lower() not in str(getattr(t, "merchant", "")).lower():
                continue
            if start and t.initiated_on < start or end and t.initiated_on > end:
                continue
            if kind and not isinstance(t, kind):
                continue
            found.append(t)
        return found

    # ---------------------------------------------------------------- history & reporting
    def capacities_of(self, person):
        """Report: every capacity one person holds across the bank (one record, many roles)."""
        out = []
        if person.relationship:
            rm = person.relationship.manager_on(self.today)
            out.append(f"Customer since {person.relationship.since}"
                       + (f", relationship manager {rm}" if rm else ""))
        for a in self.arrangements.values():
            if person in a.holders:
                out.append(f"Holder of {a.number} {a.product.name} [{a.status.current}]")
        for org in self.parties.values():
            if isinstance(org, Organization):
                out += [f"{r.title} of {org.name}, {r.period}" for r in org.officers if r.person is person]
                out += [f"Owner {o.percent}% of {org.name}, {o.period}" for o in org.owners if o.person is person]
                out += [f"Mandate {m}" for m in org.mandates if m.person is person]
        for e in self.employees.values():
            if e.person is person:
                out.append(f"Employee {e.employee_no}")
        return out

    def transaction_story(self, txn):
        """Report: the full, unedited story of a transaction. Each class adds its own
        lines through the story_lines() template (polymorphism, no type checks)."""
        return txn.story_lines()

    def daily_report(self, on):
        """Report: what changed on a day, who did it and why (from the audit log)."""
        return [f"{e.actor:<22} {e.action:<26} {e.subject:<10} {e.detail}"
                for e in self.audit if e.on == on]

    def trial_balance(self, on=None):
        """Report: every posting is double-entry, so all balances across the bank sum to zero."""
        rows = [(a.number, str(a), a.ledger_balance(on))
                for a in list(self.arrangements.values()) if isinstance(a, DepositAccount)]
        rows += [(g.number, str(g), g.ledger_balance(on)) for g in self.gl.values()]
        return rows, sum((r[2] for r in rows), ZERO)

    def relationship_history(self, party):
        """Report: a customer's relationship, home-branch and RM history."""
        rel = party.relationship
        out = [f"{party.name}: relationship {rel.status.trail()}"]
        out += [f"  home branch {b.code} {p}" for p, b in rel.branch_history]
        out += [f"  relationship manager {e} {p}" for p, e in rel.rm_history]
        return out

    def party_snapshot(self, party, on):
        """Report ('time machine'): what the bank knew about a party on a past date."""
        out = [f"{party.name} as at {on}"]
        if isinstance(party, Organization):
            out.append(f"  registered address: {party.detail_on('registered_address', on)}")
            out += [f"  {r.title}: {r.person.name}" for r in party.officers if r.period.contains(on)]
            out += [f"  mandate: {m}" for m in party.mandates if m.period.contains(on)]
        out += [f"  restriction {r.scope}: {r.reason}" for r in party.restrictions if r.period.contains(on)]
        if party.relationship and party.relationship.status.on(on):
            rel = party.relationship
            out.append(f"  relationship {rel.status.on(on)}, home branch {rel.home_branch_on(on)}, "
                       f"RM {rel.manager_on(on)}")
        return out


# =============================================================================
# PART 13 - Seeded demonstration
# A fictional bank (Indus Commercial Bank, Lahore) is seeded and then driven
# through 16 scenarios on a simulated calendar (Jan 2026 - Aug 2027). Each
# scenario starts as a normal workflow and is broken by an exception,
# dependency or conflict. [OK] = allowed, [BLOCKED] = refused by a named rule.
# =============================================================================
def _section(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def _show(*lines):
    for line in lines:
        if isinstance(line, (list, tuple)):
            _show(*line)
        else:
            print("  " + str(line))


def _attempt(label, fn):
    """Run an operation that may be refused and print the outcome."""
    try:
        result = fn()
        print(f"  [OK]      {label}")
        return result
    except BankingError as e:
        print(f"  [BLOCKED] {label}\n            -> {type(e).__name__}: {e}")
        return None


def _txn_line(label, txn):
    extra = f"  -> {txn.failure_reason}" if txn.failure_reason else ""
    print(f"  {label}: {txn.txn_id} {fmt(txn.amount)} [{txn.status.current}]{extra}")


def run_demo():
    """Seed the bank and run every scenario. Returns the Bank for further inspection."""
    reset_ids()
    bank = Bank("Indus Commercial Bank", date(2026, 1, 5))

    # -------------------------------------------------------------------------
    _section("SEED: branches, staff, products")
    # -------------------------------------------------------------------------
    ho = bank.open_branch("HO-01", "Head Office", "Lahore")
    gulberg = bank.open_branch("LHR-01", "Gulberg Branch", "Lahore")
    mall = bank.open_branch("LHR-02", "Mall Road Branch", "Lahore")

    def staff(name, role, branch):
        return bank.hire_employee(bank.register_person(name, date(1990, 1, 1), "HR"), role, branch)

    farah = staff("Farah Siddiqui", "TELLER", gulberg)
    omar = staff("Omar Raza", "RELATIONSHIP_MANAGER", gulberg)
    zainab = staff("Zainab Qureshi", "CREDIT_OFFICER", gulberg)
    asad = staff("Asad Iqbal", "OPERATIONS_OFFICER", mall)
    rabia = staff("Rabia Anwar", "TELLER", mall)
    kamran = staff("Kamran Javed", "COMPLIANCE_ANALYST", ho)
    hina = staff("Hina Aslam", "CARD_OPERATIONS", ho)
    imran = staff("Imran Shah", "COLLECTIONS_OFFICER", ho)
    nida = staff("Nida Farooq", "AUDITOR", ho)

    classic = bank.define_product("CUR-CLASSIC", "Classic Current (legacy)", "CURRENT", monthly_fee=0)
    personal = bank.define_product("CUR-PERS", "Personal Current", "CURRENT", monthly_fee=0)
    biz_cur = bank.define_product("CUR-BIZ", "Business Current", "CURRENT", monthly_fee=500, overdraft_limit=0)
    biz_sav = bank.define_product("SAV-BIZ", "Business Savings", "SAVINGS", max_monthly_withdrawals=2,
                                  annual_rate="0.08")
    debit = bank.define_product("DC-BIZ", "Business Debit Card", "DEBIT_CARD", default_daily_limit=200_000)
    wcf = bank.define_product("WCF", "Working Capital Finance", "FINANCING", base_rate="0.18")
    _show(f"{len(bank.branches)} branches, {len(bank.employees)} staff, {len(bank.products)} products")

    # Ayesha is an existing personal customer BEFORE the business arrives
    bank.advance_to(date(2026, 1, 6))
    ayesha = bank.register_person("Ayesha Khan", date(1985, 4, 2), omar)
    a_doc = bank.add_identity_document(ayesha, "CNIC", "35202-1111111-2", date(2022, 5, 1), date(2032, 5, 1), omar)
    bank.verify_party(ayesha, a_doc, omar)
    bank.become_customer(ayesha, omar, "RETAIL")
    ayesha_acct = bank.open_deposit_account(CurrentAccount, classic, [ayesha], omar)
    bank.deposit_cash(ayesha_acct, 150_000, farah, ayesha)
    _show(f"Ayesha personal account {ayesha_acct.number} balance {fmt(ayesha_acct.ledger_balance())}")

    # -------------------------------------------------------------------------
    _section("SCENARIO 1: Business onboarding blocked by a document that expires mid-process")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 2, 2))
    ravi = bank.register_company("Ravi Textiles (Pvt) Ltd", "0098765", "Plot 12, Sundar Industrial Estate",
                                 date(2019, 8, 1), omar)
    cert = bank.add_identity_document(ravi, "INCORPORATION_CERT", "0098765", date(2019, 8, 1), None, omar)
    bilal = bank.register_person("Bilal Ahmed", date(1982, 9, 9), omar)
    sara = bank.register_person("Sara Malik", date(1988, 3, 3), omar)
    b_doc = bank.add_identity_document(bilal, "CNIC", "35202-2222222-3", date(2016, 2, 10), date(2026, 2, 10), omar)
    s_doc = bank.add_identity_document(sara, "PASSPORT", "AB1234567", date(2023, 1, 1), date(2033, 1, 1), omar)

    bank.advance_to(date(2026, 2, 3))
    for party, doc in [(ravi, cert), (bilal, b_doc), (sara, s_doc)]:
        bank.verify_party(party, doc, omar)
    bank.appoint_officer(ravi, ayesha, omar)          # SAME Person record as the retail customer
    bank.appoint_officer(ravi, bilal, omar)
    bank.record_beneficial_owner(ravi, sara, 40, omar)
    bank.record_beneficial_owner(ravi, ayesha, 10, omar)       # recorded, but below the 25% threshold
    _show("Ayesha reused her existing verified identity; no duplicate Person was created.",
          "Beneficial owners at or above 25%: "
          + ", ".join(o.person.name for o in ravi.owners if o.percent >= ravi.OWNERSHIP_THRESHOLD)
          + " (Ayesha's 10% is recorded but is below the threshold)",
          "People whose KYC the company file depends on: "
          + ", ".join(p.name for p in ravi.connected_persons(bank.today)))

    bank.advance_to(date(2026, 2, 12))                # board paperwork took time; Bilal's CNIC expired on 10 Feb
    _attempt("Onboard Ravi Textiles on 12 Feb", lambda: bank.become_customer(ravi, omar, "SME"))

    bank.advance_to(date(2026, 2, 13))
    b_doc2 = bank.add_identity_document(bilal, "CNIC", "35202-2222222-3", date(2026, 2, 12), date(2036, 2, 12), omar)
    bank.verify_party(bilal, b_doc2, omar)
    _attempt("Onboard Ravi Textiles after renewal", lambda: bank.become_customer(ravi, omar, "SME"))
    _show("Bilal's verification history is kept, not overwritten:",
          *[f"  {c.check_id} on {c.performed_on}: {c.result} against CNIC expiring {c.document.expires_on}"
            for c in bilal.checks])

    hamza = bank.register_person("Hamza Sheikh", date(1992, 6, 6), omar)
    noor = bank.register_person("Noor Fatima", date(1998, 7, 7), omar)
    usman = bank.register_person("Usman Ali", date(1990, 1, 20), omar)
    bank.grant_mandate(ravi, ayesha, {"PAYMENTS", "BORROWING", "CARD"}, None, omar)
    m_bilal = bank.grant_mandate(ravi, bilal, {"PAYMENTS"}, 5_000_000, omar)
    bank.grant_mandate(ravi, hamza, {"PAYMENTS", "CARD"}, 2_000_000, omar,
                       dual_control_above=1_000_000)   # needs a 2nd signatory above 1m
    bank.grant_mandate(ravi, noor, {"VIEW"}, None, omar)
    bank.grant_mandate(ravi, usman, {"CARD"}, None, omar)

    ravi_cur = bank.open_deposit_account(CurrentAccount, biz_cur, [ravi], omar)
    ravi_sav = bank.open_deposit_account(SavingsAccount, biz_sav, [ravi], omar)

    # Bilal also opens a PERSONAL account at Mall Road
    bank.verify_party(bilal, b_doc2, asad)
    bank.become_customer(bilal, asad, "RETAIL")
    bilal_acct = bank.open_deposit_account(CurrentAccount, personal, [bilal], asad)
    bank.deposit_cash(bilal_acct, 80_000, rabia, bilal)

    # A second organization where Ayesha is a trustee (several capacities, one person)
    bank.advance_to(date(2026, 2, 16))
    roshni = bank.register_charity("Roshni Education Trust", "TR-4411", "12 Canal View, Lahore", omar)
    bank.verify_party(roshni, bank.add_identity_document(roshni, "TRUST_DEED", "TR-4411", date(2015, 1, 1),
                                                         None, omar), omar)
    bank.appoint_officer(roshni, ayesha, omar)
    _attempt("Onboard Roshni Trust with one trustee", lambda: bank.become_customer(roshni, omar, "NON_PROFIT"))
    bank.appoint_officer(roshni, sara, omar)
    _attempt("Onboard Roshni Trust with two trustees", lambda: bank.become_customer(roshni, omar, "NON_PROFIT"))
    bank.grant_mandate(roshni, ayesha, {"PAYMENTS"}, 500_000, omar)

    # -------------------------------------------------------------------------
    _section("SEED: funding, beneficiaries, standing order, cards")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 2, 20))
    bank.deposit_cash(ravi_cur, 8_000_000, farah, hamza)
    bank.deposit_cash(ravi_sav, 1_000_000, farah, hamza)
    yarn = bank.add_beneficiary(ravi, "Lahore Yarn Traders", "Meezan Bank", "0101-0012345678",
                                "Lahore Yarn Traders", hamza)
    landlord = bank.add_beneficiary(ravi, "Model Town Properties", "HBL", "5566-7788990011",
                                    "Model Town Properties", bilal)
    rent = bank.create_standing_order(ravi_cur, landlord, 150_000, 12, bilal)
    hamza_card = bank.issue_card(debit, ravi_cur, hamza, hina)
    usman_card = bank.issue_card(debit, ravi_cur, usman, hina)
    bank.advance_to(date(2026, 2, 25))
    bank.card_purchase(hamza_card, "Metro Cash & Carry", 45_000)
    bank.advance_to(date(2026, 2, 27))
    _txn_line("Noor (view-only) tries to pay a supplier",
              bank.initiate_transfer(ravi_cur, yarn, 50_000, noor))
    _attempt("Issue card to Noor", lambda: bank.issue_card(debit, ravi_cur, noor, hina))

    # -------------------------------------------------------------------------
    _section("SCENARIO 2: Large transfer: dual control, then held for review, branch contact, release")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 3, 2))
    big = bank.initiate_transfer(ravi_cur, yarn, 1_500_000, hamza)
    _txn_line("Hamza sends 1.5m to Lahore Yarn Traders", big)
    _attempt("Hamza authorises his own payment", lambda: bank.authorise_payment(big, hamza))
    _attempt("Noor (view-only) authorises it", lambda: bank.authorise_payment(big, noor))
    bank.authorise_payment(big, ayesha)
    _txn_line("Ayesha authorises as second signatory", big)
    _show(f"Ledger {fmt(ravi_cur.ledger_balance())} | available {fmt(ravi_cur.available_balance(bank.today))}")
    alert = [c for c in bank.cases.values() if c.kind == "FraudAlert"][-1]

    bank.advance_to(date(2026, 3, 3))
    complaint = bank.log_complaint(ravi, "Supplier payment stuck, supplier waiting", "BRANCH", hamza,
                                   "PAYMENT_DELAY", omar)
    _attempt("Teller Farah releases the held payment",
             lambda: bank.release_transaction(big, farah, "customer is asking"))
    inv = bank.open_investigation(ravi, "Source of funds for large supplier payments", kamran, linked=[alert])
    ev = bank.add_evidence(inv, "Company profile at review time", ravi,
                           {"registered_address": ravi.detail("registered_address"),
                            "beneficiary": str(yarn.current_version)}, kamran)
    _show(f"Complaint {complaint.case_id} (customer channel) and investigation {inv.case_id} (risk) are "
          f"separate records, linked to {alert.case_id}")

    bank.advance_to(date(2026, 3, 5))
    bank.release_transaction(big, kamran, "Invoices verified; long-standing supplier")
    bank.close_case(alert, "FALSE_POSITIVE", kamran)
    bank.close_case(complaint, "RESOLVED - payment released 5 Mar", omar)
    _show(bank.transaction_story(big))

    # -------------------------------------------------------------------------
    _section("SCENARIO 3: Card stolen, replaced twice with different limits, old card found")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 3, 10))
    block_request = bank.report_card(hamza_card, "STOLEN", hamza)
    card2 = bank.replace_card(hamza_card, hina, daily_limit=100_000)
    bank.advance_to(date(2026, 3, 11))
    _txn_line("Thief tries old card", bank.card_purchase(hamza_card, "Online Store X", 25_000))
    _txn_line("Hamza uses new card", bank.card_purchase(card2, "Hyperstar", 30_000))
    _txn_line("Hamza tries 120k on new card", bank.card_purchase(card2, "Al-Fatah Electronics", 120_000))
    bank.advance_to(date(2026, 3, 12))
    bank.record_card_found(hamza_card, hina, "found in office drawer; destroyed")
    _attempt("Reactivate the found card", lambda: bank.reactivate_card(hamza_card, hina))
    bank.advance_to(date(2026, 3, 15))
    bank.report_card(card2, "DAMAGED", hamza)
    card3 = bank.replace_card(card2, hina)
    _show(f"Service request {block_request.case_id}: {block_request.request_type} -> "
          f"{block_request.status.current} ({block_request.outcome})")
    for c in card3.lineage():
        spent = [f"{p.txn_id}:{p.status.current}" for p in c.payments]
        _show(f"{c} status={c.status.current} limit={fmt(c.daily_limit_on(bank.today))} payments={spent}")

    # -------------------------------------------------------------------------
    _section("SCENARIO 4: Posted -> reversed -> re-posted differently -> disputed -> partial refund")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 3, 20))
    buy = bank.card_purchase(usman_card, "Packages Mall Electronics", 120_000)
    bank.advance_to(date(2026, 3, 21))
    fixed = bank.repost_card_payment(buy, 105_000, "merchant presented corrected amount", hina)
    bank.advance_to(date(2026, 4, 5))
    dispute = bank.open_dispute(fixed, 105_000, ayesha, "PHONE", omar)
    _attempt("Open a second dispute on the same payment",
             lambda: bank.open_dispute(fixed, 1_000, ayesha, "BRANCH", omar))
    bank.advance_to(date(2026, 4, 9))
    bank.resolve_dispute(dispute, "PARTIALLY_UPHELD", 40_000, hina)
    _attempt("Resolve the same dispute again (would refund twice)",
             lambda: bank.resolve_dispute(dispute, "UPHELD", 65_000, hina))
    _show(bank.transaction_story(buy), bank.transaction_story(fixed))

    # -------------------------------------------------------------------------
    _section("SCENARIO 5: Customer restricted then cleared; standing order fails in between")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 4, 10))
    block = bank.impose_restriction(ravi, "DEBIT_BLOCK", "pending source-of-funds documents", kamran, inv)
    _txn_line("Hamza transfer during restriction", bank.initiate_transfer(ravi_cur, yarn, 300_000, hamza))
    _txn_line("Ayesha's PERSONAL account is unaffected",
              bank.withdraw_cash(ayesha_acct, 20_000, farah, ayesha))
    bank.advance_to(date(2026, 4, 12))                  # standing order runs in the daily batch
    _show("Rent standing order: " + ", ".join(f"{t.initiated_on} {t.status.current}" for t in rent.payments))
    _attempt("Close investigation while restriction live", lambda: bank.close_case(inv, "CLEARED", kamran))
    bank.advance_to(date(2026, 4, 14))
    bank.lift_restriction(block, "documents received and satisfactory", kamran)
    _txn_line("Hamza transfer after clearance", bank.initiate_transfer(ravi_cur, yarn, 300_000, hamza))
    _attempt("Close investigation now", lambda: bank.close_case(inv, "CLEARED - no further action", kamran))
    _show(f"Was Ravi restricted on 11 Apr? {block.blocks('DEBIT', date(2026, 4, 11))} | "
          f"today? {block.blocks('DEBIT', bank.today)}")

    # -------------------------------------------------------------------------
    _section("SCENARIO 6: Financing with conditions, delegated limits, arrears, restructure, settlement")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 4, 15))
    _attempt("Noor applies for financing", lambda: bank.submit_financing_application(
        ravi, wcf, 3_000_000, 12, "working capital", noor))
    app = bank.submit_financing_application(ravi, wcf, 3_000_000, 12, "working capital for export order", ayesha)
    bank.attach_application_document(app, "Management accounts Jan-Mar 2026", zainab)
    bank.attach_application_document(app, "Export order from buyer (USD 40k)", zainab)
    capex = bank.submit_financing_application(ravi, wcf, 8_000_000, 36, "new looms", ayesha)
    bank.advance_to(date(2026, 4, 17))
    _attempt("Credit officer approves 8m (above her 5m delegated limit)",
             lambda: bank.decide_application(capex, zainab, True, 8_000_000, "0.19"))
    bank.decide_application(capex, zainab, False)
    _show(f"{capex.application_id} {capex.status.trail()}")
    decision = bank.decide_application(app, zainab, True, 2_500_000, "0.19",
                                       ["Personal guarantee from directors", "Audited FY2025 accounts"])
    _show(str(decision), f"Application status: {app.status.current}")
    bank.advance_to(date(2026, 4, 20))
    _attempt("Disburse before conditions met",
             lambda: bank.disburse_financing(app, ravi_cur, date(2026, 5, 23), zainab))
    bank.advance_to(date(2026, 4, 22))
    for c in app.conditions:
        bank.satisfy_condition(c, "signed original on file", omar)
    bank.advance_to(date(2026, 4, 23))
    fin = bank.disburse_financing(app, ravi_cur, date(2026, 5, 23), zainab)
    first = fin.current_schedule.installments[0]
    _show(f"{fin.number} disbursed {fmt(fin.principal)}; installment 1 due {first.due_on}: {fmt(first.outstanding)}")

    for due in (date(2026, 5, 23), date(2026, 6, 23)):
        bank.advance_to(due)
        inst = next(i for i in fin.current_schedule.installments if i.outstanding > 0)
        bank.repay_financing(fin, inst.outstanding, ravi_cur)
    _show(f"Paid 2 installments. Outstanding principal {fmt(fin.outstanding_principal())}")
    _txn_line("Customer tries to overpay by 10m", bank.repay_financing(fin, 10_000_000, ravi_cur))
    _show(f"Outstanding principal unchanged: {fmt(fin.outstanding_principal())}")

    bank.advance_to(date(2026, 7, 24))                 # July installment missed; batch flags it
    col = [c for c in bank.cases.values() if c.kind == "CollectionsCase"][-1]
    _show(f"{fin.number} status {fin.status.current}; {col.case_id}: {col.summary}")
    bank.assign_case(col, imran, "Head of Collections")
    promise = bank.record_collections_contact(col, imran, "director promised payment after export receipt",
                                              col.overdue_at_opening, date(2026, 7, 27))
    _attempt("Teller records a collections call", lambda: bank.record_collections_contact(col, farah, "called"))
    bank.advance_to(date(2026, 7, 28))
    _show(f"Promise to pay {fmt(promise.amount)} by {promise.due_on}: {promise.status.current} "
          f"-> credit decides to restructure")
    sched2 = bank.restructure_financing(fin, 18, "0.17", date(2026, 8, 28), "cash-flow delay on export order", zainab)
    _show(f"Schedule v2: {fmt(sched2.principal)} (incl. capitalised interest {fmt(sched2.capitalised_interest)}), "
          f"{len(sched2.installments)} installments; collections case {col.status.current} ({col.outcome})")

    bank.advance_to(date(2026, 8, 1))
    bank.change_role(zainab, "CREDIT_MANAGER")
    bank.advance_to(date(2026, 8, 28))
    bank.repay_financing(fin, sched2.installments[0].outstanding, ravi_cur)
    for s in fin.schedules:
        states = [i.status_on(bank.today) for i in s.installments]
        _show(f"Schedule v{s.version} [{s.status.current}]: "
              + ", ".join(f"{x}x{states.count(x)}" for x in sorted(set(states))))
    _show(f"Original credit decision still reads: {app.decision}",
          f"Zainab's role today: {zainab.role_on(bank.today).role}")

    bank.advance_to(date(2026, 9, 15))
    p, i = fin.settlement_quote(bank.today)
    bank.settle_financing(fin, ravi_cur, zainab)
    _show(f"Settled for {fmt(p + i)}; agreement status {fin.status.trail()}")
    _attempt("Restructure the settled agreement",
             lambda: bank.restructure_financing(fin, 6, "0.1", date(2026, 10, 15), "late request", zainab))

    # -------------------------------------------------------------------------
    _section("SCENARIO 7: Director leaves; old authority stays provable, new attempts fail")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 9, 16))
    old_pay = bank.initiate_transfer(ravi_cur, yarn, 500_000, bilal)
    _txn_line("Bilal pays supplier while still a director", old_pay)
    bank.advance_to(date(2026, 9, 20))
    bank.end_officer_role(ravi, bilal, "resigned", omar)
    bank.revoke_mandate(m_bilal, "resigned as director", omar)
    bank.appoint_officer(ravi, usman, omar)
    bank.verify_party(usman, bank.add_identity_document(usman, "CNIC", "35202-3333333-4",
                                                       date(2024, 1, 1), date(2034, 1, 1), omar), omar)
    bank.grant_mandate(ravi, usman, {"PAYMENTS"}, 1_000_000, omar)
    bank.advance_to(date(2026, 9, 21))
    _txn_line("Bilal tries to pay from Ravi account", bank.initiate_transfer(ravi_cur, yarn, 200_000, bilal))
    _txn_line("Bilal withdraws from his OWN account", bank.withdraw_cash(bilal_acct, 10_000, farah, bilal))
    _show(bank.transaction_story(old_pay))
    _show(f"Bilal's authority on 16 Sep: {[m.mandate_id for m in bank.authority_on(ravi, bilal, date(2026, 9, 16))]}",
          f"Bilal's authority today:    {[m.mandate_id for m in bank.authority_on(ravi, bilal, bank.today)]}",
          f"Rent standing order (set up by Bilal) continues: {rent.status.current}")
    _show("Ayesha's capacities across the bank:", *["  - " + x for x in bank.capacities_of(ayesha)])
    _show("Time machine - Ravi Textiles as the bank saw it on 11 Apr 2026:",
          *["  " + x for x in bank.party_snapshot(ravi, date(2026, 4, 11))])

    # -------------------------------------------------------------------------
    _section("SCENARIO 8: Beneficiary changes bank details after old transfers")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 9, 22))
    bank.amend_beneficiary(yarn, "Bank Alfalah", "0200-9988776655", "Lahore Yarn Traders", hamza)
    new_pay = bank.initiate_transfer(ravi_cur, yarn, 250_000, hamza)
    _show(f"{big.txn_id} was sent to {big.beneficiary_version}",
          f"{new_pay.txn_id} was sent to {new_pay.beneficiary_version}")

    # -------------------------------------------------------------------------
    _section("SCENARIO 9: Evidence referenced data that was later corrected")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 9, 25))
    bank.correct_party_detail(ravi, "registered_address", "Plot 21, Sundar Industrial Estate",
                              "typo at onboarding (12 vs 21)", omar)
    _show(f"Evidence {ev.evidence_id} captured {ev.captured_on}: {ev.snapshot['registered_address']}",
          f"Bank's record as of 3 Mar:  {ravi.detail_on('registered_address', date(2026, 3, 3))}",
          f"Bank's record today:        {ravi.detail('registered_address')}",
          f"Correction: {ravi.corrections[0].reason} (by {ravi.corrections[0].by} on {ravi.corrections[0].on})")

    # -------------------------------------------------------------------------
    _section("SCENARIO 10: Product withdrawn / terms revised without rewriting old customers")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2026, 10, 1))
    bank.withdraw_from_sale(classic, "replaced by Personal Current")
    newbie = bank.register_person("Danish Butt", date(2000, 2, 2), omar)
    bank.verify_party(newbie, bank.add_identity_document(newbie, "CNIC", "35202-4444444-5",
                                                         date(2025, 1, 1), date(2035, 1, 1), omar), omar)
    bank.become_customer(newbie, omar, "RETAIL")
    _attempt("Open Classic Current for a new customer",
             lambda: bank.open_deposit_account(CurrentAccount, classic, [newbie], omar))
    _txn_line("Ayesha still deposits to her Classic account", bank.deposit_cash(ayesha_acct, 5_000, farah, ayesha))
    bank.revise_product_terms(biz_cur, date(2026, 11, 1), monthly_fee=750)
    bank.advance_to(date(2026, 11, 30))
    nov_fee = [t for t in bank.transactions.values() if t.kind == "FeeCharge" and t.initiated_on == bank.today][0]
    _show(f"Nov fee for existing Ravi account: {fmt(nov_fee.amount)} (pinned terms v{nov_fee.terms_version.version_no})")
    bank.advance_to(date(2026, 12, 1))
    bank.migrate_terms(ravi_cur, omar)
    bank.advance_to(date(2026, 12, 31))
    dec_fee = [t for t in bank.transactions.values() if t.kind == "FeeCharge" and t.initiated_on == bank.today][0]
    _show(f"Dec fee after migration + notice: {fmt(dec_fee.amount)} (terms v{dec_fee.terms_version.version_no})",
          f"Terms in force on 15 Nov: v{ravi_cur.terms_on(date(2026, 11, 15)).version_no}; "
          f"on 15 Dec: v{ravi_cur.terms_on(date(2026, 12, 15)).version_no}")
    bank.withdraw_from_sale(debit, "new chip-and-PIN card range")
    bank.report_card(usman_card, "LOST", usman)
    usman_card2 = _attempt("Replace a card after its product was withdrawn (existing cardholder)",
                           lambda: bank.replace_card(usman_card, hina))
    _attempt("Issue the withdrawn card to a NEW cardholder",
             lambda: bank.issue_card(debit, ravi_cur, ayesha, hina))
    if usman_card2:
        _show(f"Usman's card chain: {[c.card_id for c in usman_card2.lineage()]}")

    # -------------------------------------------------------------------------
    _section("SCENARIO 11: Branch closes; customers, accounts, staff and vault cash move; history stays")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2027, 1, 4))
    mall_cash_before = -mall.vault.ledger_balance()
    moved = bank.close_branch(mall, gulberg, "Head of Operations")
    _show(f"Moved: {moved}; vault cash {fmt(mall_cash_before)} moved to {gulberg.code}",
          f"{bilal_acct.number} opened at {bilal_acct.opened_at_branch.code}; "
          f"served on 1 Dec by {bilal_acct.servicing_branch_on(date(2026, 12, 1)).code}, "
          f"today by {bilal_acct.servicing_branch_on(bank.today).code}",
          f"Asad on 1 Dec: {asad.role_on(date(2026, 12, 1)).branch.code}; today: {asad.role_on(bank.today).branch.code}",
          f"Branch status: {mall.status.trail()}")
    _attempt("Hire a new teller at the closed branch",
             lambda: bank.hire_employee(bank.register_person("Late Hire", date(1995, 1, 1), "HR"), "TELLER", mall))

    # -------------------------------------------------------------------------
    _section("SCENARIO 12: Savings withdrawal limit, then account closure (closure is not deletion)")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2027, 1, 5))
    _txn_line("Withdrawal 1", bank.withdraw_cash(ravi_sav, 400_000, farah, ayesha))
    _txn_line("Withdrawal 2", bank.withdraw_cash(ravi_sav, 300_000, farah, ayesha))
    _txn_line("Withdrawal 3", bank.withdraw_cash(ravi_sav, 300_000, farah, ayesha))
    _attempt("Close savings with balance", lambda: bank.close_account(ravi_sav, "customer request", omar))
    bank.advance_to(date(2027, 2, 1))
    bank.withdraw_cash(ravi_sav, ravi_sav.ledger_balance(), farah, ayesha)
    _attempt("Close savings at zero balance", lambda: bank.close_account(ravi_sav, "customer request", omar))
    _show(f"{ravi_sav.number}: {ravi_sav.status.trail()}; {len(ravi_sav.entries)} ledger entries retained")

    # -------------------------------------------------------------------------
    _section("SCENARIO 13: Staff member and customer leave; history keeps both")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2027, 2, 3))
    _attempt("Omar resigns while still managing customers",
             lambda: bank.record_employee_exit(omar, "resigned"))
    maryam = staff("Maryam Tahir", "RELATIONSHIP_MANAGER", gulberg)
    for p in bank.parties.values():
        if p.relationship and p.relationship.manager_on(bank.today) is omar:
            bank.assign_relationship_manager(p, maryam, "Branch Manager")
    _attempt("Omar resigns after hand-over", lambda: bank.record_employee_exit(omar, "resigned"))
    _show(f"Old KYC check still names the verifier: {bilal.checks[0].check_id} by {bilal.checks[0].performed_by}"
          f" (employee status now {omar.status.current})")
    _show(bank.relationship_history(ravi))
    _attempt("Bilal closes his relationship while his account is open",
             lambda: bank.end_relationship(bilal, "moving abroad", maryam))
    _attempt("Danish (no products) leaves the bank",
             lambda: bank.end_relationship(newbie, "moved to another bank", maryam))
    _show(f"Danish's record kept: {newbie} relationship {newbie.relationship.status.trail()}")

    # -------------------------------------------------------------------------
    _section("SCENARIO 14: Sole trader and high-value customer; fixed-term deposits")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2027, 2, 8))
    private_cur = bank.define_product("CUR-PRIV", "Private Banking Current", "CURRENT", monthly_fee=0)
    ftd6 = bank.define_product("FTD-6M", "6-Month Term Deposit", "TERM_DEPOSIT", term_months=6,
                               annual_rate="0.115", early_break_penalty="0.01")
    imtiaz = bank.register_person("Imtiaz Ahmed", date(1979, 5, 5), maryam)
    bank.verify_party(imtiaz, bank.add_identity_document(imtiaz, "CNIC", "35202-5555555-6",
                                                         date(2021, 3, 1), date(2031, 3, 1), maryam), maryam)
    _attempt("Onboard Imtiaz as a sole trader without a trading name",
             lambda: bank.become_customer(imtiaz, maryam, "SOLE_TRADER"))
    bank.become_customer(imtiaz, maryam, "SOLE_TRADER", trading_name="Imtiaz Auto Parts")
    imtiaz_acct = bank.open_deposit_account(CurrentAccount, biz_cur, [imtiaz], maryam)
    bank.deposit_cash(imtiaz_acct, 300_000, farah, imtiaz)
    lesco = bank.register_biller("LESCO", "Lahore Electric Supply Co", "UTILITY")
    fbr = bank.register_biller("FBR", "Federal Board of Revenue", "TAX")
    _txn_line("Imtiaz pays the shop's electricity bill",
              bank.pay_bill(imtiaz_acct, lesco, "04-11234-5567", 18_400, imtiaz))
    _show(f"{imtiaz.name} trades as '{imtiaz.detail('trading_name')}': one Person, segment "
          f"{imtiaz.relationship.segment}, personally liable (no separate Organization record)")

    zara = bank.register_person("Zara Hussain", date(1975, 10, 10), maryam)
    bank.verify_party(zara, bank.add_identity_document(zara, "PASSPORT", "ZH7654321",
                                                       date(2024, 6, 1), date(2034, 6, 1), maryam), maryam)
    _attempt("Onboard Zara as a high-value (PRIVATE) customer",
             lambda: bank.become_customer(zara, maryam, "PRIVATE"))
    sow = bank.add_identity_document(zara, "SOURCE_OF_WEALTH", "Sale deed DHA plot 14-B",
                                     date(2026, 11, 20), None, maryam)
    bank.verify_party(zara, sow, kamran)
    _attempt("Onboard Zara after enhanced due diligence", lambda: bank.become_customer(zara, maryam, "PRIVATE"))
    zara_cur = bank.open_deposit_account(CurrentAccount, private_cur, [zara], maryam)
    bank.deposit_cash(zara_cur, 12_000_000, farah, zara)
    ftd_a = bank.open_deposit_account(FixedTermDeposit, ftd6, [zara], maryam, payout_account=zara_cur)
    ftd_b = bank.open_deposit_account(FixedTermDeposit, ftd6, [zara], maryam, payout_account=zara_cur)
    bank.transfer_between_accounts(zara_cur, ftd_a, 10_000_000, zara)
    bank.transfer_between_accounts(zara_cur, ftd_b, 1_000_000, zara)
    _show(f"{ftd_a.number} PKR 10m and {ftd_b.number} PKR 1m placed at 11.5% for 6 months, "
          f"maturing {ftd_a.maturity_on}")
    _txn_line("Zara tries to withdraw cash from the term deposit",
              bank.withdraw_cash(ftd_a, 500_000, farah, zara))
    _txn_line("Zara tries to top up the term deposit",
              bank.transfer_between_accounts(zara_cur, ftd_a, 100_000, zara))
    bank.advance_to(date(2027, 3, 10))
    penalty = bank.break_term_deposit(ftd_b, maryam, "customer needs funds for a car")
    _show(f"{ftd_b.number} broken early: interest forfeited, penalty {fmt(penalty)}; "
          f"status {ftd_b.status.trail()}")
    bank.advance_to(ftd_a.maturity_on)
    interest = [t for t in bank.transactions.values()
                if isinstance(t, InterestCredit) and ftd_a.number in t.narrative][0]
    _show(f"{ftd_a.number} matured {ftd_a.maturity_on}: interest {fmt(interest.amount)} and principal "
          f"paid to {zara_cur.number}; deposit {ftd_a.status.current}, "
          f"{len(ftd_a.entries)} ledger entries retained")

    # -------------------------------------------------------------------------
    _section("SCENARIO 15: Card controls, bill payments under dual control, searchable card history")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2027, 8, 10))
    bank.deposit_cash(ravi_cur, 5_000_000, farah, hamza)
    online_block = bank.add_card_control(card3, "ONLINE", hamza)
    bank.add_card_control(card3, "MERCHANT_CATEGORY", hina, value="GAMBLING")
    _attempt("Noor (not the cardholder) switches off Hamza's online block",
             lambda: bank.remove_card_control(online_block, noor))
    _txn_line("Online purchase while blocked",
              bank.card_purchase(card3, "Daraz.pk", 12_000, channel="ONLINE"))
    _txn_line("In-store purchase", bank.card_purchase(card3, "Imtiaz Auto Parts", 9_500))
    bank.advance_to(date(2027, 8, 12))
    bank.remove_card_control(online_block, hamza)
    _txn_line("Online purchase after Hamza lifts his block",
              bank.card_purchase(card3, "Daraz.pk", 12_000, channel="ONLINE"))
    _txn_line("Online betting site (category still blocked by card operations)",
              bank.card_purchase(card3, "BetWorld", 5_000, channel="ONLINE", merchant_category="GAMBLING"))
    _show(f"Was online use blocked on 10 Aug? {online_block.blocks('ONLINE', 'PK', 'RETAIL', date(2027, 8, 10))}"
          f" | today? {online_block.blocks('ONLINE', 'PK', 'RETAIL', bank.today)}")
    _txn_line("Noor (view-only) pays a tax bill", bank.pay_bill(ravi_cur, fbr, "NTN-4455667", 50_000, noor))
    tax = bank.pay_bill(ravi_cur, fbr, "NTN-4455667", 1_250_000, hamza)
    _txn_line("Hamza pays the quarterly sales-tax bill", tax)
    bank.authorise_payment(tax, ayesha)
    _txn_line("Ayesha authorises it as second signatory", tax)
    hits = bank.search_transactions(card=card3)
    _show(f"Search by Hamza's current card finds {len(hits)} payments across the whole chain:",
          *[f"  {t.txn_id} {t.initiated_on} {fmt(t.amount):>16} [{t.status.current}] "
            f"card {t.card.card_id} at {t.merchant}" for t in hits])

    # -------------------------------------------------------------------------
    _section("SCENARIO 16: Auditor review, record retention, archive versus delete")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2027, 8, 20))
    _attempt("Teller runs the approvals audit",
             lambda: bank.approvals_and_authority_audit(farah, date(2026, 1, 1), date(2026, 12, 31)))
    audit_lines = bank.approvals_and_authority_audit(nida, date(2026, 1, 1), date(2026, 12, 31))
    _show(f"Auditor {nida.person.name}: {len(audit_lines) - 2} approvals and authority changes in 2026, e.g.:",
          *[line for line in audit_lines if "CREDIT_OFFICER" in line or "REVOKE_MANDATE" in line][:5])
    _attempt(f"Delete closed savings account {ravi_sav.number}",
             lambda: bank.request_deletion(ravi_sav, maryam))
    before = len(bank.active_arrangements())
    bank.archive_record(ravi_sav, maryam)
    bank.archive_record(newbie.relationship, maryam)
    bank.archive_record(dispute, maryam)
    _show(f"Archived {ravi_sav.number}, Danish's ended relationship and {dispute.case_id}: working list "
          f"{before} -> {len(bank.active_arrangements())} arrangements; all records still held",
          f"{ravi_sav.number} may not be destroyed before {bank.retention_until(ravi_sav)}")
    old_payee = bank.add_beneficiary(ravi, "Old courier", "UBL", "7777888899990000", "Swift Couriers", hamza)
    _attempt("Delete a payee that was never used", lambda: bank.delete_beneficiary(old_payee, maryam))
    _attempt("Delete Lahore Yarn Traders (used by past payments)",
             lambda: bank.delete_beneficiary(yarn, maryam))

    # -------------------------------------------------------------------------
    _section("OPEN ITEMS: work still waiting at the end of the simulation")
    # -------------------------------------------------------------------------
    bank.advance_to(date(2027, 8, 25))
    waiting = bank.initiate_transfer(ravi_cur, yarn, 1_200_000, hamza)      # needs a second signatory
    held = bank.initiate_transfer(ravi_cur, yarn, 1_100_000, ayesha)        # above the review threshold
    books = bank.card_purchase(card3, "Liberty Books", 18_500)
    open_dispute = bank.open_dispute(books, 18_500, hamza, "BRANCH", maryam)
    _txn_line("Waiting for a second signatory", waiting)
    _txn_line("Held for compliance review", held)
    _show(f"Open dispute {open_dispute.case_id} on {books.txn_id}; "
          f"Ravi available balance {fmt(ravi_cur.available_balance(bank.today))}")

    # -------------------------------------------------------------------------
    _section("REPORTS")
    # -------------------------------------------------------------------------
    _show("Statement, Ravi current account, March 2026:")
    _show(bank.generate_statement(ravi_cur, date(2026, 3, 1), date(2026, 3, 31)).render())
    _show("", "End-of-day audit for 10-11 March 2026 (what changed, who, why):")
    _show(bank.daily_report(date(2026, 3, 10)) + bank.daily_report(date(2026, 3, 11)))
    rows, total = bank.trial_balance()
    _show("", "Trial balance (double-entry check; credits +, debits -):")
    _show(*[f"{num:<12} {bal:>16,.2f}  {name}" for num, name, bal in rows])
    _show(f"{'TOTAL':<12} {total:>16,.2f}  <- must be zero")
    _show("", f"Totals: {len(bank.transactions)} transactions, {len(bank.cases)} cases, "
              f"{len(bank.notices)} notices, {len(bank.audit)} audit events. Nothing was deleted.")
    return bank


# =============================================================================
# PART 14 - Automated tests
# Run:  python banking_system.py --test
# Each test builds a fresh, small bank so the tests are independent.
# =============================================================================
class _World:
    """A small bank: one verified company with two directors, accounts, a card, a payee."""

    def __init__(self):
        bank = self.bank = Bank("Test Bank", date(2026, 1, 1))
        self.branch = bank.open_branch("B1", "Main", "Lahore")
        self.branch2 = bank.open_branch("B2", "Second", "Lahore")

        def staff(name, role, branch=self.branch):
            return bank.hire_employee(bank.register_person(name, date(1990, 1, 1), "HR"), role, branch)

        self.teller, self.rm = staff("Teller", "TELLER"), staff("RM", "RELATIONSHIP_MANAGER")
        self.credit, self.compliance = staff("Credit", "CREDIT_OFFICER"), staff("Compliance", "COMPLIANCE_ANALYST")
        self.cards, self.ops2 = staff("Cards", "CARD_OPERATIONS"), staff("Ops2", "OPERATIONS_OFFICER", self.branch2)

        self.cur = bank.define_product("CUR", "Current", "CURRENT", monthly_fee=500)
        self.sav = bank.define_product("SAV", "Savings", "SAVINGS", max_monthly_withdrawals=2)
        self.dc = bank.define_product("DC", "Debit Card", "DEBIT_CARD", default_daily_limit=100_000)
        self.fin = bank.define_product("FIN", "Finance", "FINANCING")

        def person(name, expires=date(2035, 1, 1)):
            p = bank.register_person(name, date(1985, 1, 1), self.rm)
            d = bank.add_identity_document(p, "CNIC", name, date(2020, 1, 1), expires, self.rm)
            bank.verify_party(p, d, self.rm)
            return p

        self.person = person
        self.a, self.b, self.c = person("Alpha"), person("Beta"), person("Gamma")
        co = self.co = bank.register_company("Co Ltd", "1", "Old Address", date(2020, 1, 1), self.rm)
        bank.verify_party(co, bank.add_identity_document(co, "CERT", "1", date(2020, 1, 1), None, self.rm), self.rm)
        bank.appoint_officer(co, self.a, self.rm)
        bank.appoint_officer(co, self.b, self.rm)
        bank.become_customer(co, self.rm, "SME")
        self.m_a = bank.grant_mandate(co, self.a, {"PAYMENTS", "BORROWING", "CARD"}, None, self.rm)
        self.m_b = bank.grant_mandate(co, self.b, {"PAYMENTS", "CARD"}, 2_000_000, self.rm,
                                      dual_control_above=500_000)
        bank.grant_mandate(co, self.c, {"VIEW"}, None, self.rm)
        self.acct = bank.open_deposit_account(CurrentAccount, self.cur, [co], self.rm)
        bank.deposit_cash(self.acct, 5_000_000, self.teller, self.a)
        self.ben = bank.add_beneficiary(co, "Supplier", "HBL", "1111222233334444", "Supplier Ltd", self.a)
        self.card = bank.issue_card(self.dc, self.acct, self.b, self.cards)

    def disbursed(self, amount=1_200_000, conditions=("guarantee",)):
        """Apply, approve with conditions, meet them and disburse."""
        app = self.bank.submit_financing_application(self.co, self.fin, amount, 12, "wc", self.a)
        self.bank.decide_application(app, self.credit, True, amount, "0.12", list(conditions))
        for c in app.conditions:
            self.bank.satisfy_condition(c, "signed", self.rm)
        return self.bank.disburse_financing(app, self.acct, date(2026, 2, 1), self.credit)


class OnboardingTests(unittest.TestCase):
    def test_expired_document_blocks_onboarding(self):
        w = _World()
        late = w.bank.register_person("Late", date(1980, 1, 1), w.rm)
        doc = w.bank.add_identity_document(late, "CNIC", "9", date(2020, 1, 1), date(2026, 1, 10), w.rm)
        w.bank.verify_party(late, doc, w.rm)
        w.bank.advance_to(date(2026, 1, 11))
        with self.assertRaises(KycIncomplete):
            w.bank.become_customer(late, w.rm, "RETAIL")

    def test_charity_needs_two_trustees(self):
        w = _World()
        ch = w.bank.register_charity("Trust", "T1", "Addr", w.rm)
        w.bank.verify_party(ch, w.bank.add_identity_document(ch, "DEED", "T1", date(2020, 1, 1), None, w.rm), w.rm)
        w.bank.appoint_officer(ch, w.a, w.rm)
        with self.assertRaises(KycIncomplete):
            w.bank.become_customer(ch, w.rm, "NON_PROFIT")
        w.bank.appoint_officer(ch, w.b, w.rm)
        self.assertIsNotNone(w.bank.become_customer(ch, w.rm, "NON_PROFIT"))

    def test_same_person_is_never_duplicated_across_roles(self):
        w = _World()
        w.bank.become_customer(w.a, w.rm, "RETAIL")
        capacities = w.bank.capacities_of(w.a)
        self.assertTrue(any("Customer since" in c for c in capacities))
        self.assertTrue(any("DIRECTOR of Co Ltd" in c for c in capacities))
        self.assertEqual(sum(1 for p in w.bank.parties.values() if p.name == "Alpha"), 1)

    def test_only_branch_staff_can_onboard(self):
        w = _World()
        with self.assertRaises(AuthorityError):
            w.bank.become_customer(w.a, w.credit, "RETAIL")

    def test_verification_needs_the_partys_own_document(self):
        w = _World()
        with self.assertRaises(BankingError):
            w.bank.verify_party(w.a, w.b.documents[0], w.rm)


class PaymentTests(unittest.TestCase):
    def test_view_only_mandate_cannot_pay_and_failure_is_kept(self):
        w = _World()
        t = w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.c)
        self.assertEqual(t.status.current, "FAILED")
        self.assertIn(t.txn_id, w.bank.transactions)

    def test_dual_control_needs_a_different_signatory(self):
        w = _World()
        t = w.bank.initiate_transfer(w.acct, w.ben, 600_000, w.b)
        self.assertEqual(t.status.current, "AWAITING_AUTHORISATION")
        with self.assertRaises(AuthorityError):
            w.bank.authorise_payment(t, w.b)
        w.bank.authorise_payment(t, w.a)
        self.assertEqual(t.status.current, "POSTED")

    def test_only_a_signatory_may_cancel_a_pending_payment(self):
        w = _World()
        t = w.bank.initiate_transfer(w.acct, w.ben, 600_000, w.b)
        with self.assertRaises(AuthorityError):
            w.bank.cancel_pending_payment(t, w.c, "not mine to cancel")
        w.bank.cancel_pending_payment(t, w.b, "wrong invoice")
        self.assertEqual(t.status.current, "CANCELLED")

    def test_large_transfer_held_reduces_available_not_ledger(self):
        w = _World()
        before = w.acct.ledger_balance()
        t = w.bank.initiate_transfer(w.acct, w.ben, 1_500_000, w.a)
        self.assertEqual(t.status.current, "HELD_FOR_REVIEW")
        self.assertEqual(w.acct.ledger_balance(), before)
        self.assertEqual(w.acct.available_balance(w.bank.today), before - money(1_500_000))
        with self.assertRaises(AuthorityError):
            w.bank.release_transaction(t, w.teller, "customer asked")
        w.bank.release_transaction(t, w.compliance, "ok")
        self.assertEqual(w.acct.ledger_balance(), before - money(1_500_000))

    def test_reject_of_a_non_held_payment_is_refused_cleanly(self):
        w = _World()
        t = w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.a)
        with self.assertRaises(InvalidStateError):
            w.bank.reject_held_transaction(t, w.compliance, "no")

    def test_restriction_blocks_then_lifts_with_history(self):
        w = _World()
        r = w.bank.impose_restriction(w.co, "DEBIT_BLOCK", "review", w.compliance)
        self.assertEqual(w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.a).status.current, "FAILED")
        w.bank.advance_to(date(2026, 1, 5))
        w.bank.lift_restriction(r, "cleared", w.compliance)
        self.assertEqual(w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.a).status.current, "POSTED")
        self.assertTrue(r.blocks("DEBIT", date(2026, 1, 3)))
        self.assertFalse(r.blocks("DEBIT", w.bank.today))

    def test_partial_reversal_and_over_reversal(self):
        w = _World()
        t = w.bank.card_purchase(w.card, "Shop", 50_000)
        w.bank.reverse_transaction(t, 20_000, "partial refund", w.cards)
        self.assertEqual(t.status.current, "PARTIALLY_REVERSED")
        self.assertEqual(t.net_amount, money(30_000))
        with self.assertRaises(BankingError):
            w.bank.reverse_transaction(t, 40_000, "too much", w.cards)

    def test_repost_links_original_and_correction(self):
        w = _World()
        t = w.bank.card_purchase(w.card, "Shop", 50_000)
        new = w.bank.repost_card_payment(t, 45_000, "corrected", w.cards)
        self.assertIs(t.superseded_by, new)
        self.assertIs(new.supersedes, t)
        self.assertEqual(t.status.current, "REVERSED")

    def test_dispute_cannot_be_resolved_twice(self):
        w = _World()
        t = w.bank.card_purchase(w.card, "Shop", 50_000)
        d = w.bank.open_dispute(t, 50_000, w.a, "PHONE", w.rm)
        with self.assertRaises(InvalidStateError):
            w.bank.open_dispute(t, 10_000, w.a, "PHONE", w.rm)
        w.bank.resolve_dispute(d, "PARTIALLY_UPHELD", 20_000, w.cards)
        with self.assertRaises(InvalidStateError):
            w.bank.resolve_dispute(d, "UPHELD", 30_000, w.cards)
        self.assertEqual(t.net_amount, money(30_000))           # refunded once only

    def test_only_customer_payments_can_be_disputed(self):
        w = _World()
        fee = w.bank.charge_fee(w.acct, "TEST", 100)
        with self.assertRaises(BankingError):
            w.bank.open_dispute(fee, 100, w.a, "PHONE", w.rm)

    def test_beneficiary_snapshot_survives_amendment(self):
        w = _World()
        t = w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.a)
        w.bank.amend_beneficiary(w.ben, "UBL", "9999888877776666", "Supplier Ltd", w.a)
        self.assertEqual(t.beneficiary_version.bank_name, "HBL")
        self.assertEqual(w.ben.current_version.bank_name, "UBL")

    def test_standing_order_day_must_exist_every_month(self):
        w = _World()
        with self.assertRaises(BankingError):
            w.bank.create_standing_order(w.acct, w.ben, 1_000, 31, w.a)

    def test_unbalanced_posting_is_refused(self):
        w = _World()
        with self.assertRaises(BankingError):
            InternalTransfer(100, w.bank.today, "bad").post([(w.acct, 100)], w.bank.today)

    def test_trial_balance_is_always_zero(self):
        w = _World()
        w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.a)
        w.bank.card_purchase(w.card, "Shop", 5_000)
        w.bank.advance_to(date(2026, 2, 1))           # month-end fee
        self.assertEqual(w.bank.trial_balance()[1], 0)


class CardTests(unittest.TestCase):
    def test_stolen_replaced_card_cannot_be_reactivated(self):
        w = _World()
        w.bank.report_card(w.card, "STOLEN", w.b)
        new = w.bank.replace_card(w.card, w.cards, daily_limit=50_000)
        self.assertEqual(w.bank.card_purchase(w.card, "X", 10).status.current, "DECLINED")
        with self.assertRaises(InvalidStateError):
            w.bank.reactivate_card(w.card, w.cards)
        self.assertEqual([c.card_id for c in new.lineage()], [w.card.card_id, new.card_id])

    def test_card_daily_limit(self):
        w = _World()
        self.assertEqual(w.bank.card_purchase(w.card, "A", 80_000).status.current, "POSTED")
        self.assertEqual(w.bank.card_purchase(w.card, "B", 30_000).status.current, "DECLINED")

    def test_found_active_card_is_not_destroyed(self):
        w = _World()
        with self.assertRaises(InvalidStateError):
            w.bank.record_card_found(w.card, w.cards, "was never lost")
        self.assertEqual(w.card.status.current, "ACTIVE")

    def test_replacement_allowed_after_card_product_withdrawn(self):
        w = _World()
        w.bank.withdraw_from_sale(w.dc, "new range")
        w.bank.report_card(w.card, "DAMAGED", w.b)
        self.assertEqual(w.bank.replace_card(w.card, w.cards).replaces, w.card)
        with self.assertRaises(ProductNotAvailable):
            w.bank.issue_card(w.dc, w.acct, w.a, w.cards)


class AuthorityAndStaffTests(unittest.TestCase):
    def test_revoked_mandate_still_provable_for_past_dates(self):
        w = _World()
        t = w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.b)
        w.bank.advance_to(date(2026, 1, 10))
        w.bank.revoke_mandate(w.m_b, "resigned", w.rm)
        self.assertEqual(w.bank.authority_on(w.co, w.b, date(2026, 1, 1)), [w.m_b])
        self.assertEqual(w.bank.authority_on(w.co, w.b, w.bank.today), [])
        self.assertIs(t.mandate_used, w.m_b)
        self.assertEqual(w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.b).status.current, "FAILED")

    def test_approval_keeps_role_after_promotion(self):
        w = _World()
        app = w.bank.submit_financing_application(w.co, w.fin, 1_000_000, 12, "wc", w.a)
        w.bank.decide_application(app, w.credit, True, 1_000_000, "0.2")
        w.bank.advance_to(date(2026, 2, 1))
        w.bank.change_role(w.credit, "CREDIT_MANAGER")
        self.assertEqual(app.decision.role_at_time, "CREDIT_OFFICER")

    def test_credit_approval_respects_delegated_limit(self):
        w = _World()
        app = w.bank.submit_financing_application(w.co, w.fin, 8_000_000, 24, "capex", w.a)
        with self.assertRaises(AuthorityError):
            w.bank.decide_application(app, w.credit, True, 8_000_000, "0.2")
        self.assertEqual(app.status.current, "SUBMITTED")
        w.bank.change_role(w.credit, "CREDIT_MANAGER")
        w.bank.decide_application(app, w.credit, True, 8_000_000, "0.2")
        self.assertEqual(app.status.current, "APPROVED")

    def test_employee_exit_blocked_while_managing_customers(self):
        w = _World()
        with self.assertRaises(InvalidStateError):
            w.bank.record_employee_exit(w.rm, "resigned")

    def test_employee_cannot_leave_twice(self):
        w = _World()
        w.bank.record_employee_exit(w.teller, "resigned")
        with self.assertRaises(InvalidStateError):
            w.bank.record_employee_exit(w.teller, "resigned again")

    def test_branch_closure_moves_but_keeps_history(self):
        w = _World()
        acct2 = w.bank.open_deposit_account(CurrentAccount, w.cur, [w.co], w.ops2)
        w.bank.advance_to(date(2026, 3, 1))
        w.bank.close_branch(w.branch2, w.branch, "ops")
        self.assertEqual(acct2.opened_at_branch.code, "B2")
        self.assertEqual(acct2.servicing_branch_on(date(2026, 2, 1)).code, "B2")
        self.assertEqual(acct2.servicing_branch_on(w.bank.today).code, "B1")
        with self.assertRaises(InvalidStateError):
            w.bank.hire_employee(w.a, "TELLER", w.branch2)

    def test_branch_closure_moves_vault_cash(self):
        w = _World()
        teller2 = w.bank.hire_employee(w.bank.register_person("T2", date(1990, 1, 1), "HR"), "TELLER", w.branch2)
        w.bank.deposit_cash(w.acct, 70_000, teller2, w.a)
        w.bank.close_branch(w.branch2, w.branch, "ops")
        self.assertEqual(w.branch2.vault.ledger_balance(), 0)
        self.assertEqual(w.branch.vault.ledger_balance(), money(-5_070_000))
        self.assertEqual(w.bank.trial_balance()[1], 0)
        with self.assertRaises(InvalidStateError):
            w.bank.close_branch(w.branch, w.branch, "ops")


class ProductTests(unittest.TestCase):
    def test_withdrawn_product_blocks_new_but_not_existing(self):
        w = _World()
        w.bank.withdraw_from_sale(w.cur, "legacy")
        with self.assertRaises(ProductNotAvailable):
            w.bank.open_deposit_account(CurrentAccount, w.cur, [w.co], w.rm)
        self.assertEqual(w.bank.deposit_cash(w.acct, 10, w.teller).status.current, "POSTED")

    def test_terms_pinned_until_migration(self):
        w = _World()
        w.bank.revise_product_terms(w.cur, date(2026, 2, 1), monthly_fee=900)
        w.bank.advance_to(date(2026, 2, 5))
        self.assertEqual(w.acct.terms.get("monthly_fee"), 500)
        w.bank.migrate_terms(w.acct, w.rm)
        self.assertEqual(w.acct.terms.get("monthly_fee"), 900)
        self.assertEqual(w.acct.terms_on(date(2026, 2, 1)).get("monthly_fee"), 500)
        with self.assertRaises(InvalidStateError):
            w.bank.migrate_terms(w.acct, w.rm)           # already on the latest version

    def test_savings_withdrawal_limit_and_closure(self):
        w = _World()
        s = w.bank.open_deposit_account(SavingsAccount, w.sav, [w.co], w.rm)
        w.bank.deposit_cash(s, 300, w.teller)
        for _ in range(2):
            w.bank.withdraw_cash(s, 100, w.teller, w.a)
        self.assertEqual(w.bank.withdraw_cash(s, 100, w.teller, w.a).status.current, "FAILED")
        with self.assertRaises(InvalidStateError):
            w.bank.close_account(s, "request", w.rm)

    def test_bank_fees_do_not_use_savings_withdrawals(self):
        w = _World()
        s = w.bank.open_deposit_account(SavingsAccount, w.sav, [w.co], w.rm)
        w.bank.deposit_cash(s, 1_000, w.teller)
        w.bank.charge_fee(s, "CHEQUE_BOOK", 50)
        w.bank.charge_fee(s, "SMS_ALERTS", 50)
        self.assertEqual(w.bank.withdraw_cash(s, 100, w.teller, w.a).status.current, "POSTED")

    def test_close_account_refuses_while_money_is_on_hold_or_pending(self):
        w = _World()
        w.bank.initiate_transfer(w.acct, w.ben, 600_000, w.b)          # awaiting 2nd signatory
        with self.assertRaises(InvalidStateError):
            w.bank.close_account(w.acct, "request", w.rm)

    def test_closing_an_account_cancels_its_cards_and_standing_orders(self):
        w = _World()
        s = w.bank.open_deposit_account(CurrentAccount, w.cur, [w.co], w.rm)
        so = w.bank.create_standing_order(s, w.ben, 1_000, 5, w.a)
        card = w.bank.issue_card(w.dc, s, w.a, w.cards)
        w.bank.close_account(s, "no longer needed", w.rm)
        self.assertEqual((so.status.current, card.status.current), ("CANCELLED", "CANCELLED"))
        self.assertEqual(s.status.trail().count(">"), 1)               # ACTIVE > CLOSED, record kept


class FinancingTests(unittest.TestCase):
    def test_disbursement_waits_for_conditions(self):
        w = _World()
        app = w.bank.submit_financing_application(w.co, w.fin, 1_200_000, 12, "wc", w.a)
        w.bank.decide_application(app, w.credit, True, 1_200_000, "0.12", ["guarantee"])
        with self.assertRaises(BankingError):
            w.bank.disburse_financing(app, w.acct, date(2026, 2, 1), w.credit)

    def test_restructure_supersedes_schedule_and_keeps_paid(self):
        w = _World()
        fin = w.disbursed()
        w.bank.advance_to(date(2026, 2, 1))
        w.bank.repay_financing(fin, fin.current_schedule.installments[0].outstanding, w.acct)
        w.bank.advance_to(date(2026, 3, 5))                 # March installment missed
        self.assertEqual(fin.status.current, "IN_ARREARS")
        w.bank.restructure_financing(fin, 18, "0.10", date(2026, 4, 1), "cash flow", w.credit)
        old, new = fin.schedules
        self.assertEqual(old.status.current, "SUPERSEDED")
        self.assertEqual(old.installments[0].status_on(w.bank.today), "PAID")
        self.assertGreater(new.capitalised_interest, 0)
        self.assertEqual(w.bank.trial_balance()[1], 0)

    def test_early_settlement_clears_principal(self):
        w = _World()
        fin = w.disbursed()
        w.bank.advance_to(date(2026, 1, 20))
        w.bank.settle_financing(fin, w.acct, w.credit)
        self.assertEqual(fin.outstanding_principal(), 0)
        self.assertEqual(fin.status.current, "SETTLED")
        self.assertEqual(w.bank.gl["1100"].ledger_balance(), 0)
        with self.assertRaises(InvalidStateError):
            w.bank.restructure_financing(fin, 6, "0.1", date(2026, 3, 1), "late", w.credit)

    def test_overpayment_is_refused_without_touching_installments(self):
        w = _World()
        fin = w.disbursed()
        before = [(i.principal_paid, i.interest_paid) for i in fin.current_schedule.installments]
        txn = w.bank.repay_financing(fin, 5_000_000, w.acct)
        self.assertEqual(txn.status.current, "FAILED")
        self.assertEqual([(i.principal_paid, i.interest_paid) for i in fin.current_schedule.installments], before)
        self.assertEqual(w.bank.trial_balance()[1], 0)

    def test_disbursement_only_into_the_applicants_account(self):
        w = _World()
        w.bank.become_customer(w.a, w.rm, "RETAIL")
        own = w.bank.open_deposit_account(CurrentAccount, w.cur, [w.a], w.rm)
        app = w.bank.submit_financing_application(w.co, w.fin, 100_000, 6, "wc", w.a)
        w.bank.decide_application(app, w.credit, True, 100_000, "0.12")
        with self.assertRaises(BankingError):
            w.bank.disburse_financing(app, own, date(2026, 2, 1), w.credit)


class HistoryTests(unittest.TestCase):
    def test_correction_keeps_past_value(self):
        w = _World()
        w.bank.advance_to(date(2026, 1, 10))
        w.bank.correct_party_detail(w.co, "registered_address", "New Address", "typo", w.rm)
        self.assertEqual(w.co.detail_on("registered_address", date(2026, 1, 5)), "Old Address")
        self.assertEqual(w.co.detail("registered_address"), "New Address")

    def test_evidence_snapshot_is_not_rewritten_by_correction(self):
        w = _World()
        inv = w.bank.open_investigation(w.co, "review", w.compliance)
        ev = w.bank.add_evidence(inv, "profile", w.co, {"addr": w.co.detail("registered_address")}, w.compliance)
        w.bank.correct_party_detail(w.co, "registered_address", "New Address", "typo", w.rm)
        self.assertEqual(ev.snapshot["addr"], "Old Address")

    def test_risk_case_cannot_close_with_live_restriction(self):
        w = _World()
        inv = w.bank.open_investigation(w.co, "review", w.compliance)
        r = w.bank.impose_restriction(w.co, "FULL_FREEZE", "review", w.compliance, inv)
        with self.assertRaises(InvalidStateError):
            w.bank.close_case(inv, "done", w.compliance)
        w.bank.lift_restriction(r, "ok", w.compliance)
        w.bank.close_case(inv, "done", w.compliance)
        self.assertEqual(inv.status.current, "CLOSED")

    def test_status_on_a_past_date(self):
        w = _World()
        w.bank.advance_to(date(2026, 1, 10))
        w.bank.report_card(w.card, "LOST", w.b)
        self.assertEqual(w.card.status.on(date(2026, 1, 5)), "ACTIVE")
        self.assertEqual(w.card.status.current, "BLOCKED_LOST")


class BriefCoverageTests(unittest.TestCase):
    """Features added after rereading the brief: segments, term deposits, bills, card
    controls, collections, audit, retention and search."""

    def test_sole_trader_is_a_person_with_a_trading_name(self):
        w = _World()
        with self.assertRaises(BankingError):
            w.bank.become_customer(w.co, w.rm, "SOLE_TRADER", "Co Traders")
        with self.assertRaises(BankingError):
            w.bank.become_customer(w.a, w.rm, "SOLE_TRADER")
        w.bank.become_customer(w.a, w.rm, "SOLE_TRADER", "Alpha Auto Parts")
        self.assertEqual(w.a.detail("trading_name"), "Alpha Auto Parts")

    def test_high_value_customer_needs_source_of_wealth(self):
        w = _World()
        with self.assertRaises(KycIncomplete):
            w.bank.become_customer(w.b, w.rm, "PRIVATE")
        sow = w.bank.add_identity_document(w.b, "SOURCE_OF_WEALTH", "SOW-1", date(2025, 12, 1), None, w.rm)
        w.bank.verify_party(w.b, sow, w.rm)
        self.assertIsNotNone(w.bank.become_customer(w.b, w.rm, "PRIVATE"))

    def _term_deposit(self, w, amount=1_000_000):
        ftd = w.bank.define_product("FTD6", "6-month deposit", "TERM_DEPOSIT", term_months=6,
                                    annual_rate="0.12", early_break_penalty="0.01")
        dep = w.bank.open_deposit_account(FixedTermDeposit, ftd, [w.co], w.rm, payout_account=w.acct)
        w.bank.transfer_between_accounts(w.acct, dep, amount, w.a)
        return dep

    def test_term_deposit_pays_out_at_maturity(self):
        w = _World()
        dep = self._term_deposit(w)
        self.assertEqual(w.bank.withdraw_cash(dep, 100, w.teller, w.a).status.current, "FAILED")
        self.assertEqual(w.bank.transfer_between_accounts(w.acct, dep, 10, w.a).status.current, "FAILED")
        before = w.acct.ledger_balance()
        w.bank.advance_to(dep.maturity_on)
        self.assertEqual(dep.status.current, "CLOSED")
        self.assertEqual(dep.ledger_balance(), 0)
        fees = sum((t.amount for t in w.bank.transactions.values()
                    if isinstance(t, FeeCharge) and t.account is w.acct), ZERO)
        self.assertEqual(w.acct.ledger_balance() - before + fees, money(1_000_000 + 60_000))
        self.assertEqual(w.bank.trial_balance()[1], 0)

    def test_breaking_a_term_deposit_forfeits_interest_and_charges_penalty(self):
        w = _World()
        dep = self._term_deposit(w)
        before = w.acct.ledger_balance()
        penalty = w.bank.break_term_deposit(dep, w.rm, "cash needed")
        self.assertEqual(penalty, money(10_000))
        self.assertEqual(w.acct.ledger_balance() - before, money(990_000))
        self.assertEqual(dep.status.current, "CLOSED")

    def test_bill_payment_rules(self):
        w = _World()
        lesco = w.bank.register_biller("LESCO", "Lahore Electric", "UTILITY")
        self.assertEqual(w.bank.pay_bill(w.acct, lesco, "0412", 8_000, w.c).status.current, "FAILED")
        self.assertEqual(w.bank.pay_bill(w.acct, lesco, "0412", 8_000, w.a).status.current, "POSTED")
        big = w.bank.pay_bill(w.acct, lesco, "0412", 700_000, w.b)
        self.assertEqual(big.status.current, "AWAITING_AUTHORISATION")
        w.bank.authorise_payment(big, w.a)
        self.assertEqual(big.status.current, "POSTED")
        w.bank.deactivate_biller(lesco, "contract ended")
        self.assertEqual(w.bank.pay_bill(w.acct, lesco, "0412", 1_000, w.a).status.current, "FAILED")
        self.assertEqual(w.bank.trial_balance()[1], 0)

    def test_card_controls_block_and_keep_history(self):
        w = _World()
        online = w.bank.add_card_control(w.card, "ONLINE", w.b)
        with self.assertRaises(AuthorityError):
            w.bank.add_card_control(w.card, "INTERNATIONAL", w.a)        # not the cardholder
        self.assertEqual(w.bank.card_purchase(w.card, "Web", 1_000, channel="ONLINE").status.current, "DECLINED")
        self.assertEqual(w.bank.card_purchase(w.card, "Shop", 1_000).status.current, "POSTED")
        w.bank.advance_to(date(2026, 1, 3))
        w.bank.remove_card_control(online, w.b)
        self.assertEqual(w.bank.card_purchase(w.card, "Web", 1_000, channel="ONLINE").status.current, "POSTED")
        self.assertTrue(online.blocks("ONLINE", "PK", "RETAIL", date(2026, 1, 2)))

    def test_collections_promise_is_marked_broken(self):
        w = _World()
        col_staff = w.bank.hire_employee(w.bank.register_person("Col", date(1990, 1, 1), "HR"),
                                         "COLLECTIONS_OFFICER", w.branch)
        fin = w.disbursed()
        w.bank.advance_to(date(2026, 2, 3))                          # first installment missed
        case = [c for c in w.bank.cases.values() if isinstance(c, CollectionsCase)][-1]
        with self.assertRaises(AuthorityError):
            w.bank.record_collections_contact(case, w.teller, "called")
        w.bank.assign_case(case, col_staff, "supervisor")
        promise = w.bank.record_collections_contact(case, col_staff, "will pay Friday", 110_000,
                                                    date(2026, 2, 6))
        w.bank.advance_to(date(2026, 2, 8))
        self.assertEqual(promise.status.current, "BROKEN")
        self.assertEqual(fin.status.current, "IN_ARREARS")

    def test_audit_report_needs_auditor_and_shows_role_at_time(self):
        w = _World()
        auditor = w.bank.hire_employee(w.bank.register_person("Aud", date(1980, 1, 1), "HR"), "AUDITOR", w.branch)
        w.disbursed()
        with self.assertRaises(AuthorityError):
            w.bank.approvals_and_authority_audit(w.teller, date(2026, 1, 1), date(2026, 12, 31))
        report = w.bank.approvals_and_authority_audit(auditor, date(2026, 1, 1), date(2026, 12, 31))
        self.assertTrue(any("acting as CREDIT_OFFICER" in line for line in report))
        self.assertTrue(any("GRANT_MANDATE" in line for line in report))

    def test_deletion_refused_archive_allowed(self):
        w = _World()
        s = w.bank.open_deposit_account(SavingsAccount, w.sav, [w.co], w.rm)
        with self.assertRaises(InvalidStateError):
            w.bank.archive_record(s, w.rm)                               # still open
        w.bank.close_account(s, "not needed", w.rm)
        with self.assertRaises(InvalidStateError):
            w.bank.request_deletion(s, w.rm)
        self.assertEqual(w.bank.retention_until(s), date(2036, 1, 1))
        w.bank.archive_record(s, w.rm)
        self.assertNotIn(s, w.bank.active_arrangements())
        self.assertIn(s.number, w.bank.arrangements)                     # archived, not deleted

    def test_only_unused_beneficiaries_can_be_deleted(self):
        w = _World()
        spare = w.bank.add_beneficiary(w.co, "Spare", "UBL", "5555666677778888", "Spare Ltd", w.a)
        w.bank.initiate_transfer(w.acct, w.ben, 1_000, w.a)
        with self.assertRaises(InvalidStateError):
            w.bank.delete_beneficiary(w.ben, w.rm)
        w.bank.delete_beneficiary(spare, w.rm)
        self.assertEqual(spare.status.current, "DELETED")

    def test_card_search_covers_the_replacement_chain(self):
        w = _World()
        old = w.bank.card_purchase(w.card, "Shop", 1_000)
        w.bank.report_card(w.card, "STOLEN", w.b)
        new_card = w.bank.replace_card(w.card, w.cards)
        new = w.bank.card_purchase(new_card, "Shop", 2_000)
        self.assertEqual(w.bank.search_transactions(card=new_card), [old, new])
        self.assertEqual(w.bank.search_transactions(card=new_card, include_card_chain=False), [new])


class ModelShapeTests(unittest.TestCase):
    """The brief's minimum scale and inheritance requirements, checked from the code."""

    def test_at_least_30_classes_and_30_operations(self):
        self.assertGreaterEqual(len(domain_classes()), 30)
        self.assertGreaterEqual(len(bank_operations()), 30)

    def test_multi_level_inheritance_exists(self):
        self.assertTrue(issubclass(CurrentAccount, DepositAccount) and issubclass(DepositAccount, Arrangement))
        self.assertTrue(issubclass(TransferPayment, CustomerPayment)
                        and issubclass(CustomerPayment, BankTransaction))
        self.assertTrue(issubclass(Company, Organization) and issubclass(Organization, Party))
        self.assertTrue(issubclass(ComplianceInvestigation, RiskCase) and issubclass(RiskCase, Case))

    def test_uml_diagrams_name_only_real_classes(self):
        names = {c.__name__ for c in domain_classes()}
        for _, _, layout, edges in _ASSOC_DIAGRAMS:
            self.assertTrue(set(layout) <= names)
            self.assertTrue(all(a in layout and b in layout for a, b, _, _ in edges))
        self.assertIn("overdraft_limit()  [implements]", _own_members(CurrentAccount)[1])
        self.assertIn("overdraft_limit()  {abstract}", _own_members(DepositAccount)[1])
        self.assertIn("check_debit()  [override]", _own_members(SavingsAccount)[1])
        self.assertIn("holds", _own_attributes(DepositAccount))

    def test_the_whole_demo_runs_and_balances(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            bank = run_demo()
        self.assertEqual(bank.trial_balance()[1], 0)



class AbstractionTests(unittest.TestCase):
    """Abstract base classes and polymorphism: the base of each hierarchy cannot be
    created, and behaviour that differs by class lives in the class, not in the Bank."""

    ABSTRACT = (Party, Organization, Arrangement, DepositAccount, BankTransaction,
                CustomerPayment, LoanTransaction, Case)

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            cls.bank = run_demo()

    def test_hierarchy_roots_are_abstract(self):
        for base in self.ABSTRACT:
            self.assertTrue(inspect.isabstract(base), base.__name__)
        with self.assertRaises(TypeError):
            BankTransaction(100, date(2026, 1, 1), "not a real kind of transaction")
        with self.assertRaises(TypeError):
            Party("Nobody in particular", date(2026, 1, 1))

    def test_every_leaf_class_is_concrete(self):
        for cls in domain_classes():
            if not cls.__subclasses__():
                self.assertFalse(inspect.isabstract(cls), cls.__name__)

    def test_every_transaction_names_its_counterparty(self):
        for txn in self.bank.transactions.values():
            self.assertTrue(txn.counterparty(), txn.txn_id)

    def test_position_is_polymorphic(self):
        meanings = {type(a).__name__: a.position()[1] for a in self.bank.arrangements.values()}
        self.assertEqual(meanings["CurrentAccount"], "held")
        self.assertEqual(meanings["FinancingAgreement"], "owed")

    def test_story_and_case_roles_need_no_type_checks(self):
        for method in (Bank.transaction_story, Bank.assign_case):
            self.assertNotIn("isinstance", inspect.getsource(method))
        transfer = next(t for t in self.bank.transactions.values() if isinstance(t, TransferPayment))
        self.assertTrue(any("beneficiary as sent" in line for line in transfer.story_lines()))
        self.assertEqual(CollectionsCase.handler_roles(None), Bank.COLLECTIONS_ROLES)


def lifecycle_classes():
    """(class, attribute name, Lifecycle) for every class that declares its own state machine."""
    out = []
    for cls in domain_classes():
        for attr in ("LIFECYCLE", "SALE_LIFECYCLE"):
            if isinstance(cls.__dict__.get(attr), Lifecycle):
                out.append((cls, attr, cls.__dict__[attr]))
    return out


class LifecycleTests(unittest.TestCase):
    """Every status change in the model follows its class's declared state machine."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            cls.bank = run_demo()

    def _histories(self):
        b = self.bank
        records = [*b.parties.values(), *b.arrangements.values(), *b.transactions.values(),
                   *b.cards.values(), *b.cases.values(), *b.employees.values(), *b.branches.values(),
                   *b.standing_orders.values(), *b.applications.values(), *b.billers.values(),
                   *b.beneficiaries.values(), *b.products.values()]
        for r in records:
            for attr in ("status", "sale_status"):
                h = getattr(r, attr, None)
                if isinstance(h, StatusHistory):
                    yield r, h
        for p in b.parties.values():
            if p.relationship:
                yield p.relationship, p.relationship.status

    def test_every_history_is_checked_and_every_move_was_allowed(self):
        seen = 0
        for record, h in self._histories():
            self.assertIsNotNone(h.lifecycle, type(record).__name__)
            self.assertEqual(h.changes[0].status, h.lifecycle.initial)
            for a, b in zip(h.changes, h.changes[1:]):
                self.assertTrue(h.lifecycle.allows(a.status, b.status), (type(record).__name__, a.status, b.status))
                seen += 1
        self.assertGreater(seen, 50)

    def test_an_illegal_move_is_refused_even_outside_the_bank(self):
        w = _World()
        w.bank.report_card(w.card, "STOLEN", w.b)
        w.bank.record_card_found(w.card, w.cards, "handed in")
        with self.assertRaises(InvalidStateError):
            w.card.status.change("ACTIVE", w.bank.today, "anyone")      # bypassing reactivate_card

    def test_lifecycles_are_inherited_and_extended(self):
        base = BankTransaction.LIFECYCLE
        for sub in (CustomerPayment, TransferPayment, CardPayment):
            for frm, moves in base.transitions.items():
                self.assertTrue(set(moves) <= set(sub.LIFECYCLE.transitions[frm]), sub.__name__)
        self.assertIs(CashTransaction.LIFECYCLE, base)                  # inherited unchanged
        self.assertIn("HELD_FOR_REVIEW", TransferPayment.LIFECYCLE.states)
        self.assertNotIn("HELD_FOR_REVIEW", CardPayment.LIFECYCLE.states)
        self.assertNotIn("CLOSED", FinancingAgreement.LIFECYCLE.states)  # replaced, not extended

    def test_every_state_machine_is_well_formed(self):
        for cls, _, lc in lifecycle_classes():
            reachable, todo = {lc.initial}, [lc.initial]
            while todo:
                for nxt in lc.transitions.get(todo.pop(), {}):
                    if nxt not in reachable:
                        reachable.add(nxt)
                        todo.append(nxt)
            self.assertEqual(reachable, set(lc.states), cls.__name__)
            for final in lc.final:
                self.assertFalse(lc.transitions.get(final), f"{cls.__name__}: {final} is final")

# =============================================================================
# PART 15 - Introspection, class diagram and UML diagram generators
# The diagram is drawn from the live classes, so it can never drift from the code.
# =============================================================================
def domain_classes():
    """Every domain class in this file (errors, tests and helpers excluded)."""
    module = sys.modules[__name__]
    out = []
    for name, obj in vars(module).items():
        if (isinstance(obj, type) and obj.__module__ == module.__name__ and not name.startswith("_")
                and not issubclass(obj, (BankingError, unittest.TestCase))):
            out.append(obj)
    return out


def error_classes():
    """The business-rule error hierarchy."""
    return [c for c in vars(sys.modules[__name__]).values()
            if isinstance(c, type) and issubclass(c, BankingError)]


def bank_operations():
    """Public operations of the Bank service (each checks rules and writes audit)."""
    return [n for n, f in vars(Bank).items() if callable(f) and not n.startswith("_")]


def inheritance_tree():
    """Text tree of every hierarchy with more than one class, plus standalone classes."""
    classes = domain_classes()
    local = set(classes)
    lines, standalone = [], []

    def walk(cls, depth):
        lines.append("    " * depth + ("" if depth == 0 else "-> ") + cls.__name__
                     + ("  (abstract)" if inspect.isabstract(cls) else ""))
        for sub in sorted((c for c in classes if c.__bases__[0] is cls), key=lambda c: c.__name__):
            walk(sub, depth + 1)

    for cls in classes:
        if cls.__bases__[0] not in local:
            if any(c.__bases__[0] is cls for c in classes):
                walk(cls, 0)
            else:
                standalone.append(cls.__name__)
    lines.append("")
    lines.append("Standalone (composition, not inheritance): " + ", ".join(sorted(standalone)))
    lines.append("")
    lines.append("Errors: " + " / ".join(c.__name__ for c in error_classes()))
    return lines


def write_class_diagram(folder):
    """Write class_diagram.svg (inheritance forest + standalone classes) into a folder."""
    import os
    classes = domain_classes()
    local = set(classes)
    children = {c: sorted((s for s in classes if s.__bases__[0] is c), key=lambda s: s.__name__)
                for c in classes}
    roots = [c for c in classes if c.__bases__[0] not in local and children[c]]
    standalone = sorted((c for c in classes if c.__bases__[0] not in local and not children[c]),
                        key=lambda c: c.__name__)
    box_w, box_h, gap_x, gap_y = 170, 30, 14, 62
    pos = {}

    def leaves(c):
        return max(1, sum(leaves(s) for s in children[c]))

    def place(c, x0, depth, top):
        width = leaves(c) * (box_w + gap_x)
        pos[c] = (x0 + width / 2 - box_w / 2, top + depth * gap_y)
        x = x0
        for s in children[c]:
            place(s, x, depth + 1, top)
            x += leaves(s) * (box_w + gap_x)

    def depth_of(c):
        return 1 + max((depth_of(s) for s in children[c]), default=0)

    # lay the hierarchies out in rows no wider than ~1900px
    max_w, x, top, row_h = 1900, 20, 70, 0
    for r in roots:
        w = leaves(r) * (box_w + gap_x)
        if x + w > max_w and x > 20:
            x, top, row_h = 20, top + row_h + 40, 0
        place(r, x, 0, top)
        x += w + 30
        row_h = max(row_h, depth_of(r) * gap_y)
    top += row_h + 50
    per_row = 10
    for i, c in enumerate(standalone):
        pos[c] = (20 + (i % per_row) * (box_w + gap_x), top + 30 + (i // per_row) * (box_h + 16))
    width = max(p[0] for p in pos.values()) + box_w + 30
    height = max(p[1] for p in pos.values()) + box_h + 40

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
           f'font-family="Helvetica, Arial, sans-serif" font-size="12">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<text x="20" y="32" font-size="20" font-weight="bold" fill="#1d2b3a">Problem 4 banking model - '
           'inheritance hierarchies (arrow points to the parent class; italic = abstract)</text>',
           f'<text x="20" y="{top + 12:.0f}" font-size="15" font-weight="bold" fill="#1d2b3a">Standalone classes '
           '(related by composition / references, deliberately not inheritance)</text>',
           '<defs><marker id="tri" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="9" markerHeight="9" '
           'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#ffffff" stroke="#4a6076"/></marker></defs>']
    for c in classes:
        if c.__bases__[0] in local and c in pos:
            px, py = pos[c.__bases__[0]]
            cx, cy = pos[c]
            svg.append(f'<line x1="{cx + box_w / 2:.0f}" y1="{cy:.0f}" x2="{px + box_w / 2:.0f}" '
                       f'y2="{py + box_h:.0f}" stroke="#4a6076" marker-end="url(#tri)"/>')
    for c, (cx, cy) in pos.items():
        is_root = c in roots
        fill = "#d8e6f3" if is_root else ("#eef3f8" if c not in standalone else "#f6f6f2")
        weight = ' font-weight="bold"' if is_root else ""
        if inspect.isabstract(c):
            weight += ' font-style="italic"'           # UML: abstract classes in italics
        svg.append(f'<rect x="{cx:.0f}" y="{cy:.0f}" width="{box_w}" height="{box_h}" rx="6" '
                   f'fill="{fill}" stroke="#4a6076"/>')
        svg.append(f'<text x="{cx + box_w / 2:.0f}" y="{cy + 19:.0f}" text-anchor="middle" '
                   f'fill="#1d2b3a"{weight}>'
                   f'{c.__name__}</text>')
    svg.append("</svg>")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "class_diagram.svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(svg))
    return path


def _own_attributes(cls):
    """Instance attributes first assigned in this class's own __init__ (read from the source)."""
    import ast
    import inspect
    import textwrap
    init = cls.__dict__.get("__init__")
    if init is None:
        return []
    tree = ast.parse(textwrap.dedent(inspect.getsource(init)))
    names = []
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            for el in (t.elts if isinstance(t, ast.Tuple) else [t]):
                if (isinstance(el, ast.Attribute) and isinstance(el.value, ast.Name)
                        and el.value.id == "self" and el.attr not in names):
                    names.append(el.attr)
    return [n for n in names if not n.startswith("_")] + [n for n in names if n.startswith("_")]


def _own_members(cls):
    """(class constants, methods) defined or overridden at this level. A method is
    marked {abstract} if declared without a body here, [implements] if it fills in a
    parent's abstract method, and [override] if it replaces or extends a parent's."""
    consts, methods = [], []
    for name, value in cls.__dict__.items():
        if name.startswith("__"):
            continue
        if callable(value) or isinstance(value, property):
            parent = next((b.__dict__[name] for b in cls.__mro__[1:] if name in b.__dict__), None)
            if getattr(value, "__isabstractmethod__", False):
                mark = "  {abstract}"
            elif parent is None:
                mark = ""
            elif getattr(parent, "__isabstractmethod__", False):
                mark = "  [implements]"
            else:
                mark = "  [override]"
            methods.append(name + "()" + mark)
        elif name.isupper() or name in ("prefix", "id_prefix", "officer_title"):
            consts.append(name)
    return consts, methods


def _svg_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_uml_diagrams(folder):
    """Write one UML class diagram per inheritance hierarchy (attributes and methods that
    each level adds) and three association diagrams. Returns the file paths."""
    import os
    os.makedirs(folder, exist_ok=True)
    classes = domain_classes()
    children = {c: sorted((s for s in classes if s.__bases__[0] is c), key=lambda s: s.__name__)
                for c in classes}
    hierarchies = [("uml_parties", Party), ("uml_arrangements", Arrangement),
                   ("uml_transactions", BankTransaction), ("uml_cases", Case)]
    paths = []
    box_w, line_h, gap_x, gap_y = 250, 14, 18, 46

    def compartments(c):
        consts, methods = _own_members(c)
        attrs = _own_attributes(c)
        return [c.__name__], [("+ " + a) for a in consts] + [("- " + a) for a in attrs], methods

    def height(c):
        head, attrs, methods = compartments(c)
        return 24 + (max(1, len(attrs)) + max(1, len(methods))) * line_h + 16

    for fname, root in hierarchies:
        pos = {}

        def leaves(c):
            return max(1, sum(leaves(s) for s in children[c]))

        level_h = {}

        def depth_scan(c, d):
            level_h[d] = max(level_h.get(d, 0), height(c))
            for s in children[c]:
                depth_scan(s, d + 1)

        depth_scan(root, 0)
        tops = {0: 60}
        for d in range(1, len(level_h)):
            tops[d] = tops[d - 1] + level_h[d - 1] + gap_y

        def place(c, x0, d):
            width = leaves(c) * (box_w + gap_x)
            pos[c] = (x0 + width / 2 - box_w / 2, tops[d])
            x = x0
            for s in children[c]:
                place(s, x, d + 1)
                x += leaves(s) * (box_w + gap_x)

        place(root, 20, 0)
        width = max(p[0] for p in pos.values()) + box_w + 30
        total_h = max(pos[c][1] + height(c) for c in pos) + 30
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{total_h:.0f}" '
               f'font-family="Helvetica, Arial, sans-serif" font-size="11">',
               '<rect width="100%" height="100%" fill="#ffffff"/>',
               '<defs><marker id="tri" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="11" '
               'markerHeight="11" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#ffffff" '
               'stroke="#34495e"/></marker></defs>',
               f'<text x="20" y="30" font-size="17" font-weight="bold" fill="#1d2b3a">{root.__name__} '
               'hierarchy - what each level adds (- attribute, + class constant, () method; '
               'italic = abstract)</text>']
        for c in pos:
            if c is not root:
                px, py = pos[c.__bases__[0]]
                cx, cy = pos[c]
                ph = height(c.__bases__[0])
                mid = py + ph + gap_y / 2
                svg.append(f'<polyline points="{cx + box_w / 2:.0f},{cy:.0f} {cx + box_w / 2:.0f},{mid:.0f} '
                           f'{px + box_w / 2:.0f},{mid:.0f} {px + box_w / 2:.0f},{py + ph:.0f}" fill="none" '
                           f'stroke="#34495e" marker-end="url(#tri)"/>')
        for c, (x, y) in pos.items():
            head, attrs, methods = compartments(c)
            h = height(c)
            svg.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{box_w}" height="{h}" fill="#f4f8fb" '
                       f'stroke="#34495e"/>')
            svg.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{box_w}" height="22" fill="#d8e6f3" '
                       f'stroke="#34495e"/>')
            abstract = inspect.isabstract(c)            # UML: abstract names in italics
            style = ' font-style="italic"' if abstract else ""
            label = ("«abstract» " if abstract else "") + head[0]
            svg.append(f'<text x="{x + box_w / 2:.0f}" y="{y + 15:.0f}" text-anchor="middle" '
                       f'font-weight="bold" font-size="12" fill="#1d2b3a"{style}>{label}</text>')
            ty = y + 22 + line_h
            for a in attrs or ["(inherits all attributes)"]:
                svg.append(f'<text x="{x + 6:.0f}" y="{ty:.0f}" fill="#1d2b3a">{_svg_text(a)}</text>')
                ty += line_h
            svg.append(f'<line x1="{x:.0f}" y1="{ty - line_h + 5:.0f}" x2="{x + box_w:.0f}" '
                       f'y2="{ty - line_h + 5:.0f}" stroke="#34495e"/>')
            ty += 4
            for m in methods or ["(no new methods)"]:
                color = ("#9c3d10" if "override" in m else "#1f6f3a" if "implements" in m
                         else "#1d2b3a")
                italic = ' font-style="italic"' if "{abstract}" in m else ""
                svg.append(f'<text x="{x + 6:.0f}" y="{ty:.0f}" fill="{color}"{italic}>{_svg_text(m)}</text>')
                ty += line_h
        svg.append("</svg>")
        path = os.path.join(folder, fname + ".svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(svg))
        paths.append(path)
    paths += _write_association_diagram(folder)
    return paths


# Association diagrams, one per area. Layout = hand-placed (column, row) grid cells chosen
# so every line joins neighbouring boxes. Edge = (from, to, label, composition?), where
# composition means the owner keeps a dated history of these.
_ASSOC_DIAGRAMS = [
    ("uml_assoc_parties", "Parties, roles and staff", {
        "BeneficialOwnership": (0, 0), "Organization": (1, 0), "OfficerRole": (2, 0), "Approval": (4, 0),
        "Mandate": (1, 1), "Person": (2, 1), "Employee": (3, 1), "RoleAssignment": (4, 1),
        "IdentityDocument": (0, 2), "Party": (1, 2), "CustomerRelationship": (2, 2), "Branch": (4, 2),
        "VerificationCheck": (0, 3), "Correction": (1, 3), "Restriction": (2, 3),
    }, [
        ("Organization", "BeneficialOwnership", "owners *", True),
        ("Organization", "OfficerRole", "officers *", True),
        ("Organization", "Mandate", "mandates *", True), ("OfficerRole", "Person", "held by", False),
        ("Mandate", "Person", "for", False), ("Employee", "Person", "is", False),
        ("Employee", "RoleAssignment", "*", True), ("RoleAssignment", "Branch", "at", False),
        ("Approval", "Employee", "role frozen", False), ("Party", "IdentityDocument", "*", True),
        ("Party", "VerificationCheck", "*", True), ("Party", "Correction", "*", True),
        ("Party", "CustomerRelationship", "0..1", True), ("Party", "Restriction", "*", True),
        ("CustomerRelationship", "Employee", "RM history", False),
        ("CustomerRelationship", "Branch", "home branch history", False),
    ]),
    ("uml_assoc_accounts", "Products, accounts and payments", {
        "ProductDefinition": (0, 0), "ProductTermsVersion": (1, 0), "Arrangement": (2, 0), "Party": (3, 0),
        "Notice": (4, 0), "Statement": (0, 1), "Restriction": (2, 1),
        "Biller": (4, 1), "AccountHold": (0, 2), "DepositAccount": (1, 2), "IssuedCard": (2, 2),
        "CardControl": (3, 2), "BillPayment": (4, 2),
        "GeneralLedgerAccount": (0, 3), "LedgerEntry": (1, 3), "BankTransaction": (2, 3), "Reversal": (3, 3),
        "StandingOrder": (0, 4), "Beneficiary": (1, 4), "CustomerPayment": (3, 4), "Mandate": (4, 4),
        "BeneficiaryVersion": (1, 5), "TransferPayment": (2, 5), "Dispute": (3, 5),
        "PaymentAuthorisation": (4, 5),
    }, [
        ("ProductDefinition", "ProductTermsVersion", "1..*", True),
        ("Arrangement", "ProductTermsVersion", "pinned", False), ("Arrangement", "Party", "holders", False),
        ("Notice", "Party", "to", False), ("Arrangement", "Restriction", "*", True),
        ("Statement", "DepositAccount", "of", False), ("DepositAccount", "AccountHold", "*", True),
        ("IssuedCard", "DepositAccount", "draws on", False), ("DepositAccount", "LedgerEntry", "*", True),
        ("GeneralLedgerAccount", "LedgerEntry", "*", True), ("LedgerEntry", "BankTransaction", "from", False),
        ("Reversal", "BankTransaction", "original", False), ("StandingOrder", "Beneficiary", "pays", False),
        ("Beneficiary", "BeneficiaryVersion", "1..*", True),
        ("TransferPayment", "BeneficiaryVersion", "snapshot", False),
        ("CustomerPayment", "Mandate", "authority used", False),
        ("CustomerPayment", "PaymentAuthorisation", "2nd signatory", True),
        ("Dispute", "CustomerPayment", "disputes", False),
        ("IssuedCard", "CardControl", "controls *", True), ("BillPayment", "Biller", "pays", False),
    ]),
    ("uml_assoc_lending_cases", "Lending and cases", {
        "Approval": (0, 0), "FinancingApplication": (1, 0), "ApprovalCondition": (2, 0),
        "CollectionsCase": (0, 1), "FinancingAgreement": (1, 1), "RepaymentSchedule": (2, 1),
        "Installment": (3, 1), "PromiseToPay": (0, 2), "DepositAccount": (1, 2),
        "CaseEvidence": (0, 3), "Case": (1, 3), "CaseNote": (2, 3),
        "Dispute": (0, 4), "RiskCase": (1, 4), "Restriction": (2, 4), "CustomerPayment": (0, 5),
    }, [
        ("FinancingApplication", "Approval", "decision", False),
        ("FinancingApplication", "ApprovalCondition", "*", True),
        ("FinancingAgreement", "FinancingApplication", "from", False),
        ("FinancingAgreement", "RepaymentSchedule", "versions", True),
        ("RepaymentSchedule", "Installment", "*", True),
        ("CollectionsCase", "FinancingAgreement", "agreement", False),
        ("CollectionsCase", "PromiseToPay", "promises *", True),
        ("FinancingAgreement", "DepositAccount", "settlement account", False),
        ("Case", "CaseEvidence", "snapshots", True), ("Case", "CaseNote", "*", True),
        ("RiskCase", "Restriction", "imposed", True), ("Dispute", "CustomerPayment", "disputes", False),
    ]),
]


def _write_association_diagram(folder):
    """Write the three association diagrams; returns their paths."""
    return [_write_one_association_diagram(folder, *spec) for spec in _ASSOC_DIAGRAMS]


def _write_one_association_diagram(folder, fname, title, layout, edges):
    """Filled diamond = the owner keeps a dated history of these; arrow = reference."""
    import os
    cell_w, cell_h, box_w, box_h = 250, 96, 190, 30
    centre = {n: (30 + c * cell_w + box_w / 2, 70 + r * cell_h + box_h / 2) for n, (c, r) in layout.items()}
    width = 30 + (max(c for c, _ in layout.values()) + 1) * cell_w
    height = 70 + (max(r for _, r in layout.values()) + 1) * cell_h
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'font-family="Helvetica, Arial, sans-serif" font-size="11">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" '
           'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#34495e"/></marker>'
           '<marker id="dia" viewBox="0 0 16 10" refX="0" refY="5" markerWidth="14" markerHeight="9" '
           'orient="auto"><path d="M0,5 L8,0 L16,5 L8,10 z" fill="#34495e"/></marker></defs>',
           f'<text x="30" y="30" font-size="17" font-weight="bold" fill="#1d2b3a">Associations: {title}</text>',
           '<text x="30" y="50" font-size="12" fill="#4a6076">filled diamond = the owner keeps a dated '
           'history of these; arrow = reference to another record</text>']

    def edge_point(a, b):
        """Point where the line from centre a towards centre b leaves a's box."""
        (ax, ay), (bx, by) = a, b
        dx, dy = bx - ax, by - ay
        sx = (box_w / 2) / abs(dx) if dx else float("inf")
        sy = (box_h / 2) / abs(dy) if dy else float("inf")
        k = min(sx, sy)
        return ax + dx * k, ay + dy * k

    for src, dst, label, comp in edges:
        x1, y1 = edge_point(centre[src], centre[dst])
        x2, y2 = edge_point(centre[dst], centre[src])
        marks = 'marker-start="url(#dia)"' if comp else 'marker-end="url(#arr)"'
        svg.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#34495e" '
                   f'stroke-width="1.2" {marks}/>')
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        w = 6.2 * len(label) + 8
        svg.append(f'<rect x="{mx - w / 2:.0f}" y="{my - 8:.0f}" width="{w:.0f}" height="15" rx="3" '
                   f'fill="#ffffff"/>')
        svg.append(f'<text x="{mx:.0f}" y="{my + 3:.0f}" text-anchor="middle" fill="#5a3d8a" '
                   f'font-size="10.5">{label}</text>')
    for name, (cx, cy) in centre.items():
        svg.append(f'<rect x="{cx - box_w / 2:.0f}" y="{cy - box_h / 2:.0f}" width="{box_w}" '
                   f'height="{box_h}" rx="5" fill="#eef3f8" stroke="#34495e"/>')
        svg.append(f'<text x="{cx:.0f}" y="{cy + 4:.0f}" text-anchor="middle" font-weight="bold" '
                   f'fill="#1d2b3a">{name}</text>')
    svg.append("</svg>")
    path = os.path.join(folder, fname + ".svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(svg))
    return path


# =============================================================================
# PART 16 - Command line
# =============================================================================
def main(argv=None):
    """Entry point: demo by default; --test, --classes or --diagram DIR otherwise."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--test" in argv:
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if "--classes" in argv:
        print("\n".join(inheritance_tree()))
        print(f"\n{len(domain_classes())} domain classes, {len(error_classes())} error classes, "
              f"{len(bank_operations())} Bank operations")
        return 0
    if "--diagram" in argv:
        i = argv.index("--diagram")
        folder = argv[i + 1] if i + 1 < len(argv) else "."
        for path in [write_class_diagram(folder)] + write_uml_diagrams(folder):
            print("written", path)
        return 0
    run_demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
