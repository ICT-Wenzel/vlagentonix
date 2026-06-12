Stufe 1 — Grundverständnis (eine Woche)
---------------------------------------

**A1 — Hello World Agent** Baue in _jedem_ der vier Haupt-Frameworks (LangGraph, AutoGen, CrewAI, Claude SDK) denselben minimalen Agenten: nimmt eine Frage entgegen, ruft ein Tool auf (z. B. Websuche), gibt eine Antwort zurück. Ziel: du siehst sofort, wie sich die vier Frameworks im Grundprinzip unterscheiden.

**A2 — Framework-Vergleichsmatrix** Füll nach A1 eine Tabelle aus: Komplexität, Kontrolle, Vendor Lock-in, Community, Kosten, wann du welches wählen würdest. Eigene Erfahrung, nicht Wikipedia.

Stufe 2 — Kernmechanik (zwei Wochen)
------------------------------------

**A3 — Tool Use vertiefen** Schreibe drei eigene Tools (z. B. Websuche, Datei lesen, Datum/Zeit) und binde sie in LangGraph ein. Der Agent soll selbst entscheiden, welches Tool er wann braucht.

**A4 — Memory einbauen** Erweitere A3: Der Agent soll sich über mehrere Läufe hinweg an frühere Ergebnisse erinnern. Kurzzeit im Kontext, Langzeit in einer Vektor-DB.

**A5 — Structured Output** Der Agent gibt kein Freitext-Ergebnis zurück, sondern ein typsicheres, strukturiertes Objekt (z. B. JSON-Schema). Baue das in LangGraph und im Claude SDK.

**A6 — Code Execution Agent** Baue einen Agenten, der Code generiert und ihn in einer Sandbox (E2B) ausführt. Ziel: du verstehst, was Sandboxing konkret bedeutet und wo die Grenzen liegen.

Stufe 3 — Multi-Agent (zwei Wochen)
-----------------------------------

**A7 — Zwei Agenten, eine Aufgabe** Baue ein minimales Zwei-Agenten-System in AutoGen: ein Planer-Agent zerlegt eine Aufgabe, ein Ausführungs-Agent erledigt sie. Kein Orchestrator-Framework — alles selbst verdrahtet, damit du die Kommunikation verstehst.

**A8 — CrewAI Crew** Baue dasselbe Szenario wie A7, aber mit CrewAI. Vergleiche danach: Was war einfacher, was hast du weniger im Griff?

**A9 — Orchestrator-Worker in LangGraph** Baue einen Orchestrator, der zur Laufzeit entscheidet, welchen von drei Worker-Agenten er aufruft. Das ist die direkte Vorbereitung auf dein eigenes System.

Stufe 4 — Dein Anwendungsfall (zwei Wochen)
-------------------------------------------

**A10 — Daten sammeln + Dokument erzeugen (v1)** Baue deinen eigenen Anwendungsfall als Einzel-Agent: eine Aufgabe rein, Agent sammelt Daten aus zwei Quellen, erzeugt ein strukturiertes Dokument. Kein Framework — direktes Claude SDK oder roher Agent Loop. Ziel: du verstehst, was unter der Haube passiert.

**A11 — Denselben Anwendungsfall in LangGraph** Bau A10 nochmal, diesmal mit LangGraph. Vergleiche: was gewinnst du, was verlierst du an Kontrolle?

**A12 — Eval-Harness bauen** Schreibe einen automatisierten Test, der A10 oder A11 gegen dein Eval-Set (5–10 Aufgaben) laufen lässt und dir sagt: wie viele bestanden, wo ist es gescheitert, warum.

Stufe 5 — Produktion & Sicherheit (eine Woche)
----------------------------------------------

**A13 — Prompt Injection angreifen und abwehren** Baue absichtlich eine Prompt-Injection in eine Datenquelle ein (z. B. eine Webseite mit versteckter Instruktion). Prüfe, ob dein Agent aus A10 darauf hereinfällt. Dann baue die Abwehr ein.

**A14 — Fehlerbehandlung & Resilience** Simuliere Ausfälle: ein Tool antwortet nicht, ein Tool gibt Müll zurück, der Agent läuft in eine Schleife. Wie verhält sich dein System? Baue Retries, Timeouts und harte Grenzen ein.

**A15 — Observability** Füge vollständiges Tracing und Logging zu A11 hinzu (LangSmith oder Langfuse). Beantworte nach einem Lauf: Wie viele Token wurden verbraucht? Wo hat der Agent am längsten gewartet? Wo ist er fast gescheitert?

Reihenfolge auf einen Blick
---------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   A1 → A2 → A3 → A4 → A5 → A6                            ↓                      A7 → A8 → A9                                 ↓                          A10 → A11 → A12                                       ↓                                A13 → A14 → A15   `

15 Aufgaben, aufbauend, jede mit einem klaren Ergebnis. A1–A2 kannst du in einer Woche erledigen, A15 bist du tief im Produktions-Denken. Willst du, dass ich für eine bestimmte Aufgabe einen konkreten Starter-Guide schreibe?