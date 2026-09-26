# Project Presentation 1: speech (Urdu) and preparation

**Khizar Rizwan (25L-5668)**, Problem 4: Commercial Banking, Lending, Payments and Compliance
CS2012 Introduction to Object-Oriented Programming, instructor Bilal Nadeem

Slides: `docs/Progress_Presentation_1.pptx` (9 slides). The Roman Urdu speech is also in each slide's speaker notes.

## What to submit on Google Classroom

1. **`Progress_Presentation_1.pptx`**, the slide deck (the main submission).
2. Optionally, this document (`Progress_Presentation_1_Speech.docx`), if a second file is allowed. The brief says "only one submission per group member", so if only one file is allowed, submit the deck.

## How the talk earns each part of the 40 marks

| Criterion (10 marks each) | Where it is earned |
|---|---|
| Content delivery | A timed script, one idea per slide, every claim backed by something on screen |
| Progress | Slide 2: six phases with their status and five numbers; slide 8: what is built and what is in progress; slide 9: remaining steps |
| Sequencing | Progress, research, design, build, next: the order the work was done. The tracker at the top of every slide shows where you are |
| Diagrams | A progress timeline, the class diagram, two UML inheritance diagrams, a flowchart in standard symbols and a GUI screen |

## Speech in Urdu (about 5 minutes)

Keep technical words (class, inheritance, mandate, reversal) in English, as written. Speak calmly; the times in brackets are checkpoints.

### سلائیڈ 1: تعارف (0:00 تا 0:20)

السلام علیکم۔ میرا نام خضر رضوان ہے، رول نمبر 25L-5668۔ میرا پروجیکٹ Problem 4 ہے: ایک commercial bank کا object-oriented model، جس میں customers، loans، payments، cards اور compliance سب شامل ہیں۔ اگلے پانچ منٹ میں میں آپ کو اپنی research، design، اب تک کی progress اور اگلے steps دکھاؤں گا۔

### سلائیڈ 2: پروجیکٹ کہاں کھڑا ہے (0:20 تا 0:55)

میں نے پروجیکٹ کو چھ phases میں plan کیا۔ پہلے تین phases مکمل ہیں: domain research، assumptions اور requirements، اور class اور inheritance design۔ چوتھا phase، یعنی Python implementation، اس وقت جاری ہے، اور اس کے ساتھ Tkinter GUI پر بھی کام چل رہا ہے۔ آخری phase final report اور viva ہے۔ نیچے دیے گئے numbers میری research اور design کے ہیں: آٹھ sources، ستائیس banking terms، چھتیس documented assumptions، اور اکہتر classes کا design، جن میں چار multi-level hierarchies ہیں۔

### سلائیڈ 3: ریسرچ (0:55 تا 1:40)

Brief کہتا ہے کہ model بنانے سے پہلے industry کو سمجھو۔ اس لیے میں نے آٹھ sources study کیے۔ FATF Recommendations اور State Bank of Pakistan کی AML regulations سے customer due diligence اور beneficial ownership سمجھا۔ Basel Committee سے risk management۔ ISO 20022 سے payment کا lifecycle، کہ payment صرف "ہوئی" یا "نہیں ہوئی" نہیں ہوتی، بلکہ pending، held، posted اور failed جیسے statuses سے گزرتی ہے۔ Visa اور Mastercard کے dispute rules سے reversal، refund اور chargeback کا فرق۔ IFRS 9 سے loan restructuring، BIAN سے product اور customer agreement کا فرق، اور Martin Fowler کی Analysis Patterns سے roles اور time-dated records۔

### سلائیڈ 4: ریسرچ نے design کیسے بدلا (1:40 تا 2:20)

اس research نے میرا design بدل دیا۔ پہلے میرا خیال تھا کہ Customer، Person کی subclass ہوگی۔ لیکن KYC rules بتاتے ہیں کہ customer، director، owner اور signatory ایک ہی انسان کے roles ہیں۔ اس لیے ایک Person class ہے، اور roles الگ، dated objects ہیں۔ دوسرا: bank کبھی غلط payment کو مٹاتا نہیں، بلکہ نئی entry post کرتا ہے۔ اس لیے Reversal اور Chargeback نئی transactions ہیں۔ تیسرا: product بند ہو جائے تو پرانے customers اپنی پرانی terms پر رہتے ہیں، اس لیے ProductDefinition اور customer کا Arrangement الگ classes ہیں۔

### سلائیڈ 5: Class diagram (2:20 تا 2:50)

