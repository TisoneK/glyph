# Rosetta prior-art research — UI↔API correlation / DOM-payload alignment / semantic dictionary derivation

**Task ID:** 4 (parallel research, Session 3)
**Date:** 2026-07-30
**Question:** Is there prior art for UI↔API correlation / DOM-payload alignment / automatic semantic dictionary derivation? Validate or refute the novelty of Glyph's Rosetta concept (RESEARCH.md §5).

**Method:** web-search across academic (RESTler, RestTestGen, EvoMaster, Schemathesis, Carving-UI-Tests, taint tracking, program synthesis, Fellegi-Sunter, schema matching) + industry (Burp, Postman, Akto, Levo, Noname/Salt/Wallarm, SwaggerHub/Stoplight/Hoppscotch, mitmproxy, Playwright Trace Viewer, WebdriverIO, Label Studio, Prodigy) + targeted page reads (Playwright trace-viewer docs, Levo blog, Akto docs, Carving-UI-Tests arXiv abstract). Raw search/page JSON saved under `/home/z/my-project/tool-results/task4/`.

---

## 1. Academic prior art — API discovery / inference from specs

- **RESTler** (Microsoft Research, ICSE 2019, ~397 citations) — first stateful REST API fuzzer; consumes an OpenAPI spec, synthesizes request sequences, finds producer/consumer dependencies between endpoints. Open source (MIT). **Gap:** requires a pre-existing spec; does not correlate with DOM; no semantic decoding. URLs: https://www.microsoft.com/en-us/research/publication/restler-stateful-rest-api-fuzzing, https://github.com/microsoft/restler-fuzzer
- **RestTestGen** (Univ. Verona, ICST 2020, ~256 citations) — black-box test generation from Swagger. Same shape. URLs: https://profs.scienze.univr.it/~ceccato/papers/2020/icst2020api.pdf, https://github.com/SeUniVr/RestTestGen
- **Schemathesis** (Dygalo; open source, production) — property-based testing from OpenAPI/GraphQL. Uses the spec, not the traffic. URLs: https://schemathesis.readthedocs.io, https://github.com/schemathesis/schemathesis
- **EvoMaster** (open source; 2024 tool report, 23 citations) — evolutionary white-box REST API test generation. No semantic decoding. URLs: https://dl.acm.org/doi/10.1145/3293455, https://pmc.ncbi.nlm.nih.gov/articles/PMC11607064
- **MINER** (USENIX Security 2023, 36 citations) — hybrid data-driven REST fuzzing; outperforms RESTler on error-finding. Same gap. URL: https://www.usenix.org/system/files/sec23fall-prepub-129-lyu.pdf
- **ARTE** (IEEE TSE 2023, 59 citations) — extracts *realistic test data* for web APIs from public knowledge bases (DBpedia). Closest "semantic" prior art in the API-testing literature, but pulls meanings from external ontologies, not from the target's own rendered UI. URL: https://www.computer.org/csdl/journal/ts/2023/01/09712422/1AZLr0T7JfO

## 2. Closest academic prior art — UI-driven API inference

- **"Carving UI Tests to Generate API Tests and API Specification"** (Yandrapally, Sinha, Tzoref-Brill, Mesbah; ICSE 2023, 41 citations) — **the single closest published work to Rosetta.** It drives the web UI, captures XHR/fetch calls, infers REST endpoints + path parameters via "directed API probing", and emits an OpenAPI spec plus carved API-level tests. 98% precision / 56% recall on endpoint inference across 7 open-source apps. **Critical gap:** the output is *structural* (endpoints, params, response shapes) — it does NOT correlate opaque API code values (enum ints, status codes, type ids) with rendered DOM labels. DOM content is used only to identify navigation events and element interactions, not as a semantic ground truth. URLs: https://arxiv.org/abs/2305.14692, https://people.ece.ubc.ca/amesbah/resources/papers/apicarv-icse23.pdf

## 3. Browser-side data-flow / taint tracking (conceptually adjacent)

