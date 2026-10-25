# Answer-Quality Report — LinkedIn Easy Apply Automaton

*Generated 2026-08-04 05:22 · read-only analysis (nothing was changed).*

Every distinct question the tool has answered was re-read and judged for **logical correctness** against your profile (`answers.yaml`). Legend: 🟢 correct · 🟠 questionable (defensible but unverifiable) · 🔴 incorrect (illogical / contradicts profile) · ⬜ unanswered (blank).

**Ground truth:** Debashish Mishra · ~6y total · notice 45d · current CTC 3,000,000 · expected 3,200,000–4,000,000 · Hyderabad, India.

## 1 · Summary

- **1,754 answers** across all applications · **316 distinct** question/answer pairs.

| Verdict | Answers | Share |
|---|---:|---:|
| 🟢 Correct | 1,137 | 65% |
| 🟠 Questionable | 161 | 9% |
| 🔴 Incorrect | 221 | 13% |
| ⬜ Unanswered | 235 | 13% |

**Headline findings**
- 🔴 **61 wrong/risky answers were actually submitted** to real employers (§2).
- Total-experience questions are sometimes answered **3** instead of your real **~6** years.
- Salary fields fall back to **0** on several postings; one phone fallback is a **dummy number**.
- Skills not on your résumé (Java, Azure, AWS, Spring Boot…) are sometimes answered **6 years** — inflated.
- Most failures are **blank bespoke screening questions** (coverage gaps), not wrong answers.

## 2 · ⚠️ Wrong / risky answers that were actually submitted

These went out on at least one **submitted** application. `#sub` = submitted applications using this answer.

| · | Question | Answer submitted | Should be | Why it's off | #sub |
|---|---|---|---|---|---:|
| 🔴 | Are you comfortable commuting to this job's location? | Hyderabad | Yes | 'Hyderabad' answers a city, but this is a Yes/No location question. | 3 |
| 🔴 | How many years of work experience do you have with Java? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 2 |
| 🔴 | How many years of Engineering experience do you currently have? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 2 |
| 🔴 | How many years of work experience do you have with Microsoft Azure? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Amazon Web Services (AWS)? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with PostgreSQL? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (adjacent to SQL (résumé)) — inflated. | 1 |
| 🔴 | How many years of work experience do you have in Typescript | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (adjacent to JavaScript (résumé)) — inflated. | 1 |
| 🔴 | How many years of experience do you have in Java/Core java? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of experience do you have in Spring boot and Microservice? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Spring Boot? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | In total, How many years of experience do you have ? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 1 |
| 🔴 | How many years of work experience do you have with Cloud Applications? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years' experience do you have as a software engineer? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 1 |
| 🔴 | How many years of Semiconductor Manufacturing experience do you currently have? | 3 | 0 | Claims 3y of 'semiconductor manufacturing', unrelated to the résumé. | 1 |
| 🔴 | How many years of Product Management experience do you currently have? | 3 | 0 | Claims 3y of 'product management', unrelated to the résumé. | 1 |
| 🔴 | How many years of overall experience you have? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 1 |
| 🔴 | How many years of work experience do you have with Bootstrap (Framework)? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (generic web skill) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Tailwind CSS | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (generic web skill) — inflated. | 1 |
| 🔴 | How many years of experience do you have in API ? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Information Technology? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | This is Hybrid role, and available work location is Chennai. Would you be comfortable for the mentioned location? | Hyderabad | Yes | 'Hyderabad' answers a city, but this is a Yes/No location question. | 1 |
| 🔴 | Are you comfortable with the job location as either Pune/Mumbai ? | Hyderabad | Yes | 'Hyderabad' answers a city, but this is a Yes/No location question. | 1 |
| 🔴 | Are you an immediate joiner ? If not, please specify your official notice period and remaining days, if serving. | 45 | Yes/No | '45' answers a number, but this is a Yes/No joining question. | 1 |
| 🔴 | Are you an immediate joiner? (Only mention 'Yes' if you are an immediate joiner or serving your notice period with the last working day before 30th Sep 2026.) | 45 | Yes/No | '45' answers a number, but this is a Yes/No joining question. | 1 |
| 🔴 | What is your current location? | 3000000 | city (Hyderabad) | A location question answered with a salary figure. | 1 |
| 🟠 | How many years of work experience do you have with Databases? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 3 |
| 🟠 | How many years of work experience do you have with PostgreSQL? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to SQL (résumé)) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with Next.js? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to React (résumé)) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with C++? | 2 | verify | Claims 2y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with MySQL? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to SQL (résumé)) — unverifiable. | 2 |
| 🟠 | "Have you completed a BE degree in Computer Science or Equivalent? | Master's Degree | Yes | Master's implies 'Yes', but the field wanted a Yes/No. | 1 |
| 🟠 | How many years of work experience do you have with Amazon Web Services (AWS)? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with REST APIs? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Angular? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with C (Programming Language)? | 2 | verify | Claims 2y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with TypeScript? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to JavaScript (résumé)) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with PHP? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Linux? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | Do you have professional experience working with C++? | Yes | verify | Claims a skill not in the résumé. | 1 |
| 🟠 | How many years of work experience do you have with Django REST Framework? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Java? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Core Java? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Docker/Kubernetes ? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with PostgreSQL/MongoDB ? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to SQL (résumé)) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Azure/AWS/GCP ? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with NoSQL? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Laravel? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with OpenCL? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Software as a Service (SaaS)? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of Technology, Information and Internet experience do you currently have? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Database Management System (DBMS)? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with HTML5? | 3 | verify | Claims 3y of a skill not in the résumé (generic web skill) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Cascading Style Sheets (CSS)? | 3 | verify | Claims 3y of a skill not in the résumé (generic web skill) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Bedrock? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with FastAPI? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to Python (résumé)) — unverifiable. | 1 |
| 🟠 | How many years of backend experience do you have? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of frontend experience do you have? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Generative AI frameworks like Lang Chain, Lang Graph, Crew AI ? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of experience do you have in Backend Engineering? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | We must fill this position urgently. Can you start immediately? | 1 month | No (45-day notice) | '1 month' for an immediate-availability question. | 1 |
| 🟠 | Do you have experience with OpenCL or GPU/parallel computing technologies? | Yes | verify | Claims GPU/parallel-computing experience not in the résumé. | 1 |