یہ research کے بعد کا class diagram ہے۔ اس میں چار hierarchies ہیں: Party، Arrangement، BankTransaction اور Case۔ باقی چیزیں، جیسے cards، mandates، branches اور employees، association سے جڑی ہیں، کیونکہ وہ ایک دوسرے سے related ہیں مگر ایک دوسرے کی قسم نہیں۔ میرا اصول یہ تھا: inheritance صرف وہاں جہاں سچ مچ "is-a" رشتہ ہو۔

### سلائیڈ 6: Multi-level inheritance (2:50 تا 3:25)

یہ دو multi-level hierarchies UML میں ہیں۔ Party سے Organization، اور Organization سے Company اور Charity۔ اور Arrangement سے DepositAccount، پھر Current، Savings اور Term Deposit۔ Shared data ہمیشہ اس سب سے اونچے level پر ہے جہاں ہر subclass کو اس کی ضرورت ہے۔ دائیں طرف وہ inheritance ہے جو میں نے سوچ کر reject کی: card account نہیں کیونکہ اس میں پیسہ نہیں ہوتا، sole trader الگ legal entity نہیں، اور merchant refund، reversal نہیں کیونکہ اصل purchase valid رہتی ہے۔

### سلائیڈ 7: ایک مکمل workflow (3:25 تا 3:55)

یہ flowchart ایک پورا workflow دکھاتا ہے: digital banking سے ایک بڑا transfer، جو brief کا اپنا case ہے۔ پہلے authority check ہوتی ہے، پھر funds اور limit، پھر dual control جہاں دوسرے signatory کی approval چاہیے، اور پھر compliance review۔ اگر کوئی rule fail ہو تو payment مٹتی نہیں، بلکہ وجہ کے ساتھ record میں رہتی ہے۔

### سلائیڈ 8: Implementation اور GUI (3:55 تا 4:35)

اب implementation کی progress۔ Core model Python میں بن رہا ہے: parties، accounts، transactions اور double-entry ledger کا کام ہو چکا ہے، اور ہر rule کے ساتھ test لکھ رہا ہوں۔ اس وقت میں cards اور lending کے workflows اور brief کے exception scenarios پر کام کر رہا ہوں۔ ساتھ ہی Tkinter میں GUI کا prototype بن رہا ہے، یہ اس کی screen ہے، جہاں staff اور customer دونوں اپنے role کے حساب سے کام کر سکیں گے۔ اور میں ایک AI assistant بھی جوڑ رہا ہوں، جو Claude API سے bank کے records پڑھ کر سوالوں کا جواب دیتا ہے، مگر خود کوئی record نہیں بدل سکتا۔

### سلائیڈ 9: اگلے steps (4:35 تا 5:00)

اگلے steps: implementation اور GUI مکمل کرنا، brief کے ہر critical case کو automated tests سے check کرنا، files اور JSON سے data save کرنا، اور SOLID principles کے مطابق design review کرنا۔ آخر میں final report اور viva۔ شکریہ، میں سوالات کے لیے حاضر ہوں۔

## Speech in Roman Urdu

The same speech, for reading aloud. This version is also in the slides' speaker notes.

### Slide 1 (0:00-0:20)

Assalam-o-Alaikum. Mera naam Khizar Rizwan hai, roll number 25L-5668. Mera project Problem 4 hai: ek commercial bank ka object-oriented model, jis mein customers, loans, payments, cards aur compliance sab shamil hain. Agle paanch minute mein main aap ko apni research, design, ab tak ki progress aur agle steps dikhaunga.

### Slide 2 (0:20-0:55)

Main ne project ko chhe phases mein plan kiya. Pehle teen phases mukammal hain: domain research, assumptions aur requirements, aur class aur inheritance design. Chautha phase, yani Python implementation, is waqt jaari hai, aur us ke saath Tkinter GUI par bhi kaam chal raha hai. Aakhri phase final report aur viva hai. Neeche diye gaye numbers meri research aur design ke hain: aath sources, sattaees banking terms, chhattees documented assumptions, aur ikhattar classes ka design, jin mein chaar multi-level hierarchies hain.

### Slide 3 (0:55-1:40)

Brief kehta hai ke model banane se pehle industry ko samjho. Is liye main ne aath sources study kiye. FATF Recommendations aur State Bank of Pakistan ki AML regulations se customer due diligence aur beneficial ownership samjha. Basel Committee se risk management. ISO 20022 se payment ka lifecycle, ke payment sirf "hui" ya "nahi hui" nahi hoti, balkay pending, held, posted aur failed jaise statuses se guzarti hai. Visa aur Mastercard ke dispute rules se reversal, refund aur chargeback ka farq. IFRS 9 se loan restructuring, BIAN se product aur customer agreement ka farq, aur Martin Fowler ki Analysis Patterns se roles aur time-dated records.

### Slide 4 (1:40-2:20)

