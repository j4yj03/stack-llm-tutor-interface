# Literaturnotizen: Learning AID 2025 – Kapitel mit Tutor-Bezug

Quellordner: `docs/literatur/`
Beide PDFs stammen aus demselben Open-Access-Sammelband (Tagungsband der Learning AID 2025).
Seitenzahlen im Folgenden = **Buchpagination**. In den PDF-Dateien gilt:
**Buchseite N = PDF-Seite N+1** (PDF-Seite 1 ist ein Sicherheitshinweis des Bereitstellers, PDF-Seite 2 ist die Kapiteltitelseite = erste Buchseite).

---

## Sammelband (gemeinsame Quelle)

> Leschke, Jonas / Queckenberg, Robert / Persike, Malte (Hg.) (2026): Learning Analytics,
> Artificial Intelligence und Data Mining in der Hochschulbildung. Beiträge zur Learning
> AID 2025 (Reihe: Zukunft der Hochschule). Bielefeld: transcript Verlag.
> ISBN 978-3-8376-8045-4 (Print) / 978-3-8394-5876-1 (PDF). Open Access.
> DOI: https://doi.org/10.14361/9783839458761

- Erschienen: 19.08.2026, 210 Seiten, transcript.open
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
- **Ergebnisse Studierende:**
  - Nutzung eher selten: 41 % seltener als monatlich, 37 % wöchentlich; 79 % nutzen
    parallel kommerzielle Tools (S. 51).
  - Vorteile kommerzieller Tools: Benutzerfreundlichkeit 51 %, Funktionen 49 %,
    Ergebnisqualität 49 % (S. 51).
  - Anwendungsfälle: Lernen/Klausurvorbereitung 49 %, Ideenentwicklung 46 %,
    sprachliche Verbesserung 46 % (S. 51 f.).
  - **Vorlagenbereich wird von 62,7 % nie genutzt** – hauptsächlich, weil er unbekannt
    war (56,8 %) (S. 52).
  - Zufriedenheit gespalten: 38 % zufrieden/very, 38 % unzufrieden/very (S. 51).