- **PanoptiChrome** (OpenReview, modern Chromium taint tracking) — dynamic in-browser taint propagation. URL: https://openreview.net/forum?id=bxwn1m8Y0S
- **Platform-Independent Dynamic Taint Analysis for JavaScript** (IEEE TS 2020) — generic data-flow tracking for JS values. URL: https://www.computer.org/csdl/journal/ts/2020/12/08511058/14H4WMh20et
- **Augur** (Northeastern PL lab, open source) — performant taint analysis for Node.js. URL: https://github.com/nuprl/augur
- **FP-tracer** (PoPETS 2024) — fine-grained browser fingerprinting detection via JS instrumentation. URL: https://petsymposium.org/popets/2024/popets-2024-0092.pdf
- **Who Left Open the Cookie Jar?** (Franken et al., USENIX Security 2018, 74 citations) — third-party cookie policy enforcement evaluation. URL: https://wholeftopenthecookiejar.com/static/tpc-paper.pdf

**Verdict for §3:** the technique ("follow an API field value as it propagates into the DOM") exists, but every published application targets *security* (XSS, secret leakage, cookie exfiltration), never *semantic dictionary derivation*. The mechanical plumbing Rosetta needs is publishable-quality research; the application is not.

## 4. Program synthesis from execution traces

- **Program synthesis from execution traces and demonstrations** (MIT MEng thesis, 2016) — match demonstration traces against a trace database to infer code snippets. URL: https://dspace.mit.edu/handle/1721.1/106098
- **Program Synthesis from Partial Traces** (Amazon/CMU, POPL 2025) — first technique to synthesize programs composing side-effecting functions, pure functions, and control flow from partial traces. URLs: https://dl.acm.org/doi/abs/10.1145/3729316, https://www.amazon.science/publications/program-synthesis-from-partial-traces
- **NeurIPS 2018 — Improving Neural Program Synthesis with Inferred Execution Traces** (71 citations) — split synthesis into "infer traces from I/O examples" + "infer programs from traces". URL: http://papers.neurips.cc/paper/8107-improving-neural-program-synthesis-with-inferred-execution-traces.pdf

**Verdict for §4:**"derive the function `code → label` from paired observations" *can* be framed as program synthesis from traces. No published work has done so for the UI↔API instance.

## 5. "Rosetta stone" analogy in RE/security literature