## 3 · Top problem patterns

| Pattern | Answers affected |
|---|---:|
| Bespoke screening question left blank | 151 |
| Years claimed for a skill not in résumé | 142 |
| Identity field left blank (email / country code) | 70 |
| Salary answered as 0 | 40 |
| Inflated years for a skill not in résumé (=6) | 40 |
| Dummy placeholder phone number | 33 |
| Answer type mismatch (Yes/No ↔ number ↔ city) | 32 |
| Understated total experience (said 3, résumé ~6) | 26 |
| Notice period 30 vs configured 45 | 25 |
| Experience claimed in an unrelated domain | 16 |
| Question mis-classified (wrong field filled) | 13 |
| Blank for a skill the résumé lists | 6 |
| Right info, wrong field format | 6 |
| Blank (skill not in résumé) | 4 |

## 4 · Every question, graded (by category, worst first)

### unknown — 167 answers (🟢15 · 🟠1 · ⬜151)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟠 | Do you have experience with OpenCL or GPU/parallel computing technologies? | Yes | verify | Claims GPU/parallel-computing experience not in the résumé. | 1 |
| ⬜ | This is a hybrid opportunity and the shift timings are 5 PM-2 AM (Cabs provided). Are you comfortable with this? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 12 |
| ⬜ | Are you available to join immediately or within 30 days? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 12 |
| ⬜ | This position does not include Provident Fund (PF) & Insurance benefits. Are you comfortable proceeding with this arrangement? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 12 |
| ⬜ | AI/ML | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 8 |
| ⬜ | Have you built and deployed a production application using Microsoft Azure? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 6 |
| ⬜ | Have you built a production application using Azure OpenAI or another LLM? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 6 |
| ⬜ | Do you have practical experience with RAG, tool calling, structured outputs, or AI agents? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 6 |
| ⬜ | Have you worked with MCP servers or MCP clients? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 6 |
| ⬜ | Have you built product experiences involving execution visibility, instrumentation, logs, traces, timelines, failures, debugging, approvals, or operational controls? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 6 |
| ⬜ | Have you built complex workflow products, developer tools, observability products, operator platforms, internal engineering platforms, or state rich enterprise applications? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 6 |
| ⬜ | What is your preferred working location? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 4 |
| ⬜ | Are you fine to give on call support on rotational basis for a week in a month and you will get allowances for that. Apply only if fine. | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 4 |
| ⬜ | Are you available to Face-to-Face interview on Aug 8th 2026 (Saturday) ? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 4 |
| ⬜ | If offered the role, within how many days will you be able to join? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 4 |
| ⬜ | Will you be able to work from Pune office in hybrid working model? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 4 |
| ⬜ | Insurance domain background experience | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 4 |
| ⬜ | Are you comfortable to work Hybrid | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 4 |
| ⬜ | Which location are you applying for? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 3 |
| ⬜ | Backend engineering ? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Led a team or project ? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you worked in Backend Development at a startup, scale-up, or in the high-tech industry? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | LLMs have you worked with LLM's? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you built any RAG-based applications? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you built REST APIs or backend services that integrate AI models? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | How would you rate yourself on a scale of 1 to 10 in Data Structures and Algorithms? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you worked in SDET or QA Roles at a startup, scale-up, or in the high-tech industry? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you worked in FinTech, Consumer Tech or have worked in Product Companies? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | This role is for Full Stack Integration specialist so have you developed enterprise system integrations between multiple applications? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you implemented event-driven integrations? Type 1 if you have used Azure Service Bus, Type 2 for Event Grid, Type 3 for Kafka, Type 4 for RabbitMQ)? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | This is an immediate requirement. Can you join within 20 days? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | What is your level of proficiency in English? |   | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Do you have experience building scalable, component-based applications and working with state management libraries (Redux, Context API, Zustand, etc.)? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you worked with any AI/GenAI technologies? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you applied to the following companies within one year for any role ? (Type-1 for Accenture/ Type 2 for Mphasis/ Type-3 for Both/ Type 4 for None | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | This role is for an 9+ yrs, but Sahaj operates without traditional management layers. You will be expected to be 100% hands-on with writing production code. Does this align with your current goals? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you ever led the technical design and initial setup of a software project completely from scratch (a greenfield project)? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Have you ever been responsible for selecting a project's technology stack based on business trade-offs rather than just using what was already there? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 2 |
| ⬜ | Are you comfortable for Pune location with 2 days Hybrid Mode? | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 1 |
| ⬜ | Please specify your preferred location/s | (blank) | needs an answer | Bespoke screening question left blank — this is why such applications abort. | 1 |
| 🟢 | This is a hybrid opportunity and the shift timings are 5 PM-2 AM (Cabs provided). Are you comfortable with this? | Yes | Yes | Reasonable 'Yes' to a fit/comfort question. | 5 |
| 🟢 | Which location are you applying for? | Bengaluru | Bengaluru | Matches the configured location preference. | 4 |
| 🟢 | What is your level of proficiency in English? | Professional | Professional/Native | Reasonable English proficiency. | 3 |
| 🟢 | Are you comfortable for Pune location with 2 days Hybrid Mode? | yes | Yes | Reasonable 'Yes' to a fit/comfort question. | 1 |
| 🟢 | Website | zanark.github.io | zanark.github.io | Portfolio/website link provided. | 1 |
| 🟢 | Have you worked on multi-threaded or performance-critical software application | Yes | Yes | Reasonable 'Yes' to a fit/comfort question. | 1 |

