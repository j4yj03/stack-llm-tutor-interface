# Literaturnotizen: Learning AID 2025 – Kapitel mit Tutor-Bezug

**Status: lokal gesichtete Quellen mit kritischer Einordnung, 2026-10-02.**
Diese Notizen betreffen genau die zwei vorliegenden Kapitel, nicht eine
vollstaendige Literaturrecherche. Texte und Seitenzuordnung wurden lokal
extrahiert; Verlag, DOI-Ziele, Primaerstudien und Peer-Review-Verfahren wurden
hier nicht extern verifiziert. Fuer das eigene Design gilt
[eval-protocol-2](../evaluation_protocol.md), nicht automatisch das
Interventionsdesign einer zitierten Quelle.

Quellordner: `docs/literatur/`
Beide PDFs stammen aus demselben Open-Access-Sammelband (Tagungsband der Learning AID 2025).
Seitenzahlen im Folgenden = **Buchpagination**. In den PDF-Dateien gilt:
PDF-Seite 1 ist ein Sicherheitshinweis; PDF-Seite 2 ist die jeweilige
Kapiteltitelseite. Fuer den **1-basierten PDF-Seitenindex p** gilt:

| Datei | Buchseite | Beispiele |
|---|---|---|
| `9783839458761-049.pdf` | `49 + (p - 2)` fuer `p=2..8` | PDF 2 = Buch 49; PDF 7 = Buch 54; PDF 8 = Buch 55 |
| `9783839458761-057.pdf` | `57 + (p - 2)` fuer `p=2..9` | PDF 2 = Buch 57; PDF 5 = Buch 60; PDF 9 = Buch 64 |

Bei einer Bibliothek mit **0-basiertem** Seitenindex i entsprechend
`49 + (i - 1)` bzw. `57 + (i - 1)` verwenden. Die Sicherheitshinweise haben
keine Buchseite; die fruehere pauschale Zuordnung `N+1` war falsch.

---

## Sammelband (gemeinsame Quelle)

> Leschke, Jonas / Queckenberg, Robert / Persike, Malte (Hg.) (2026): Learning Analytics,
> Artificial Intelligence und Data Mining in der Hochschulbildung. Beiträge zur Learning
> AID 2025 (Reihe: Zukunft der Hochschule). Bielefeld: transcript Verlag.
> ISBN 978-3-8376-8045-4 (Print) / 978-3-8394-5876-1 (PDF). Open Access.
> DOI: https://doi.org/10.14361/9783839458761

- Uebernommene Verlagsangaben: 19.08.2026, 210 Seiten, transcript.open.
  Diese Bandmetadaten sind nicht vollstaendig aus den Kapiteldateien belegt;
  vor finaler bibliografischer Verwendung separat pruefen.