Is research ne mera design badal diya. Pehle mera khayal tha ke Customer, Person ki subclass hogi. Lekin KYC rules batate hain ke customer, director, owner aur signatory ek hi insaan ke roles hain. Is liye ek Person class hai, aur roles alag, dated objects hain. Doosra: bank kabhi galat payment ko mitata nahi, balkay nayi entry post karta hai. Is liye Reversal aur Chargeback nayi transactions hain. Teesra: product band ho jaye to purane customers apni purani terms par rehte hain, is liye ProductDefinition aur customer ka Arrangement alag classes hain.

### Slide 5 (2:20-2:50)

Yeh research ke baad ka class diagram hai. Is mein chaar hierarchies hain: Party, Arrangement, BankTransaction aur Case. Baqi cheezen, jaise cards, mandates, branches aur employees, association se jurri hain, kyunke woh ek doosre se related hain magar ek doosre ki qism nahi. Mera usool yeh tha: inheritance sirf wahan jahan sach mein "is-a" rishta ho.

### Slide 6 (2:50-3:25)

Yeh do multi-level hierarchies UML mein hain. Party se Organization, aur Organization se Company aur Charity. Aur Arrangement se DepositAccount, phir Current, Savings aur Term Deposit. Shared data hamesha us sab se oonche level par hai jahan har subclass ko us ki zaroorat hai. Daayen taraf woh inheritance hai jo main ne soch kar reject ki: card account nahi kyunke us mein paisa nahi hota, sole trader alag legal entity nahi, aur merchant refund reversal nahi kyunke asal purchase valid rehti hai.

### Slide 7 (3:25-3:55)

Yeh flowchart ek poora workflow dikhata hai: digital banking se ek bara transfer, jo brief ka apna case hai. Pehle authority check hoti hai, phir funds aur limit, phir dual control jahan doosre signatory ki approval chahiye, aur phir compliance review. Agar koi rule fail ho to payment mitti nahi, balkay wajah ke saath record mein rehti hai.

### Slide 8 (3:55-4:35)

Ab implementation ki progress. Core model Python mein ban raha hai: parties, accounts, transactions aur double-entry ledger ka kaam ho chuka hai, aur har rule ke saath test likh raha hoon. Is waqt main cards aur lending ke workflows aur brief ke exception scenarios par kaam kar raha hoon. Saath hi Tkinter mein GUI ka prototype ban raha hai, yeh us ki screen hai, jahan staff aur customer dono apne role ke hisaab se kaam kar sakenge. Aur main ek AI assistant bhi jor raha hoon, jo Claude API se bank ke records parh kar sawalon ka jawab deta hai, magar khud koi record nahi badal sakta.

### Slide 9 (4:35-5:00)

Agle steps: implementation aur GUI mukammal karna, brief ke har critical case ko automated tests se check karna, files aur JSON se data save karna, aur SOLID principles ke mutabiq design review karna. Aakhir mein final report aur viva. Shukriya, main sawalat ke liye hazir hoon.

## Likely questions (answers in Roman Urdu)

**Customer, Person ki subclass kyun nahi?** Customer hona ek role hai jo shuru aur khatam hota hai. Ayesha ek hi waqt mein customer, director aur signatory hai. Subclasses se ek insaan ke teen records ban jate, aur role khatam hone par history toot jati.

**Multi-level inheritance kahan hai?** Chaar jagah. Misal ke taur par Party › Organization › Company, aur BankTransaction › Reversal › Chargeback.

**Reversal naya record kyun, payment delete kyun nahi?** Bank history kabhi nahi mitata. Asal payment posted rehti hai aur reversal usay counteract karta hai, is liye books balance rehti hain aur auditor dono dekh sakta hai.

**Purani authority kaise dikhate ho?** Mandate ka ek validity period hai. Revoke karne se period band hota hai, mandate delete nahi hota, aur har payment apna mandate store karti hai.

**Research ke kaun se sources?** FATF, State Bank of Pakistan, Basel Committee, ISO 20022, Visa aur Mastercard dispute rules, IFRS 9, BIAN aur Martin Fowler ki Analysis Patterns.

**AI assistant kyun, aur kya yeh khatarnak nahi?** Assistant sirf records parhta hai aur form bhar kar deta hai; Run insaan dabata hai, is liye bank ke saare rules aur audit log waise hi lagte hain. Internet na ho to offline assistant jawab deta hai.

**Abhi kya baqi hai?** Implementation aur GUI mukammal karna, har critical case ka test, files/JSON persistence, SOLID review, aur final report aur viva.

## Rehearsal checklist

- Time yourself twice with a stopwatch; stop at 5:00.
- Point at the diagram while you describe it, for example the Party › Organization › Company path on slide 6.
- Learn the eight source names on slide 3; they are the strongest sign of research.