### location_city — 11 answers (🟢4 · 🔴7)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🔴 | Are you comfortable commuting to this job's location? | Hyderabad | Yes | 'Hyderabad' answers a city, but this is a Yes/No location question. | 3 |
| 🔴 | Are you okay for Hyderabad location? | Hyderabad | Yes | 'Hyderabad' answers a city, but this is a Yes/No location question. | 2 |
| 🔴 | This is Hybrid role, and available work location is Chennai. Would you be comfortable for the mentioned location? | Hyderabad | Yes | 'Hyderabad' answers a city, but this is a Yes/No location question. | 1 |
| 🔴 | Are you comfortable with the job location as either Pune/Mumbai ? | Hyderabad | Yes | 'Hyderabad' answers a city, but this is a Yes/No location question. | 1 |
| 🟢 | Location (city) | Hyderabad | hyderabad | Matches the profile city. | 2 |
| 🟢 | Are you okay for Hyderabad location? | Yes | Yes | Comfortable with the location — 'Yes'. | 2 |

### experience_total — 124 answers (🟢9 · 🟠60 · 🔴51 · ⬜4)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🔴 | In total, How many years of experience do you have ? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 7 |
| 🔴 | Kindly mention your total IT experience in years. | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 6 |
| 🔴 | How many years of work experience do you have with Cloud Applications? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 5 |
| 🔴 | How Many Years of work experience do you have in your chosen engineering field | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 4 |
| 🔴 | What is your total experience? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 4 |
| 🔴 | How many years of experience do you have creating and reviewing engineering drawings in manufacturing environments? | 6 | 0 | Claims 6y in a domain unrelated to the résumé. | 4 |
| 🔴 | How many years of work experience do you have with Informatica? | 6 | 0 | Claims 6y of 'informatica', unrelated to the résumé. | 4 |
| 🔴 | How many years of work experience do you have with Teradata? | 6 | 0 | Claims 6y of 'teradata', unrelated to the résumé. | 4 |
| 🔴 | How many years of work experience do you have with Capital Markets? | 3 | 0 | Claims 3y of 'capital markets', unrelated to the résumé. | 2 |
| 🔴 | How many years of Engineering experience do you currently have? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 2 |
| 🔴 | How many years of Information Technology experience do you currently have? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 1 |
| 🔴 | How many years' experience do you have as a software engineer? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 1 |
| 🔴 | How many years of Semiconductor Manufacturing experience do you currently have? | 3 | 0 | Claims 3y of 'semiconductor manufacturing', unrelated to the résumé. | 1 |
| 🔴 | How many years of Product Management experience do you currently have? | 3 | 0 | Claims 3y of 'product management', unrelated to the résumé. | 1 |
| 🔴 | How many years of overall experience you have? | 3 | 6 | Answered 3, but the résumé shows ~6 years total — understated. | 1 |
| 🔴 | How many years of work experience do you have with Bootstrap (Framework)? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (generic web skill) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Tailwind CSS | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (generic web skill) — inflated. | 1 |
| 🔴 | How many years of experience do you have in API ? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Information Technology? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🟠 | How many years of work experience do you have with Databases? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 12 |
| 🟠 | How many years of work experience do you have with Generative AI? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 9 |
| 🟠 | How many years of work experience do you have with NoSQL? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 9 |
| 🟠 | How many years of work experience do you have with Back-End Web Development? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with IPython? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with Data Engineering? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with OpenAI API? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with Claude Code? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with AI? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with Laravel? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of experience do you have in developing or integrating Agentic AI/Generative AI solutions into applications? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with Relational Databases? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Generative AI Tools? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with OpenCL? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Software as a Service (SaaS)? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of Technology, Information and Internet experience do you currently have? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Database Management System (DBMS)? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with HTML5? | 3 | verify | Claims 3y of a skill not in the résumé (generic web skill) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Cascading Style Sheets (CSS)? | 3 | verify | Claims 3y of a skill not in the résumé (generic web skill) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Bedrock? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with FastAPI? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to Python (résumé)) — unverifiable. | 1 |
| 🟠 | How many years of backend experience do you have? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of frontend experience do you have? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Generative AI frameworks like Lang Chain, Lang Graph, Crew AI ? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of experience do you have in Backend Engineering? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| ⬜ | You have more than 5 years of professional experience post-education? | (blank) | — | Left blank (skill not in résumé). | 2 |
| ⬜ | You have more than 3 years of professional experience post-education? | (blank) | — | Left blank (skill not in résumé). | 2 |
| 🟢 | Total IT Experience? | 6 | 6 | Matches the résumé total (6y). | 4 |
| 🟢 | How many years of software engineer experience do you currently have? | 6 | 6 | Matches the résumé total (6y). | 2 |
| 🟢 | Do you have 8-10 years of hands-on software development experience? | No | No | Résumé ~6y vs threshold 8 — 'No'. | 1 |
| 🟢 | How many years of work experience do you have with WCF Services? | 6 | 2 | 6y is plausible for C# / .NET (résumé ~2y, within total). | 1 |
| 🟢 | How many years of total experience do you have? | 6 | 6 | Matches the résumé total (6y). | 1 |