- Relevanz des Bandes insgesamt: Deutschsprachiger State of Practice 2025 zu KI in der
  Hochschullehre; gut als Zeitmarken-Zitat („Stand 2025/26") und für Related Work
  („KI-Tutoren an deutschen Hochschulen").

---

## Kapitel 1 – Buck/Christ/Kaib/Ulzheimer (S. 49–55)

**Datei:** `9783839458761-049.pdf`
**DOI:** https://doi.org/10.14361/9783839458761-049

### Bibliografie

> Buck, Isabella / Christ, Nina / Kaib, Alexander / Ulzheimer, Lisa (2026):
> Implementierung, Nutzung und Herausforderungen eines hochschuleigenen KI-Interfaces.
> In: Leschke/Queckenberg/Persike (Hg.): Learning Analytics, Artificial Intelligence und
> Data Mining in der Hochschulbildung. Bielefeld: transcript, S. 49–55.

### Zusammenfassung

Evaluation des hochschuleigenen KI-Interfaces **KI@HSRM** der Hochschule RheinMain
(SoSe 2025):

- **Plattform:** Zentrales Web-Frontend, Februar 2024 durch Präsidiumsbeschluss als
  modellhafte Einführung auf Basis der OpenAI-API gestartet; inzwischen zusätzlich DeepL
  (Übersetzung, ›Write‹), Text-to-Speech, Perplexity Sonar; lokal betriebene LLMs als
  Perspektive. Didaktische Einbettung v. a. über einen **Vorlagenbereich** mit Prompts
  (S. 50).
- **Methodik:** Online-Fragebogen (Ende Mai–Mitte Juli 2025; 74 Studierende, 78
  Lehrende) plus qualitative Interviews (6 Lehrende, 2 Studierende), ausgewertet per
  qualitativer Inhaltsanalyse nach Mayring (2022); nur Personen befragt, die das
  Interface bereits genutzt hatten (S. 51).
- Ergebnisse Studierende: Die folgenden Prozentwerte haben je Frage
  verschiedene Nenner, nicht immer alle 74 Teilnehmenden.
- Nutzung eher selten: 41 % seltener als monatlich, 37 % woechentlich; 79 %
  nutzen parallel kommerzielle Tools (`n=68`, S. 51).
- Genannte Vorteile kommerzieller Tools: Benutzerfreundlichkeit 51 %,
  Funktionen 49 %, Ergebnisqualitaet 49 % (`n=45`, S. 51).
- Anwendungsfaelle: Lernen/Klausurvorbereitung 49 %, Ideenentwicklung 46 %,
  sprachliche Verbesserung 46 % (`n=61`, S. 51 f.).
- **62,7 % nutzen die Vorlagen nie** (`n=59`); 56,8 % der Nichtnutzenden
  kannten sie nicht. Den zweiten Prozentsatz nicht auf alle Befragten beziehen
  (S. 52).
- Zufriedenheit: jeweils 38 % zufrieden/sehr bzw. unzufrieden/sehr
  (`n=63`, S. 51).
- Lehrende: 20 % taeglich, 55,4 % woechentlich (`n=65`); 58 % zufrieden/sehr,
  10 % unzufrieden/sehr (`n=60`, S. 52 f.).
- Lehrenden-Anwendungsfaelle: Lehrmaterialien und Aufgabenstellungen je 49 %,
  Verwaltung 40 % (`n=57`, S. 53).
- Datenschutz/Datenhoheit ist laut den sechs Interviews ein wichtiger
  Nutzungsgrund, etwa LEHR2: „Datenschutz. Das ist der ganze Grund" (S. 53).
  Das Zitat belegt eine Wahrnehmung, keine rechtliche Konformitaetspruefung.
- Diskussion: Die Autor:innen interpretieren ihre Daten als Hinweis, dass
  Bereitstellung allein keine breite Nutzung garantiert. Erklaerungen zu
  Usability, Vertrautheit, Kosten und Sichtbarkeit bleiben teilweise Vermutungen
  (S. 54 f.), keine kausalen Nachweise.
- Die Aussage, im Hintergrund liefen dieselben Sprachmodelle, stammt aus der
  Diskussion zu KI@HSRM (S. 54). Sie ist kein Nachweis gleicher Endpunkte,
  Prompts, Parameter oder Modellgewichte bei anderen Plattformen.
- Die Autor:innen vermuten, dass der Nachbau bekannter Chat-Interfaces
  bekannte Nutzungsmuster beguenstigt, und schlagen gezieltere didaktische
  Funktionen sowie offene KI-Bildungstechnologien vor (S. 54 f.). Daraus folgt
  nicht bereits eine erwiesene Ueberlegenheit eines gestuften Mathematiktutors.

### Relevanz für die Masterarbeit

| Aspekt | Relevanz | Nutzung |
|---|---|---|
| Einleitung/Motivation | **mittel–hoch** | Beispiel fuer ein Hochschulinterface und unterschiedliche berichtete Nutzungs-/Akzeptanzmuster, keine repraesentative Hochschulgesamtquote. |
| Forschungsbeitrag | **hoch** | Motivation, domänenspezifische Interaktionsformen zu untersuchen; der Beitrag belegt nicht die Wirkung unserer Hilfestufen. |
| Datenschutz/Hosting | mittel | Wahrgenommener institutioneller Mehrwert; keine uebertragbare Freigabe fuer SAIA, GET-Daten oder Judge-Verarbeitung. |
| Methodik | gering | Survey-/Interviewdesign nur am Rande übertragbar; die Arbeit evaluiert primär Prompt-/Hinweisqualität. |
| Technischer Kern (PromptBuilder, Hint-Policy, STACK) | **keiner** | Kein Tutoring, keine Mathematik-Didaktik, keine automatische Bewertung – nur Kontextkapitel. |

### Direkt zitierfähige Passagen

- S. 54: „Vielleicht sind unsere Ergebnisse ein Hinweis darauf, dass die Nachbildung
  bekannter Chat-Interfaces nicht der beste Weg ist, um die potenziellen Vorteile einer
  hochschuleigenen KI-Lösung zu implementieren und kommunizieren."
- S. 54: „Besonders die ernüchternde Unbekanntheit der didaktischen Vorlagen zeigt, dass
  die Nutzeroberfläche von KI@HSRM zu bekannten Verhaltensmustern einlädt, statt gezielt
  pädagogisch sinnvolle KI-Interaktionen anzuregen."
- S. 53: „Datenschutz. Das ist der ganze Grund" (Lehrenden-Interview, LEHR2).
- S. 54: Feststellung, dass Studierenden kommerziellen Tools höhere Antwortqualität
  zuschreiben, „obwohl im Hintergrund dieselben Sprachmodelle verwendet werden" –
  als autorenseitige Einordnung fuer Erwartungsmanagement nutzbar, nicht als
  unabhängiger Modell-/Providervergleich. Zeilenumbruch und Originalwortlaut
  vor einem finalen direkten Zitat am Kapitel prüfen.

### Sekundärquellen aus dem Kapitel (zu beschaffen)

- **von Garrel, Jörg / Mayer, Jana (2025):** Künstliche Intelligenz im Studium – Eine
  quantitative Längsschnittstudie zur Nutzung KI-basierter Tools durch Studierende.
  Hochschule Darmstadt. DOI: 10.48444/H_DOCS-PUB-533 → Standardbeleg für
  KI-Nutzungsverbreitung unter dt. Studierenden; in **beiden** Kapiteln zitiert,
  sollte in die eigene LitListe.
- **Paaßen, Benjamin u. a. (2025):** KI-Infrastruktur für Digitale Autonomie an
  Hochschulen. AIDARE. https://aidare.org/ki-infrastruktur-fur-digitale-autonomie-an-hochschulen/
  → Für Abschnitt zu offenen/institutionellen KI-Infrastrukturen.
- **Buck, Isabella / Jost, Christiane / Kreis-Hoyer, Petra / Limburg, Anika (2023):**
  KI-induzierte Transformation an Hochschulen. Diskussionspapier Hochschulforum
  Digitalisierung 26 → Hintergrund Hochschultransformation.
- Mayring, Philipp (2022): Qualitative Inhaltsanalyse. 13. Aufl. Beltz → Methodikreferenz,
  falls qualitative Auswertung eigener Chatdaten.

---

## Kapitel 2 – Gerber/Lorenz/Pfeiffer (S. 57–64)

**Datei:** `9783839458761-057.pdf`
**DOI:** https://doi.org/10.14361/9783839458761-057

### Bibliografie

> Gerber, Alexander / Lorenz, Lars / Pfeiffer, Ulrich (2026): KI-Tutoren in der Lehre:
> rechtlich sicher, didaktisch wertvoll, technisch innovativ. In: Leschke/Queckenberg/
> Persike (Hg.): Learning Analytics, Artificial Intelligence und Data Mining in der
> Hochschulbildung. Bielefeld: transcript, S. 57–64.

### Zusammenfassung

Praxisbericht zum Projekt **Sokratest** (Practice-Projekt von KI:edu.nrw): Prozessmodell
(„Blaupause"), mit dem Lehrende ohne technische Vorkenntnisse **kursspezifische
KI-Tutoren** erstellen können.

- Ausgangslage (S. 58): Die Autor:innen beziehen "fast alle" auf Teilnehmende
  der zitierten von-Garrel/Mayer-Studien, nicht auf saemtliche Studierende.
  Sie diskutieren unangeleitete Nutzung und moegliche didaktische Risiken.
- Cognitive Offloading, kritisches Denken und "metakognitive Faulheit" werden
  mit Verweisen auf Gerlich (2025), Fan et al. (2024) und Stadler et al. (2024)
  erörtert. Die Primärtexte wurden hier nicht geprüft; aus diesen Verweisen
  keine universellen kausalen Aussagen über jede KI-Nutzung ableiten.
- "Inversion Effect"/ISAR (Bauer et al. 2025) wird im Kapitel mit ICAP/SAMR
  verbunden. Die Referenz Bauer et al. ist im lokalen Kapitelverzeichnis
  nicht aufgeloest; die Modellgenealogie bleibt vor eigenem Zitat zu pruefen.
- Der Ausdruck "breiter wissenschaftlicher Konsens" ist eine Formulierung
  der Kapitelautor:innen (S. 58), keine eigene systematische Evidenzsynthese.
- Vier beanspruchte Dimensionen (S. 59): didaktischer Mehrwert, technische
  Innovation, Rechtssicherheit und Ethik/KI-Kompetenz. Zielbeschreibung und
  berichtete Umsetzung nicht mit unabhaengiger Wirksamkeits-/Rechtspruefung
  gleichsetzen.
- RAG-Pipeline (S. 59 f.): Kursmaterialien werden gechunkt, vektorisiert,
  abgerufen und als Kontext uebergeben. Die Metapher "Open-Book-Klausur" und
  der Verweis auf weniger Halluzinationen sind autorenseitige Begruendungen;
  RAG garantiert keine korrekte mathematische Bewertung.
- Sokratischer Systemprompt nach revidierter Bloom-Taxonomie; laut Kapitel
  durch 50 simulierte Interaktionen in Fuenferbloecken verfeinert (S. 60).
  Diese Simulationen sind kein Lernwirksamkeitsnachweis und keine Validierung
  unserer konkreten Stufenfolge.
- React, Qdrant, Postgres, Docker, Self-Hosting in Deutschland und eine
  "sichere Schnittstelle" der GWDG werden berichtet (S. 60). **Ob es derselbe
  SAIA-Endpunkt oder derselbe Modellalias wie hier ist, bleibt unbelegt.**
  Auch Rechts-/Datensouveraenitaetszusagen des Projekts gelten nicht automatisch
  fuer diesen Tutor oder dessen zusaetzliche Judge-Verarbeitung.
- **Evaluation (S. 60):** Pre-Post-Interventionsstudie, 62 Studierende, zwei Pilot-Kurse
  (Bachelor/Master), quantitative Befragungen (Lernpräferenzen, KI-Einstellungen,
  Wissen), zwei Fokusgruppen, **~400 Seiten Lerntagebücher**, Auswertung von **883
  Prompts + Antworten** in Arbeit.
- Berichtete Fragebereitschaft: Mittelwert 5,15 auf 6,21, siebenstufige Skala,
  Cliff's Delta 0,43 (S. 61). Der Vergleich betrifft laut Beschreibung
  Fragen an Lehrende versus den Tutor; er ist keine reine Verhaltenszaehlung
  und kein eigenstaendiger Kausalnachweis.
- Berichtete Neugier am "Warum": Mittelwert 6,15 auf 4,93, Cliff's Delta
  -0,57. Die Autor:innen deuten das als moegliche Antwortmaschinen-Nutzung;
  Motivation wurde nicht durch unsere Skriptsimulation untersucht (S. 61).
- Die Aussagen zu Llama 3.3 (70B), leichterer Ueberredbarkeit und "keinem"
  gaenzlich falschen Fall betreffen die beschriebenen Beobachtungen (S. 61).
  Es fehlen hier ein unabhaengiger Modellbenchmark und ein vollstaendiger
  mathematischer Nachweis; "etwas zu viele Informationen" ist nicht dasselbe
  wie positiv nachgewiesener kompletter Loesungsverrat.
- Selbstwahrgenommene Kompetenz `d=0,45` und wahrgenommene Vorteile `d=0,37`
  werden berichtet (S. 62); daraus folgt keine objektive Kompetenzsteigerung.
- **Diskussion/Ausblick (S. 62 f.):** Zentrale Herausforderung = didaktische
  Feinjustierung der **Balance zwischen direkter Hilfe und sokratischer Führung**;
  Studierendenwunsch nach **Modi** (direkte Antworten vs. kritisches Hinterfragen);
  anonymisiertes Learning-Analytics-Feedback für Lehrende (aggregierte Fragemuster);
  Weiterentwicklung des Prozessmodells zu einer finalen „Bauanleitung".

### Relevanz für die Masterarbeit

| Aspekt | Relevanz | Nutzung |
|---|---|---|
| Theoretische Fundierung | **hoch** | Forschungsanlass für aktive Unterstuetzung; Primärliteratur und Geltungsbereich pruefen. Keine direkte Validierung der konkreten Stufen 0-4. |
| Offenlegungsprüfung | **hoch** | Anlass, zu umfangreiche Hilfe getrennt zu untersuchen. Unser [Protokoll](../evaluation_protocol.md#7-auswertung) trennt Hinweisumfang, Loesungsanwesenheit und unzulaessige Offenlegung; kein Verweis auf veränderliche Agentenpunktnummern. |
| Hint-Level-Design | **hoch** | Moduswuensche und berichtete Risiken motivieren empirische Regel-/Startvergleiche, nicht eine unveraenderliche ideale Progression. |
| Related Work | **hoch** | Im betrachteten Kapitel wird RAG/sokratische Führung beschrieben, nicht eine STACK-PRT-Kopplung oder unser formales Stufen-/Kontextschema. Das ist ein begrenzter Kontrast, keine allgemeine Neuheitsbehauptung. |
| Infrastruktur | mittel | GWDG-Bezug ist belegt; gleicher SAIA-Endpunkt/Alias und uebertragbare Datenschutzkonformitaet sind es nicht. |
| Evaluationsdesign | **hoch** | Anregung fuer eine spaetere echte Nutzerstudie; unsere initialen Antwort-/Skriptvergleiche messen keine Lern- oder Motivationseffekte. Effektgroessen nur bei geeigneten Daten und beschriebenen Nennern verwenden. |
| Technischer Kern | mittel | RAG ist ein Kontrast zu unserem Task-ID-Kontextladen. STACK-Autoritaet bleibt Ziel bei echten Pruefergebnissen; die initiale Fehlerbank liefert keine solche Bewertung. |

### Direkt zitierfähige Passagen

Die folgenden Formulierungen sind **Aussagen der Kapitelautor:innen**. Die
weitreichenden Deutungen nicht als eigene bewiesene Kausalitaet uebernehmen.

- S. 58: „Es kann daher als breiter wissenschaftlicher Konsens bezeichnet werden, dass
  eine unzureichend angeleitete und nicht an didaktischen Zielen ausgerichtete Nutzung
  von KI an der Hochschule den Lernerfolg von Studierenden nachhaltig gefährdet."
- S. 61: „Der Mittelwert fiel von 6,15 (pre) auf 4,93 (post) … Dieses Ergebnis deutet
  darauf hin, dass der Tutor trotz seines explizit sokratischen Designs von einigen
  Studierenden als zu effiziente Antwortmaschine wahrgenommen wurde …"
- S. 61: „In keinem einzigen Fall trafen diese Modelle gänzlich falsche Aussagen; sie
  stellten aber in einzelnen Fällen etwas zu viele Informationen bereit."
- S. 62: „Die Balance zwischen direkter Hilfe und sokratischer Führung ist weiter zu
  optimieren, um einen Verlust tiefergehender Neugier zu vermeiden."
- S. 59: RAG als „Art ›Open-Book-Klausur‹ für die KI".

### Sekundärquellen aus dem Kapitel (zu beschaffen)

Priorisiert für die eigene Literaturliste:

1. **Fan, Yizhou u. a. (2024):** Beware of metacognitive laziness: Effects of generative
   artificial intelligence on learning motivation, processes, and performance. British
   Journal of Educational Technology. → Primaerquelle zu spezifischen
   Untersuchungsbedingungen beschaffen; kein pauschaler Beleg, dass jede
   unangeleitete KI-Nutzung schadet.
2. **Gerlich, Michael (2025):** AI Tools in Society: Impacts on Cognitive Offloading and
   the Future of Critical Thinking. Societies 15(1), 6. → Cognitive Offloading.
3. **Stadler, Matthias / Bannert, Maria / Sailer, Michael (2024):** Cognitive ease at a
   cost: LLMs reduce mental effort but compromise depth in student scientific inquiry.
   Computers in Human Behavior. → LLM vs. Suchmaschine.
4. **Chi, Michelene / Wylie, Ruth (2014):** The ICAP framework. Educational Psychologist
   49(4), 219–243. → Theorieanker für aktive Lernaktivität; passt zur Hinweis-Eskalation.
5. **Sailer, Michael u. a. (2024):** Learning activities in technology-enhanced learning:
   systematic review of meta-analyses … Learning and Individual Differences 112 (102446).
6. **Shuster, Kurt u. a. (2021):** Retrieval Augmentation Reduces Hallucination in
   Conversation. EMNLP. → falls RAG-Vergleich im Related-Work-Kapitel.
7. **Anderson, Lorin W. / Krathwohl, David R. (2001):** A Taxonomy for Learning, Teaching,
   and Assessing (Revision der Bloom-Taxonomie). → falls Hint-Level kognitiv begründet
   werden sollen.
8. **von Garrel/Mayer (2024):** Which features of AI-based tools are important for
   students? Computers and Education: Artificial Intelligence 7 (100311).
9. **Bauer et al. (2025)** (ISAR-Modell/„Inversion Effect"): im Text zitiert (S. 58),
   aber **im Literaturverzeichnis des Kapitels nicht aufgelöst**; volle Referenz
   und Geltungsbereich vor einem eigenen Zitat recherchieren.

### Kritische Anmerkungen für die wissenschaftliche Nutzung

- Beide Kapitel nennen einen zugrunde liegenden Tagungs-Impulsbeitrag.
  Der **Peer-Review-Status ist aus den lokalen Kapiteldateien nicht
  feststellbar**; weder positive noch negative Review-Zusage ableiten.
- Sokratest berichtet eine Pre-Post-Interventionsstudie mit 62 Teilnehmenden
  aus zwei Kursen und Abbruch zwischen den Messzeitpunkten (S. 60 f.). Das
  Kapitel beschreibt keine randomisierte Kontrollgruppe. Ohne vollstaendige
  Stichproben-/Auswertungsdetails keine kausale oder allgemeine Wirkung behaupten.
- Tagebuch-/Promptauswertung ist laut Bericht noch in Arbeit; einzelne erste
  Beobachtungen werden genannt. Nicht als bereits vollstaendig ausgewertete
  Verhaltensdaten oder unabhaengige mathematische Fehlerrate zitieren.
- Buck et al. ebenfalls Praxis-Evaluation mit Selektionseffekt (nur Bestandsnutzer:innen
  befragt, S. 51) → Trends, keine Kausalität.
- Beide Kapitel eignen sich fuer Einleitung, Related Work und Diskussion.
  Primaerstudien zu Lernaktivitaet oder KI-Nutzung muessen mit ihrem Design und
  Geltungsbereich selbst geprueft werden; sie validieren nicht automatisch
  konkrete Hint-Level oder einen mathematischen Offenlegungsdetector. Fuer
  diese Fragen ist weitere einschlaegige Literatur zu beschaffen.

---

## Positionierung im eigenen Related-Work-Kapitel (Vorschlag)

1. **Praxisbeispiele:** Die zwei betrachteten Kapitel berichten ueber KI@HSRM
   und Sokratest als Beispiele fuer Hochschulinterfaces und kursspezifische
   KI-Tutoren; keine vollstaendige Bestandsaufnahme oder Prioritaetsbehauptung.
2. **Berichtete Befunde:** Buck et al. diskutieren begrenzte Nutzung trotz
   Bereitstellung (S. 54); Gerber et al. berichten Hinweise auf als zu direkt
   wahrgenommene Hilfe (S. 61). Das sind keine universellen Kausalgesetze.
3. **Begrenzter Kontrast:** In diesen **zwei Kapiteln** wird unsere Kombination
   aus Task-Kontext, formal konfigurierbaren Stufen und kontrollierten
   Diagnose-/Regelkontrasten nicht beschrieben. Daraus folgt keine Neuheit
   gegenueber der gesamten Forschung. Unser erster empirischer Schritt hat
   noch keine verifizierte PRT-Kopplung und behauptet sie nicht als Ergebnis.
4. **Eigenes Design:** [eval-protocol-2](../evaluation_protocol.md) beginnt mit
   synthetischen Referenzhypothesen, Stufenpilot und gehaltenem Testteil,
   getrennten Diagnose-/Regelkontrasten, identischen Skriptsessions und echter
   `general`-Policy. Skriptsimulation und optionaler LLM-Judge ersetzen keine
   Studierenden-, Lern- oder Motivationsstudie.

---

## BibTeX

```bibtex
@incollection{buck2026kiinterface,
  author    = {Buck, Isabella and Christ, Nina and Kaib, Alexander and Ulzheimer, Lisa},
  title     = {Implementierung, Nutzung und Herausforderungen eines hochschuleigenen {KI}-Interfaces},
  booktitle = {Learning Analytics, Artificial Intelligence und Data Mining in der Hochschulbildung},
  editor    = {Leschke, Jonas and Queckenberg, Robert and Persike, Malte},
  series    = {Zukunft der Hochschule},
  year      = {2026},
  address   = {Bielefeld},
  publisher = {transcript Verlag},
  pages     = {49--55},
  doi       = {10.14361/9783839458761-049},
  note      = {Beitr{\"a}ge zur Learning AID 2025, Open Access}
}

@incollection{gerber2026kitutoren,
  author    = {Gerber, Alexander and Lorenz, Lars and Pfeiffer, Ulrich},
  title     = {{KI}-Tutoren in der Lehre: rechtlich sicher, didaktisch wertvoll, technisch innovativ},
  booktitle = {Learning Analytics, Artificial Intelligence und Data Mining in der Hochschulbildung},
  editor    = {Leschke, Jonas and Queckenberg, Robert and Persike, Malte},
  series    = {Zukunft der Hochschule},
  year      = {2026},
  address   = {Bielefeld},
  publisher = {transcript Verlag},
  pages     = {57--64},
  doi       = {10.14361/9783839458761-057},
  note      = {Beitr{\"a}ge zur Learning AID 2025, Open Access}
}

@book{leschke2026learningaid,
  title     = {Learning Analytics, Artificial Intelligence und Data Mining in der Hochschulbildung},
  subtitle  = {Beitr{\"a}ge zur Learning AID 2025},
  editor    = {Leschke, Jonas and Queckenberg, Robert and Persike, Malte},
  series    = {Zukunft der Hochschule},
  year      = {2026},
  address   = {Bielefeld},
  publisher = {transcript Verlag},
  isbn      = {978-3-8376-8045-4},
  doi       = {10.14361/9783839458761},
  note      = {Open Access}
}
```

---

## Offene To-dos aus dieser Sichtung

- [ ] Primärliteratur beschaffen: Fan et al. 2024, Gerlich 2025, Stadler et al. 2024,
      Chi/Wylie 2014, von Garrel/Mayer 2025 (vorrangig).
- [ ] Referenz „Bauer et al. 2025" (ISAR/Inversion Effect) recherchieren – im Kapitel
      nicht aufgelöst.
- [ ] Primaerstudien, Bandmetadaten und Peer-Review-Verfahren vor finaler
      wissenschaftlicher Einordnung pruefen; hier wurden keine externen
      Literatur-/Provideraufrufe gemacht.
- [ ] Eine kuenftige Nutzerstudie separat vom initialen Antwort-/Skriptvergleich
      planen. Ergebnisse fremder Pre-Post-Studien nicht auf unsere Simulation
      oder auf einzelne Diagnosefragen uebertragen.
- [ ] GWDG-Bezug (S. 60) als institutionelle Anbindung zitieren, aber denselben
      SAIA-Endpunkt/Alias nur mit eigener Evidenz benennen. TLS, Hosting,
      GET-Logs und zusaetzliche Judge-Verarbeitung separat governancepruefen.
