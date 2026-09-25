# Project Presentation 1: speech and preparation

**Khizar Rizwan**, Problem 4: Commercial Banking, Lending, Payments and Compliance
CS2012 Introduction to Object-Oriented Programming, instructor Bilal Nadeem

Slides: `docs/Progress_Presentation_1.pptx` (8 slides). The same speech is in each slide's speaker notes.

## What to submit on Google Classroom

1. **`Progress_Presentation_1.pptx`**, the slide deck (the main submission).
2. Optionally, this speech as `Progress_Presentation_1_Speech.docx`, if the class accepts a second file. The brief says "only one submission per group member", so if only one file is allowed, submit the deck.

Before submitting, open the deck in PowerPoint, type your roll number on slide 1, and check that nothing overlaps.

## How the talk earns each part of the 40 marks

| Criterion (10 marks each) | Where it is earned |
|---|---|
| Content delivery | A timed script (below), one idea per slide, and every claim backed by something on screen |
| Progress | Slide 2: seven planned phases with their status, and five numbers measured from the code; slide 8: the remaining steps |
| Sequencing | The talk follows the order the work was done: progress, research, design, build, next. The tracker at the top of every slide shows where you are |
| Diagrams | Five kinds: a progress timeline, the class diagram, two UML inheritance diagrams, a flowchart in standard symbols and a UML state machine |

## The speech (about 5 minutes, 700 words)

Speak at a steady pace, about 140 words a minute. The times in brackets are checkpoints: if you are behind, shorten the next slide rather than rushing.

### Slide 1: Title (0:00 to 0:20)

Assalam-o-Alaikum. I am Khizar Rizwan, and my project is Problem 4: a commercial bank modelled with classes and inheritance. In five minutes I will show where the project stands, the research behind the design, the class and inheritance diagrams, one workflow and one lifecycle, and what I will do next.

### Slide 2: Where the project stands (0:20 to 1:05)

Here is my progress. I planned seven phases. The first five are complete: research, assumptions, the class design, the core implementation with tests, and a seeded demonstration with a desktop interface.

The numbers underneath are measured from the code: 71 business classes, 98 operations, four multi-level inheritance hierarchies, 16 scenarios where the normal workflow breaks, and 73 automated tests that all pass. The brief asks for at least 30 classes and 30 operations, so the minimum is covered. I am now in phase six, refining the design with your feedback, and phase seven is the final report and viva.

### Slide 3: Research changed the design (1:05 to 1:50)

Before designing I researched how banks actually work, and three findings changed my design.

First, know-your-customer rules treat customer, director, owner and signatory as roles of one person. So I have one Person class, and the roles are separate dated objects, not subclasses.

Second, banks never erase a wrong payment; they post a new entry that counteracts it. So a Reversal, and a card Chargeback, are new transactions linked to the original.

Third, a bank product can stop being sold while existing customers keep it on their old terms. So I separated the product definition from the customer's own arrangement.

### Slide 4: Class model after research (1:50 to 2:30)

This is the class diagram. It is generated from the code itself, so it always matches the program.

There are four hierarchies: parties, arrangements, transactions and cases. Everything else, like cards, mandates, branches and employees, is a standalone class connected by association, because those things are related to each other but are not kinds of each other. That was my main rule: inheritance only for an is-a relationship where the parent's data genuinely belongs to every child.

### Slide 5: Multi-level inheritance, and what I rejected (2:30 to 3:15)

Here are two of the multi-level hierarchies as UML. Party, then Organization, then Company and Charity: an organization adds registration and officers, and each subclass adds its own rule; for example, a charity needs two trustees. Arrangement, then DepositAccount, then current, savings and term deposit: every deposit account has a ledger and a balance, and each subclass changes only one behaviour.

On the right are tempting inheritances I rejected. A customer is a role with a start and an end, not a kind of person. A card holds no money, so it is not an account. A sole trader is legally the person. And a merchant refund is not a reversal, because the original purchase stays valid.

### Slide 6: One workflow end to end (3:15 to 3:50)

This flowchart shows one complete workflow: a large transfer from the company account through digital banking, exactly the case in the brief. The code checks the rules in this order: authority, then funds and limits, then dual control, where a second signatory must approve, then the compliance hold for review. If any rule fails, the payment is not thrown away; it is kept as a failed transaction with the reason, so the history is complete.

### Slide 7: A lifecycle the code enforces (3:50 to 4:30)

Records also change over time, so each class declares its lifecycle. This UML state machine for a card is drawn from that declaration, and the same declaration is enforced in the code. It covers the brief's critical case: a card is reported stolen and blocked, then replaced with a different limit, and when the old card is found it is destroyed, never re-activated. Every old payment still names the exact card that was used, and an illegal move, like destroyed back to active, is refused.

### Slide 8: Next steps (4:30 to 5:00)

To finish, my next steps. Now, I will refine the model with your feedback from today. Next, I will add saving and loading the bank's records with files and JSON, which we cover in the course, and review the design against SOLID and the design patterns we will study. Finally, I will complete the report and prepare for the viva. Thank you; I am happy to take questions.

## Questions you may be asked, with short answers

**Why is Customer not a subclass of Person?** Being a customer is a role that starts and ends. Ayesha is a customer, a director and a signatory at the same time. Subclasses would force three records for one real person, and the history would break when a role ends.

**Where is your multi-level inheritance?** Four places. For example, Party › Organization › Company, and BankTransaction › Reversal › Chargeback.

**Why is a reversal a new record instead of deleting the payment?** Banks never erase history. The original payment stays posted, and the reversal counteracts it, so the books still balance and an auditor can see both.

**How do you show authority that existed in the past?** A Mandate has a validity period. Revoking it closes the period instead of deleting it, and every payment stores the mandate it used, so "could Bilal pay on 11 April 2026?" is still answerable.

**What does the product-versus-arrangement split buy you?** A product can close to new customers while existing holders keep the terms version they signed up under, without rewriting their history.

**What is not done yet?** Saving to files or JSON, a SOLID and design-pattern review, and the final report and viva. These are on slide 8.

## Rehearsal checklist

- Time yourself twice with a phone stopwatch. Stop at 5:00 even if you have not finished.
- Point at the diagram while you describe it, for example the Party › Organization › Company path on slide 5.
- Keep the demo ready as a backup: `python banking_gui.py`, but only if the instructor asks. The talk does not depend on it.