### notice_period — 97 answers (🟢50 · 🟠4 · 🔴43)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🔴 | Are you an immediate joiner ? If not, please specify your official notice period and remaining days, if serving. | 45 | Yes/No | '45' answers a number, but this is a Yes/No joining question. | 7 |
| 🔴 | Kindly mention your official notice period. if serving, please mention number of days remaining and if you are immediate joiner please mention "0". | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 6 |
| 🔴 | What is your notice period? | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 5 |
| 🔴 | What is your current notice period? | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 4 |
| 🔴 | What is your ECTC? | 45 | expected salary | This is an expected-salary (ECTC) question answered with notice days. | 4 |
| 🔴 | Are you an immediate joiner ? If not, please specify your official notice period and remaining days, if serving. | 30 days | Yes/No | '30 days' answers a number, but this is a Yes/No joining question. | 2 |
| 🔴 | What is your official notice period (days)? | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 2 |
| 🔴 | What is your official notice period? | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 2 |
| 🔴 | What is your Notice period (If serving how many days left?) | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 2 |
| 🔴 | Notice Period? | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 2 |
| 🔴 | What is your notice period in days? | 30 days | 45 | Answered 30, but the profile notice is 45 days. | 2 |
| 🔴 | Apply only if serving notice period and can join by August? | 45 | Yes/No | '45' answers a number, but this is a Yes/No joining question. | 2 |
| 🔴 | Currently are you serving Notice Period (Immediately to 15 days)? | 45 | Yes/No | '45' answers a number, but this is a Yes/No joining question. | 2 |
| 🔴 | Are you an immediate joiner? (Only mention 'Yes' if you are an immediate joiner or serving your notice period with the last working day before 30th Sep 2026.) | 45 | Yes/No | '45' answers a number, but this is a Yes/No joining question. | 1 |
| 🟠 | Apply only if serving notice period and can join by August? | Yes | context-specific | Yes/No joining gate — depends on the exact wording. | 2 |
| 🟠 | Currently are you serving Notice Period (Immediately to 15 days)? | Yes | context-specific | Yes/No joining gate — depends on the exact wording. | 2 |
| 🟢 | What is your Notice Period (In days)? | 45 | 45 | Matches the configured 45-day notice. | 12 |
| 🟢 | If selected, how soon can you fill this position (days)? | 45 | 45 | Matches the configured 45-day notice. | 8 |
| 🟢 | What is your notice period? | 45 | 45 | Matches the configured 45-day notice. | 7 |
| 🟢 | What is your Notice period? | 45 | 45 | Matches the configured 45-day notice. | 6 |
| 🟢 | What is your Notice Period ? | 45 | 45 | Matches the configured 45-day notice. | 4 |
| 🟢 | What is your notice period (in days)? | 45 | 45 | Matches the configured 45-day notice. | 3 |
| 🟢 | What is your notice period in days? | 45 | 45 | Matches the configured 45-day notice. | 2 |
| 🟢 | What is your notice period? | 45 days | 45 | Matches the configured 45-day notice. | 2 |
| 🟢 | What is your notice period? (In Days) | 45 | 45 | Matches the configured 45-day notice. | 1 |
| 🟢 | What is your Notice Period? | 45 | 45 | Matches the configured 45-day notice. | 1 |
| 🟢 | What is your official notice period ? | 45 | 45 | Matches the configured 45-day notice. | 1 |
| 🟢 | What is your notice period in number of days | 45 | 45 | Matches the configured 45-day notice. | 1 |
| 🟢 | What is the notice period for your current company (in days)? | 45 | 45 | Matches the configured 45-day notice. | 1 |
| 🟢 | What is your Notice period in Days ? | 45 | 45 | Matches the configured 45-day notice. | 1 |