- **Ergebnisse Lehrende:**
  - Deutlich höhere Nutzung: 20 % täglich, 55,4 % wöchentlich; höhere Zufriedenheit
    (58 % zufrieden/sehr, nur 10 % unzufrieden) (S. 52 f.).
  - Anwendungsfälle: Erstellung von Lehrmaterialien 49 %, Aufgabenstellungen 49 %,
    Verwaltungsaufgaben 40 % (S. 53).
  - **Hauptnutzungsgrund: Datenschutz/Datenhoheit** („Datenschutz. Das ist der ganze
    Grund" – LEHR2, S. 53); dazu Verlässlichkeit, zentraler Zugang ohne Zusatz-Accounts.
- **Diskussion (S. 54 f.):**
  - Bereitstellung einer hochschuleigenen Lösung **garantiert keine breite Nutzung**,
    besonders nicht bei Studierenden; Datenschutz + Kostenersparnis reichen als
    Mehrwert-Argument allein nicht aus.
  - Studierende messen das Interface an den Standards kommerzieller Chatbots – obwohl
    im Hintergrund dieselben Modelle laufen (Hinweis auf unzureichendes Verständnis
    genativer KI).
  - Kernthese: Die **Nachbildung bekannter Chat-Interfaces** lädt zu bekannten
    Verhaltensmustern ein, statt gezielt didaktisch sinnvolle KI-Interaktionen
    anzuregen; es braucht Funktionen, die sich nicht in ChatGPT & Co. wiederfinden.
  - Deutet die Ergebnisse als Argument für **offene KI-Bildungstechnologien**
    (Verweis auf Paaßen et al. 2025, S. 55).

### Relevanz für die Masterarbeit

| Aspekt | Relevanz | Nutzung |
|---|---|---|
| Einleitung/Motivation | **mittel–hoch** | Beleg für die Verbreitung hochschuleigener KI-Plattformen und die Akzeptanzlücke bei Studierenden; Autorität: aktuelle dt. Praxisstudie 2025. |
| Forschungsbeitrag | **hoch** | Direktes Argument für einen **domänenspezifischen** Tutor (STACK-integriert, gestufte Hinweise) statt Chat-Interface-Nachbau: „Nachbildung bekannter Chat-Interfaces …" (S. 54) als Sprungbrett zur Problemstellung. |
| Datenschutz/Hosting | mittel | Argumentation für institutionellen Betrieb (SAIA/GWDG statt kommerzieller API) als Rahmenbedingung des Prototyps. |
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
  verwendbar für die Diskussion um Erwartungsmanagement/KI-Verständnis.

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

- **Ausgangslage („Wilder Westen", S. 58):** Fast alle Studierenden nutzen kommerzielle
  KI-Modelle (Verweis auf von Garrel/Mayer 2024, 2025), meist unreguliert, ohne
  didaktische Einbettung. Risiken:
  - **Cognitive Offloading** beschädigt kritisches Denken (Gerlich 2025).
  - **Inversion Effect** als kritischste Auswirkung im **ISAR-Modell** (Bauer et al.
    2025), das auf ICAP (Chi/Wylie 2014) und SAMR (Sailer et al. 2024) aufbaut.
  - **„Metakognitive Faulheit"** nach randomisierten Experimenten (Fan et al. 2024).
  - Stadler et al. (2024): Nach LLM-Nutzung geringere Fähigkeit zu komplexen
    Entscheidungen als nach Recherche mit Suchmaschine.
  - Formuliert als „breiter wissenschaftlicher Konsens", dass unzureichend angeleitete
    KI-Nutzung den Lernerfolg gefährdet (S. 58).
  - Rechtsrahmen: Urheberrecht, DSGVO, Prüfungsrecht; Abhängigkeit von kommerziellen
    Anbietern (S. 58).
- **Vier Dimensionen von Sokratest (S. 59):**
  1. Didaktischer Mehrwert (sokratische Dialoge zur Förderung kritischen Denkens),
  2. technische Innovation (niederschwelliger Open-Source-Ansatz),
  3. Rechtssicherheit (DSGVO, Urheberrecht),
  4. Ethik/KI-Kompetenzerwerb (co-kreative Entwicklung mit Studierenden).
- **Technik (S. 59 f.):**
  - **RAG** als „Open-Book-Klausur" für die KI; Wissensbasis = Kursmaterialien
    (Chunks → Vektoren → Retrieval → System-Prompt); Reduktion von Halluzinationen
    (Shuster et al. 2021); Antworten mit Quellenbelegen.
  - **System-Prompt** implementiert strukturiertes sokratisches Fragemodell nach der
    revidierten **Bloom'schen Taxonomie** (Anderson/Krathwohl 2001); iterativ verfeinert
    durch 50 simulierte Interaktionen (Blöcke von 5 Dialogen).
  - Stack: React, Qdrant, Postgres, Docker; Self-Hosting in Deutschland; Open-Source-LLMs
    über die **sichere Schnittstelle der GWDG** (= dieselbe Infrastruktur, über die auch
    der SAIA-Endpunkt dieser Arbeit läuft); kursspezifische Nutzer-/Dokumentenverwaltung
    (S. 60).
- **Evaluation (S. 60):** Pre-Post-Interventionsstudie, 62 Studierende, zwei Pilot-Kurse
  (Bachelor/Master), quantitative Befragungen (Lernpräferenzen, KI-Einstellungen,
  Wissen), zwei Fokusgruppen, **~400 Seiten Lerntagebücher**, Auswertung von **883
  Prompts + Antworten** in Arbeit.
- **Schlüsselergebnisse:**
  1. **Fragebereitschaft steigt deutlich:** Mittelwert 5,15 → 6,21 (7-stufige Skala),
     Cliff's Delta = 0,43; der Tutor wirkt als hemmungsfreier, vertrauensvoller Raum
     (S. 61).
  2. **„KI-Kurzschlüsse"/Antwortmaschine:** Neugier am „Warum" sinkt 6,15 → 4,93,
     Cliff's Delta = **−0,57**. Trotz explizit sokratischen Designs nutzten Studierende
     den Tutor als zu effiziente Antwortmaschine (S. 61). Beobachtung zu Modellen:
     Llama 3.3 (70B) ließ sich leichter zu ausführlichen Antworten überreden als neuere
     Reasoning-Modelle; **kein einziger faktisch falscher Antwortfall**, aber „in
     einzelnen Fällen etwas zu viele Informationen bereit" (S. 61).
  3. **KI-Kompetenz:** Selbstwahrgenommene Kompetenz d = 0,45, wahrgenommene Vorteile
     d = 0,37 (S. 62).
- **Diskussion/Ausblick (S. 62 f.):** Zentrale Herausforderung = didaktische
  Feinjustierung der **Balance zwischen direkter Hilfe und sokratischer Führung**;
  Studierendenwunsch nach **Modi** (direkte Antworten vs. kritisches Hinterfragen);
  anonymisiertes Learning-Analytics-Feedback für Lehrende (aggregierte Fragemuster);
  Weiterentwicklung des Prozessmodells zu einer finalen „Bauanleitung".

### Relevanz für die Masterarbeit

| Aspekt | Relevanz | Nutzung |
|---|---|---|
| Theoretische Fundierung | **hoch** | Cognitive Offloading, metakognitive Faulheit, Inversion Effect/ISAR, ICAP → warum **gestufte Hinweise ohne vorzeitigen Lösungsvorhalt** didaktisch begründet sind. Kernargumentationskette für die Hint-Policy. |
| Solution-Disclosure-Guard | **sehr hoch** | empirische Bestätigung des Risikos, das in `AGENTS.md` als Known Issue 6 und Work-Plan-Punkt 6 geführt ist: auch „gutartige" Tutoren geben „etwas zu viele Informationen" → Notwendigkeit von Output-Kontrollen auf Lösungsvorhalt. |
| Hint-Level-Design | **hoch** | Sokratest-Modus-Wunsch (Antwort vs. Hinterfragen) und die Antwortmaschinen-Falle stützen die zentrale, generische **Hint-Level-Progression** (Orientierung → Struktur → konkreter Schritt → Detail) und das Level-Capping. |
| Related Work / Forschungslücke | **sehr hoch** | Sokratest ist RAG-basierter Fachtext-Tutor **ohne** symbolische Fachprüfung (STACK/PRT) und ohne formale Hinweishierarchie → genau die Lücke, die der Prototyp füllt (symbolische Autorität + gestufte Hinweispolitik + kontrollierter Kontext). |
| Infrastruktur | **hoch** | GWDG academic cloud als LLM-Anbindung identisch zum SAIA-Backend der Arbeit (vgl. `AGENTS.md`, Modell `qwen3.8-27b`); Datenschutz-/Datensouveränitätsargumentation übertragbar. |
| Evaluationsdesign | **hoch** | Pre-Post + Fokusgruppen + Lerntagebücher + Prompt-/Interaktionsauswertung als Vorbild für `docs/evaluation_protocol.md`; Cliff's Delta als Effektstärkemaß; Hinweis auf Grundvoraussetzung („setzt voraus, dass grundlegende Kenntnisse vorhanden sind", S. 61) als Limitierungsvorbehalt. |
| Technischer Kern | mittel | RAG-Pipeline ist konzeptioneller Kontrastpunkt (open-book Kontext vs. STACK-authoritative Diagnose); keine direkte Umsetzungsreferenz für PromptBuilder/Task-Format. |

### Direkt zitierfähige Passagen

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
   Journal of Educational Technology. → Kernbeleg „KI-Nutzung ohne Anleitung schadet".
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
   aber **im Literaturverzeichnis des Kapitels nicht aufgelöst** – volle Referenz vor
   Zitat selbst recherchieren. ⚠️

### Kritische Anmerkungen für die wissenschaftliche Nutzung

- Praxisbericht/Projektbericht, **keine peer-reviewte Interventionsstudie**:
  - n = 62, zwei Kurse, hohe Abbruchquote zwischen Pre- und Post-Messung (autorseitig
    eingeräumt, S. 60) → keine Generalisierung.
  - Auswertung von Lerntagebüchern und Prompts zum Druckzeitpunkt noch in Arbeit →
    Ergebnisse der Selbstberichte, nicht Verhaltensdaten.
- Buck et al. ebenfalls Praxis-Evaluation mit Selektionseffekt (nur Bestandsnutzer:innen
  befragt, S. 51) → Trends, keine Kausalität.
- Beide Kapitel eignen sich für Einleitung, Related Work und Diskussion; für die
  methodische Kernargumentation der Arbeit (Hint-Level-Effektivität, Lösungsvorhalt-
  Detektion) sind die dort zitierten Primärstudien (Fan, Gerlich, Stadler, Chi/Wylie)
  heranzuziehen, nicht die Kapitel selbst.

---

## Positionierung im eigenen Related-Work-Kapitel (Vorschlag)

1. **Stand der Praxis:** Deutsche Hochschulen stellen KI-Interfaces bereit (Buck et al.),
   und erste kursspezifische KI-Tutoren entstehen (Gerber et al./Sokratest).
2. **Befund:** Bereitstellung allein wirkt nicht (Buck et al., S. 54); auch didaktisch
   gestaltete Tutoren geraten in die Antwortmaschinen-Falle (Gerber et al., S. 61).
3. **Lücke:** Kein der beiden Projekte kombiniert (a) eine **symbolisch autoritative
   fachliche Diagnose** (STACK/PRT), (b) eine **zentral konfigurierte, gestufte
   Hinweispolitik** mit doppeltem Lösungsvorhalt-Schutz und (c) **austauschbare
   LLM-Backends** – genau dies leistet der Prototyp dieser Arbeit.
4. **Ausblick/Validation:** Das Pre-Post-/Tagebuch-Design von Sokratest (S. 60) und die
   dort genannten Effektgrößen liefern Anknüpfungspunkte für das eigene
   Evaluationsprotokoll (`docs/evaluation_protocol.md`).

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
- [ ] Evaluationsdesign von Sokratest mit `docs/evaluation_protocol.md` abgleichen
      (Pre-Post, Effektgrößen, Prompt-Analyse).
- [ ] GWDG-Bezug (S. 60) in Infrastruktur-Kapitel der Arbeit zitierbar machen
      (deckt SAIA-Backend-Begründung mit).