The metaphor is used loosely — Ghidra's decompiler is called "your Rosetta Stone" for binary translation (https://wasilzafar.com/pages/series/arm-assembly/arm-assembly-19-reverse-engineering.html); Cornell Tech's "Rosetta" project (Jan 2026) studies database-input semantic-injection attacks on embedding models (https://news.cornell.edu/stories/2026/01/rosetta-stone-database-inputs-reveals-serious-security-issue); the term appears generically for cross-domain translation. **No published tool uses the analogy for UI↔API code-decoding.** Naming-wise, Glyph's "Rosetta" is not colliding with a directly competing product in the same problem space.

## 6. Industry API security / discovery platforms

- **Burp Suite** (PortSwigger; commercial + Community; mature) — proxy + HTTP history + scanner. "DOM Invader" (https://portswigger.net/burp/documentation/desktop/tools/dom-invader) finds DOM-XSS sources/sinks. "Response extraction rules" define regex-extractable locations in responses (https://portswigger.net/burp/documentation/desktop/settings/response-extraction). The community "Burp DOM Scanner" ext auto-extracts regex matches from HTTP responses (https://github.com/snoopysecurity/awesome-burp-extensions). **Gap:** treats DOM as attack surface, never as semantic ground truth; no API-code↔DOM-label pairing.
- **Postman** (commercial + free) — generates collections *from specs*, not from traffic (https://learning.postman.com/docs/design-apis/specifications/generate-collections). Auto schema inference from samples is a long-standing community feature request that remains unaddressed (https://community.postman.com/t/auto-generating-json-schemas-to-test-in-postman/5595).
- **Akto** (open source + commercial; recent) — traffic-based API discovery + inventory + DAST. ~40 built-in "data types" (Email, Phone, etc.) for *sensitive-data classification* by field-name/value regex (https://www.akto.io/sensitive-data, https://docs.akto.io/). **Gap:** pattern-based field classification, not UI-derived semantic decoding.
- **Levo.ai** (commercial; recent) — eBPF-based API discovery; auto-generates OpenAPI specs and annotates fields with sensitive-data types (PII/PSI/PHI) using "data type inferences" (https://www.levo.ai/resources/blogs/frictionless-api-observability-87bb7). **Gap:** same as Akto — pattern-based, not UI-correlated.
- **Noname Security / Salt Security / Wallarm** (all commercial; mature) — API posture, runtime protection, behavioral ML. Salt's marketing emphasizes "business-logic learning" and "autonomous threat hunting" (https://salt.security/press-releases/salt-security-launches-first-of-its-kind-autonomous-threat-hunting-to-stop-stealthy-business-logic-api-attacks), but public docs make no claim of mapping opaque API codes to UI labels. Their ML learns *traffic sequences* for abuse detection, not *semantic dictionaries*.
- **SwaggerHub / SmartBear, Stoplight, Hoppscotch** (commercial + open source) — design-first OpenAPI editors (https://stoplight.io/api-design, https://swagger.io/specification). Help author specs, not derive them from traffic or DOM.

## 7. Web scraping / crawling + HAR analyzers

- **mitmproxy** (open source, MIT; mature) — native HAR support since v10.1 (Sept 2023; https://www.mitmproxy.org/posts/har-support). Provides wire capture; no DOM pairing.
- **BrowserMob Proxy** (open source, maintenance mode) — Selenium-era HAR capture; largely superseded by Playwright/CDP. URL: https://github.com/lightbody/browsermob-proxy
- **HAR analyzers** (Google ToolBox, jam.dev, ObservePoint, DebugBear, Keysight) — pure visualization/search over HAR files. No DOM pairing. URLs: https://toolbox.googleapps.com/apps/har_analyzer, https://jam.dev/utilities/har-file-viewer

## 8. Capture-stage pairing (specific to Glyph §4 stage 1)

- **Playwright Trace Viewer** (Microsoft; open source; mature) — **the missing half Glyph stage 1 needs already exists.** Captures per-action DOM snapshots (Before/Action/After), network requests, console logs, screenshots, source location in a single correlated `trace.zip`. Verified by reading https://playwright.dev/docs/trace-viewer. **Gap:** gives you the API+DOM pairing for free, but does not itself correlate codes with labels — that is Rosetta's job.
- **WebdriverIO DevTools service / Trace Mode** (open source) — analogous to Playwright Trace Viewer for WebdriverIO; HAR-style network entries + DOM snapshots + offline replay. URLs: https://webdriver.io/docs/wdio-devtools-service, https://webdriver.io/docs/devtools/wdio/trace-mode
- **Chrome DevTools Protocol** — `DOMSnapshot.captureSnapshot` + `Network.responseReceived` give programmatic access to the same data (https://chromedevtools.github.io/devtools-protocol/tot/DOMSnapshot).
- **Replay.io** — deterministic time-travel browser; captures everything but heavyweight.

## 9. DOM data-attribute mining + framework devtools

- **`data-*` attributes** (HTML5 standard; MDN https://developer.mozilla.org/en-US/docs/Web/HTML/How_to/Use_data_attributes) — frequently "the most specific semantic identifier for a given element" (Heap analytics, https://help.heap.io/hc/en-us/articles/37271861236881). Natural source of "the UI's own labels for opaque ids". No published tool systematically correlates `data-*` values with API codes.
- **`data-reactid`** (legacy React DOM attribute; https://www.pluralsight.com/resources/blog/guides/introduction-to-the-data-reactid-attribute-in-html) — pre-Fiber; not exposed by default in modern React.
- **React/Vue/Angular DevTools** — inspect component tree, props, state programmatically (https://stackoverflow.com/questions/29155044/how-do-you-inspect-a-react-elements-props-state-in-the-console). No published tool bridges API code → component prop → rendered label.

## 10. Confidence scoring (Fellegi-Sunter / record linkage / schema matching)

- **Fellegi-Sunter model** (1969; foundational) — probabilistic record linkage; produces match probability per record pair via per-field agreement/disagreement weights. **Directly applicable** to scoring "API record `status=3` ↔ DOM label 'Pending'": treat as a 1-field record-linkage problem. Implementations: Splink (open source, UK MoJ Analytical Services, https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html); interactive intro at https://www.robinlinacre.com/intro_to_probabilistic_linkage.
- **Schema matching survey** (Rahm & Bernstein 2001, 208 citations, https://dl.acm.org/doi/10.1007/s007780100057; Shvaiko & Euzenat 2005, 1812 citations, https://exmo.inria.fr/files/publications/shvaiko2005a.pdf; Microsoft Research TR-2001-17, https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-2001-17.pdf) — combinator/linguistic/constraint-based matching between schema elements. Useful for "which API field corresponds to which DOM element" (the alignment step before code↔label matching).
- **AWS Entity Resolution** (commercial managed service, https://aws.amazon.com/blogs/aws/aws-entity-resolution-match-and-link-related-records-from-multiple-applications-and-data-stores) — productization of the technique.

## 11. HITL labeling UX

- **Label Studio** (Heartex; open source; mature) — multi-modal annotation, supports active learning ("select most informative samples for annotation" — https://labelstud.io/blog/3-ways-to-automate-your-labeling-with-label-studio). The "low-confidence queue + paginated review" pattern is canonical.
- **Prodigy** (spaCy team; commercial) — scriptable, rapid binary accept/reject annotation flow; the canonical low-confidence review UX (https://prodi.gy).

---

## Verdict: is Rosetta novel?

**Yes — the *combination* is novel.** Every individual half exists in mature form:

| Half | Exists? | Source |
|------|---------|--------|
| Paired capture of API responses + DOM snapshots | **Yes** | Playwright Trace Viewer, WebdriverIO Trace Mode, CDP |
| Schema inference from JSON samples | Yes | quicktype (https://quicktype.io), genson |
| Traffic-based API discovery | Yes | Akto, Levo.ai, mitmproxy+HAR |
| UI-driven API spec inference | Yes (closest: structural only) | Carving UI Tests (ICSE 2023) |
| Probabilistic record-linkage confidence scoring | Yes | Fellegi-Sunter, Splink |
| HITL low-confidence review UX | Yes | Label Studio, Prodigy |
| DOM `data-*` attribute mining | Conceptually | Heap analytics practice; no published tool |
| Browser-side taint tracking of API values | Yes (for security) | PanoptiChrome, Augur |
| **UI↔API correlation to derive code→meaning dictionaries** | **No published prior art found** | **Glyph's gap** |

**The single closest published work** — Yandrapally et al., "Carving UI Tests to Generate API Tests and API Specification", ICSE 2023 — does the UI-driving + API-capture + spec-emission half but stops at *structure* (endpoints/params/shapes). It does not look at the rendered DOM *content* as semantic ground truth, and does not produce code→meaning dictionaries. Glyph's Rosetta sits precisely in the gap between (a) what Carving-UI-Tests captures and (b) what a human analyst currently does by eyeballing the rendered page.

**Recommended pivot/positioning:** rather than "novel capture technique," position Rosetta as *"semantic decoding layer over Playwright-Trace-Viewer-style paired captures, using Fellegi-Sunter-class confidence scoring and Label-Studio-class HITL review."* That framing makes the novelty crisp (the decoding layer + dictionary-emission + drift-monitoring) and the reuse explicit (don't reinvent capture, scoring, or labeling UI).

**Risks to monitor:**
1. Salt Security's "business-logic learning" ML is opaque; if their internal ML actually does code→label mapping, it's an unpublished competitor — worth a demo call before claiming total novelty in any external write-up.
2. The Carving-UI-Tests authors could extend their work to semantic decoding in a follow-up paper — cite them defensively and differentiate explicitly on "we emit code→meaning dictionaries; they emit OpenAPI specs."
3. Levo.ai's "data type inferences" wording is vague; verify with a demo that they don't already pair DOM labels with API codes.

## Open items / next actions

1. Read the full Carving-UI-Tests PDF (the page_reader returned only the chrome-extension PDF embedder stub; need a direct download) and verify whether their dynamic DOM analysis touches rendered text content at all.
2. Demo Akto and Levo to confirm the gap ("do you correlate DOM labels with API codes?").
3. Demo Salt Security to check the "business-logic learning" claim.
4. Prototype the Rosetta correlation pass over a Playwright `trace.zip` to validate that the pairing data is sufficient for code→label inference (this is the Phase-0 proof, RESEARCH.md §9).
5. Adopt Fellegi-Sunter via Splink (or a small reimplementation) for the confidence scorer rather than inventing a bespoke scheme.
6. Adopt Label Studio (or a stripped-down fork) for the low-confidence review UI rather than building from scratch.