### salary_current — 95 answers (🟢62 · 🔴33)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🔴 | What is your current location? | 3000000 | city (Hyderabad) | A location question answered with a salary figure. | 7 |
| 🔴 | Kindly mention your current CTC in LPA, Example if your CTC is 7LPA, Mention as 700000 | 0 | 3000000 (annual) | Answered 0 — no salary submitted. | 6 |
| 🔴 | What is your current CTC? | 0 | 3000000 (annual) | Answered 0 — no salary submitted. | 6 |
| 🔴 | Please provide your current salary in XX lakhs. For instance, if you earn 35 lakhs, enter 35. If it's 24.5 lakhs, round to the nearest whole number, which is 25. | 0 | 3000000 (annual) | Answered 0 — no salary submitted. | 4 |
| 🔴 | What is your current/last CTC ? | 0 | 3000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | What is your current ctc ? | 0 | 3000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | What is your Current Annual Salary? | 0 | 3000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | Your Current CTC? | 0 | 3000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | What is your current net salary in INR? (Monthly) | 0 | 250000 (monthly) | Answered 0 — no salary submitted. | 2 |
| 🟢 | What is your current CTC? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 21 |
| 🟢 | What is your current monthly take-home salary (after deductions such as tax, insurance, etc.)? | 250000 | 250000 (monthly) | Matches the profile current CTC. | 12 |
| 🟢 | What is your Current Annual Salary? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 7 |
| 🟢 | What is your current/last CTC ? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 7 |
| 🟢 | What is your current net salary in INR? (Monthly) | 250000 | 250000 (monthly) | Matches the profile current CTC. | 2 |
| 🟢 | What is your current CTC (Fixed + Variable) in LPA? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 2 |
| 🟢 | What is your current CTC in Lacs per annum? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 2 |
| 🟢 | Present CTC (Annual Salary) | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | whats your current compensation | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | What is your Current Fixed CTC? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | What is your current ctc ? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | What is your current CTC (in lakhs per annum) | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | What is your Current CTC? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | Mention your Current CTC ? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | What is your Current/Last drawn CTC(in LPA)? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |
| 🟢 | What is the current CTC You are getting in Lakhs (INR) ? | 3000000 | 3000000 (annual) | Matches the profile current CTC. | 1 |

### salary_expected — 61 answers (🟢43 · 🔴16 · ⬜2)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🔴 | What is your desired Compensation ( in LPA) | 0 | 3200000-4000000 (annual) | Answered 0 — no salary submitted. | 4 |
| 🔴 | What is your np ? | 0 | notice days | A notice-period question mis-bucketed as salary. | 2 |
| 🔴 | What is your Expected Annual Salary ? | 0 | 3200000-4000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | What is Your Expected CTC? | 0 | 3200000-4000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | What is your CTC in Lakhs? | 0 | 3200000-4000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | Your Expected CTC? | 0 | 3200000-4000000 (annual) | Answered 0 — no salary submitted. | 2 |
| 🔴 | What is your expected Net Salary in INR? (Monthly) | 0 | 300000-340000 (monthly) | Answered 0 — no salary submitted. | 2 |
| ⬜ | What is your expected CTC ? | (blank) | 3200000-4000000 (annual) | Left blank. | 2 |
| 🟢 | What is your current monthly expected salary? | 300000 | 300000-340000 (monthly) | Within the expected-CTC tier range. | 12 |
| 🟢 | What is your Expected Annual Salary ? | 3500000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 7 |
| 🟢 | What is your CTC? | 4000000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 4 |
| 🟢 | What is your expected CTC salary in Lakh Per Annum (that will have PF and TDS deductions)? | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 4 |
| 🟢 | What is your expected Net Salary in INR? (Monthly) | 340000 | 300000-340000 (monthly) | Within the expected-CTC tier range. | 2 |
| 🟢 | What is your expected CTC in Lacs per annum? | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 2 |
| 🟢 | What is your expected CTC? | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 2 |
| 🟢 | What's your expected monthly basic salary? INR | 300000 | 300000-340000 (monthly) | Within the expected-CTC tier range. | 1 |
| 🟢 | Expected CTC (Annual Salary) | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | whats your expected compensation? | 4000000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | What is your Expected Fixed CTC? | 4000000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | What is your expected ctc ? | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | What is your expected CTC (in lakhs per annum) | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | What is your Expected CTC? | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | Mention your Expected CTC ? | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | What is your expected CTC(in LPA)? | 4000000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |
| 🟢 | What is your expected CTC in Lakhs (INR) ? | 3200000 | 3200000-4000000 (annual) | Within the expected-CTC tier range. | 1 |

### education — 8 answers (🟠6 · ⬜2)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟠 | "Have you completed a BE degree in Computer Science or Equivalent? | Master's Degree | Yes | Master's implies 'Yes', but the field wanted a Yes/No. | 6 |
| ⬜ | "Have you completed a BE degree in Computer Science or Equivalent? | (blank) | Yes / Master's | Left blank. | 2 |

### phone_country_code — 215 answers (🟢178 · ⬜37)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| ⬜ | Phone country code | (blank) | india (+91) | Left blank for country code. | 33 |
| ⬜ | Phone country code |   | india (+91) | Left blank for country code. | 4 |
| 🟢 | Phone country code | India (+91) | India (+91) | Country code +91. | 177 |
| 🟢 | Phone country code | 91 | India (+91) | Country code +91. | 1 |

### email — 215 answers (🟢182 · ⬜33)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| ⬜ | Email address | (blank) | debashishemails@gmail.com | Left blank for email. | 31 |
| ⬜ | Email | (blank) | debashishemails@gmail.com | Left blank for email. | 2 |
| 🟢 | Email address | debashishemails@gmail.com | debashishemails@gmail.com | Matches the profile email. | 169 |
| 🟢 | Email | debashishemails@gmail.com | debashishemails@gmail.com | Matches the profile email. | 13 |

### phone — 215 answers (🟢182 · 🔴33)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🔴 | Mobile phone number | +91-0000000000 | +91 9873824499 | Dummy placeholder phone number. | 31 |
| 🔴 | Phone | +91-0000000000 | +91 9873824499 | Dummy placeholder phone number. | 2 |
| 🟢 | Mobile phone number | +91 9873824499 | +91 9873824499 | Matches the profile phone. | 169 |
| 🟢 | Phone | +91 9873824499 | +91 9873824499 | Matches the profile phone. | 13 |

### experience_skill — 438 answers (🟢313 · 🟠81 · 🔴38 · ⬜6)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🔴 | How much Relevant Experience you have in Java? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 10 |
| 🔴 | How many years of work experience do you have with Java? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 6 |
| 🔴 | How many years of work experience do you have with Microsoft Azure? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 5 |
| 🔴 | How many years of experience in Microservices? | Yes | a number of years | 'Yes' answers a Yes/No, but this asks for a number of years. | 2 |
| 🔴 | How many years of experience in CI/CD? | Yes | a number of years | 'Yes' answers a Yes/No, but this asks for a number of years. | 2 |
| 🔴 | Do you have Minimum 5+ years of experience in Azure & Databricks? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 2 |
| 🔴 | Do you have Minimum 5+ years of experience in Azure & Databricks? | Yes | a number of years | 'Yes' answers a Yes/No, but this asks for a number of years. | 2 |
| 🔴 | How many years of hands-on experience do you have with React.js in a production environment? | Yes | a number of years | 'Yes' answers a Yes/No, but this asks for a number of years. | 1 |
| 🔴 | How many years of work experience do you have with Angular? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with kafka-tools? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Amazon Web Services (AWS)? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with PostgreSQL? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (adjacent to SQL (résumé)) — inflated. | 1 |
| 🔴 | How many years of work experience do you have in Typescript | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (adjacent to JavaScript (résumé)) — inflated. | 1 |
| 🔴 | How many years of experience do you have in Java/Core java? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of experience do you have in Spring boot and Microservice? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🔴 | How many years of work experience do you have with Spring Boot? | 6 | <= 3 or blank | Claims 6y of a skill not in the résumé (not in résumé) — inflated. | 1 |
| 🟠 | How many years of work experience do you have with PostgreSQL? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to SQL (résumé)) — unverifiable. | 11 |
| 🟠 | How many years of experience do you have with Azure Storage and Azure Functions? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 7 |
| 🟠 | How many work experience do you have with Java and Microservices ? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 6 |
| 🟠 | How many years of work experience do you have with Next.js? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to React (résumé)) — unverifiable. | 6 |
| 🟠 | How many years of work experience do you have with Amazon Web Services (AWS)? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 4 |
| 🟠 | How many years of work experience do you have with REST APIs? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 4 |
| 🟠 | How many years of work experience do you have with Angular? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 4 |
| 🟠 | How many years of work experience do you have with C++? | 2 | verify | Claims 2y of a skill not in the résumé (not in résumé) — unverifiable. | 4 |
| 🟠 | How many years of work experience do you have with MySQL? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to SQL (résumé)) — unverifiable. | 3 |
| 🟠 | How many years of work experience do you have with C (Programming Language)? | 2 | verify | Claims 2y of a skill not in the résumé (not in résumé) — unverifiable. | 3 |
| 🟠 | How many years of work experience do you have with Microsoft Azure? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 3 |
| 🟠 | How many years of work experience do you have with TypeScript? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to JavaScript (résumé)) — unverifiable. | 3 |
| 🟠 | How many years of work experience do you have with Azure Functions? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with Docker? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with Kubernetes? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with PHP? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of experience in Microservices? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of experience in CI/CD? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How much Relevant Experience you have in Java? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 2 |
| 🟠 | How many years of work experience do you have with GraphQL? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Linux? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | Do you have professional experience working with C++? | Yes | verify | Claims a skill not in the résumé. | 1 |
| 🟠 | How many years of work experience do you have with Django REST Framework? | 3 | verify | Claims 3y of a skill not in the résumé (generic for a full-stack dev) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Java? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Core Java? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Docker/Kubernetes ? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with PostgreSQL/MongoDB ? | 3 | verify | Claims 3y of a skill not in the résumé (adjacent to SQL (résumé)) — unverifiable. | 1 |
| 🟠 | How many years of work experience do you have with Azure/AWS/GCP ? | 3 | verify | Claims 3y of a skill not in the résumé (not in résumé) — unverifiable. | 1 |
| ⬜ | How many years of experience do you have with React.js? | (blank) | 2 | Blank, but the résumé lists React (~2y). | 4 |
| ⬜ | Do you have experience in sql ? | (blank) | 3 | Blank, but the résumé lists SQL (~3y). | 2 |
| 🟢 | How many years of work experience do you have with React.js? | 2 | 2 | Matches the résumé for React (~2y). | 50 |
| 🟢 | How many years of work experience do you have with .NET Core? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 35 |
| 🟢 | How many years of work experience do you have with Python (Programming Language)? | 4 | 4 | Matches the résumé for Python (~4y). | 30 |
| 🟢 | How many years of work experience do you have with Node.js? | 2 | 2 | Matches the résumé for Node.js (~2y). | 19 |
| 🟢 | How many years of work experience do you have with ASP.NET? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 17 |
| 🟢 | How many years of work experience do you have with .Net and C#? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 17 |
| 🟢 | How many years of experience do you have as Full Stack Developer (In Years)? | 3 | 3 | Matches the résumé for Full Stack (~3y). | 12 |
| 🟢 | How much Relevant Experience you have in Reactjs? | 2 | 2 | Matches the résumé for React (~2y). | 12 |
| 🟢 | How many years of work experience do you have with .NET Framework? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 11 |
| 🟢 | How many years of work experience do you have with C#? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 9 |
| 🟢 | How many years of experience do you have with Dot Net? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 7 |
| 🟢 | How many years of experience do you have with ASP.NET Core MVC? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 7 |
| 🟢 | How many work experience do you have with React.js/ Angular and JavaScript? | 3 | 3 | Matches the résumé for JavaScript (~3y). | 6 |
| 🟢 | How many years of work experience do you have with SQL? | 3 | 3 | Matches the résumé for SQL (~3y). | 6 |
| 🟢 | How many years of professional full-stack development experience do you have? | 3 | 3 | Matches the résumé for Full Stack (~3y). | 6 |
| 🟢 | How many years of hands on full stack or product engineering experience do you have building production software? | 3 | 3 | Matches the résumé for Full Stack (~3y). | 6 |
| 🟢 | How many years of experience do you have building production applications using React, Next.js, TypeScript, or comparable modern frontend technologies? | 6 | 2 | 6y is plausible for React (résumé ~2y, within total). | 6 |
| 🟢 | How many years of experience do you have with React, Next.js, and TypeScript? | 6 | 2 | 6y is plausible for React (résumé ~2y, within total). | 4 |
| 🟢 | Relevant Experience in React ? | 2 | 2 | Matches the résumé for React (~2y). | 4 |
| 🟢 | Relevant Experience in Python? | 4 | 4 | Matches the résumé for Python (~4y). | 4 |
| 🟢 | How many years of work experience do you have with .NET in Azure? | 3 | 2 | 3y is plausible for C# / .NET (résumé ~2y, within total). | 3 |
| 🟢 | How many years of work experience do you have with JavaScript? | 3 | 3 | Matches the résumé for JavaScript (~3y). | 3 |
| 🟢 | How many years of work experience do you have with React Native? | 2 | 2 | Matches the résumé for React (~2y). | 3 |
| 🟢 | How many years of experience do you have with React.js? | 2 | 2 | Matches the résumé for React (~2y). | 3 |
| 🟢 | Do you have production experience building backend services and APIs using Python, Node.js, Go, or similar technologies? | 2 | 4 | 2y is plausible for Python (résumé ~4y, within total). | 3 |
| 🟢 | Do you have production experience building backend services and APIs using Python, Node.js, Go, or similar technologies? | Yes | Yes | Résumé lists Python — 'Yes' is right. | 3 |
| 🟢 | How many years of work experience do you have with React? | 2 | 2 | Matches the résumé for React (~2y). | 2 |
| 🟢 | How many years of work experience do you have with Microsoft SQL Server? | 3 | 3 | Matches the résumé for SQL (~3y). | 2 |
| 🟢 | How many years of experience do you have with React, Next.js, and TypeScript? | 3 | 2 | 3y is plausible for React (résumé ~2y, within total). | 2 |
| 🟢 | How many years of experience do you have in React/Angular? | 3 | 2 | 3y is plausible for React (résumé ~2y, within total). | 2 |
| 🟢 | How many years of experience do you have with .NET Framework? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 2 |
| 🟢 | How many years of hands-on experience do you have with TypeScript, React, Node.js, and JavaScript? | 6 | 3 | 6y is plausible for JavaScript (résumé ~3y, within total). | 2 |
| 🟢 | How many years of hands-on experience do you have with TypeScript, React, Node.js, and JavaScript? | 3 | 3 | Matches the résumé for JavaScript (~3y). | 2 |
| 🟢 | How many years of work experience do you have with Power BI? | 2 | 2 | Matches the résumé for Power BI (~2y). | 1 |
| 🟢 | How many years of work experience do you have with ASP.NET Web API? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 1 |
| 🟢 | Do you have experience with C# or Angular/Web technologies? | Yes | Yes | Résumé lists C# / .NET — 'Yes' is right. | 1 |
| 🟢 | How many years of work experience do you have with Full-Stack Development? | 3 | 3 | Matches the résumé for Full Stack (~3y). | 1 |
| 🟢 | Do you have 3–6 years of professional experience developing frontend applications using React and TypeScript? | 3 | 2 | 3y is plausible for React (résumé ~2y, within total). | 1 |
| 🟢 | How many years of hands-on experience do you have with React.js in a production environment? | 2 | 2 | Matches the résumé for React (~2y). | 1 |
| 🟢 | Do you have 3–6 years of professional experience developing frontend applications using React and TypeScript? | Yes | Yes | Résumé lists React — 'Yes' is right. | 1 |
| 🟢 | How many years of work experience do you have with React.js/Angular ? | 2 | 2 | Matches the résumé for React (~2y). | 1 |
| 🟢 | How many years of work experience do you have with Python? | 4 | 4 | Matches the résumé for Python (~4y). | 1 |
| 🟢 | How many years of experience do you have in .net? | 2 | 2 | Matches the résumé for C# / .NET (~2y). | 1 |
| 🟢 | Do you have experience in React / angular, if yes, What is your relevant years of experience? | 6 | 2 | 6y is plausible for React (résumé ~2y, within total). | 1 |
| 🟢 | How many years of experience do you have in React ? | 2 | 2 | Matches the résumé for React (~2y). | 1 |
| 🟢 | How many years of work experience do you have with JavaScript Frameworks? | 3 | 3 | Matches the résumé for JavaScript (~3y). | 1 |

### onsite — 28 answers (🟢28)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | Are you Comfortable working from Gurgaon in a work-from-office setup? | Yes | Yes | 'Yes' matches the profile (onsite). | 12 |
| 🟢 | Are you comfortable working in an onsite setting? | Yes | Yes | 'Yes' matches the profile (onsite). | 5 |
| 🟢 | Are you currently located in India or willing to move there to work full-time remotely for this opportunity? | Yes | Yes | 'Yes' matches the profile (onsite). | 4 |
| 🟢 | Are you comfortable working 5days from office. This role is for Bangalore (Bellandur). | Yes | Yes | 'Yes' matches the profile (onsite). | 2 |
| 🟢 | Are you willing to work from Gurgaon location? | Yes | Yes | 'Yes' matches the profile (onsite). | 2 |
| 🟢 | Are you comfortable with an on-site setting? (Andheri East) | Yes | Yes | 'Yes' matches the profile (onsite). | 1 |
| 🟢 | Willing to work onsite in given location | Yes | Yes | 'Yes' matches the profile (onsite). | 1 |
| 🟢 | This is an in-office, 5 days working from office, are you okay with this set up? | Yes | Yes | 'Yes' matches the profile (onsite). | 1 |

### github — 2 answers (🟠2)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟠 | How many years of work experience do you have with GitHub? | (blank) | — | Blank — no GitHub in the profile (add one). | 2 |

### first_name — 18 answers (🟢18)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | First name | Debashish | Debashish | Matches the profile first name. | 18 |

### last_name — 18 answers (🟢18)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | Last name | Mishra | Mishra | Matches the profile last name. | 18 |

### relocation — 19 answers (🟢19)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | Are you willing to relocate to Kochi? | Yes | Yes | 'Yes' matches the profile (relocation). | 7 |
| 🟢 | Are you willing to relocate to Coimbatore? | Yes | Yes | 'Yes' matches the profile (relocation). | 5 |
| 🟢 | Are you willing to relocate to Bangalore HSR Layout , sector 2 ? | Yes | Yes | 'Yes' matches the profile (relocation). | 2 |
| 🟢 | Are you willing to apply for these companies? (Type-1 for Accenture/ Type 2 for Mphasis/ Type-3 for Both/ Type 4 for None ) | Yes | Yes | 'Yes' matches the profile (relocation). | 2 |
| 🟢 | Are you willing to initially work from India and relocate to the UK (Wilmslow) when required? | Yes | Yes | 'Yes' matches the profile (relocation). | 1 |
| 🟢 | Are you willing to relocate to London after the probation period? | Yes | Yes | 'Yes' matches the profile (relocation). | 1 |
| 🟢 | Are you open for relocation? | Yes | Yes | 'Yes' matches the profile (relocation). | 1 |

### linkedin — 2 answers (🟢2)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | Please provide a link to your LinkedIn Profile | https://www.linkedin.com/in/debashishprofile | https://www.linkedin.com/in/debashishprofile | Matches the profile LinkedIn URL. | 1 |
| 🟢 | LinkedIn Profile | https://www.linkedin.com/in/debashishprofile | https://www.linkedin.com/in/debashishprofile | Matches the profile LinkedIn URL. | 1 |

### remote — 12 answers (🟢12)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | Are you comfortable working across front-end, backend, database, and cloud deployment? | Yes | Yes | 'Yes' matches the profile (remote). | 6 |
| 🟢 | Do you have remote setup? As we have BYOD policy. | Yes | Yes | 'Yes' matches the profile (remote). | 6 |

### start_date — 7 answers (🟠7)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟠 | Are you available immediately to start? | 1 month | No (45-day notice) | '1 month' for an immediate-availability question. | 3 |
| 🟠 | Are you available immediately to start? | Yes | No (45-day notice) | Says available immediately, but the profile has a 45-day notice. | 3 |
| 🟠 | We must fill this position urgently. Can you start immediately? | 1 month | No (45-day notice) | '1 month' for an immediate-availability question. | 1 |

### work_authorization — 1 answers (🟢1)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | Are you currently authorized/eligible to work in the location listed for this position? | Yes | Yes | 'Yes' matches the profile (work_authorization). | 1 |

### visa_sponsorship — 1 answers (🟢1)

| V | Question | Answer given | Should be | Why | # |
|---|---|---|---|---|---:|
| 🟢 | Do you now or in the future require visa sponsorship to continue working in this location? | No | No | Answered No; profile expects 'No'. | 1 |

## 5 · Method & caveats

- Grounded in `answers.yaml`. “Not in résumé” = not listed there; may still be fair — marked 🟠, not 🔴.
- 🔴 = number↔Yes/No mismatch, 0 salary, blank required field, contradicts profile, or unrelated-domain claim.
- **Read-only**: no code, answers, DB rows, or dashboard were modified.
- Contains personal data — keep local, do not commit.
