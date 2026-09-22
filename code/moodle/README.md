# Moodle-Snippets für den KI-Tutor

## Feld-Zuordnung

Dies sind **Referenzbausteine für einzelne Moodle/STACK-Zielfelder**, kein
vollständiger Fragenexport und keine eigenständig ausgeführten JavaScript-Dateien.
Der Tutor-Link steht im Fragetext. Nur STACK bewertet Mathematik und liefert
PRT-Diagnosen; JavaScript transportiert Daten, das LLM formuliert Hinweise.

| Datei | Moodle/STACK-Zielfeld | Inhalt |
| --- | --- | --- |
| `question_variables.txt` | Fragevariablen / Question variables | Ausschließlich Maxima/STACK-Zuweisungen für `v`, `rdm`, `rdm2`, `pp`, `p` |
| `fragetext_castext.html` | Fragetext / Question text, HTML-Quelltextmodus | CASText, Eingabe `ans1`, Tutor-Bereich und ein `[[javascript]]`-Block; bewusst **kein** `[[feedback:...]]`-Tag |
| `prt_feedback.html` | Feedback der passenden PRT-Zweige; erscheint als spezifisches Feedback | Zweig-Beispiele für `missing_chain_rule_inner_derivative` und `wrong_derivative_inner_exp`, jeweils im Container `ai-tutor-feedback` (Lesestelle für `get_content`) mit Marker zur exakt bewerteten Antwort; sichtbare Texte dürfen CAS-Variablen wie `{@pp@}` nutzen |

Keine Datei als `<script src="...">` laden. Die HTML-Dateien enthalten CASText,
das erst STACK auswertet. Eingabetyp, korrekte Antwort und PRT-Prüfungen bleiben
in ihren Moodle-Feldern; die Bausteine erzeugen keinen Diagnosebaum.

## Installation

1. In einer Testkopie der bestehenden STACK-Frage arbeiten. Die fünf mathematischen Zuweisungen aus `question_variables.txt` übernehmen; Formel und Randomisierung sind unverändert. Andere für die bestehende Frage notwendige Variablen nicht löschen.
2. `fragetext_castext.html` dem Feld Fragetext im HTML-/Quelltextmodus zuordnen. Der Rich-Text-Editor darf JavaScript nicht in Absätze oder HTML-Entities umwandeln. Die Eingabe muss `ans1` heißen. Ein `[[feedback:...]]`-Tag gehört **nicht** in den Fragetext: Das PRT-Feedback wird über die spezifische Feedback-Ausgabe von Moodle angezeigt. In bestehenden Fragen vorhandene `[[feedback:...]]`-Tags nicht einfach löschen, ohne die Frage anschließend zu testen; solche Tags steuern die Anzeige von PRT-Feedback.
3. `BASE_URL` **einmal, am Anfang des JavaScript-Blocks**, konfigurieren. `http://127.0.0.1:8000/start` ist nur für lokale Entwicklung: Die Adresse meint den Rechner des jeweiligen Browsers, nicht den Moodle-Server. Im Hochschulbetrieb eine für Lernende erreichbare HTTPS-Adresse des Tutors einsetzen. Keine Secrets oder Zugangsdaten in die URL schreiben.
4. `QID` auf eine vorhandene Backend-Aufgaben-ID abstimmen. `MODEL` bleibt normalerweise leer und verwendet den Backend-Standard. Ein explizites Modell muss in dessen `ALLOWED_MODELS` stehen. Hinweisstufe ist zunächst `1`.
5. `prt_feedback.html` enthält je PRT-Zweig einen Block: pro Zweig nur den passenden Block in den Feedback-CASText des Knotens einfügen, der den bezeichneten Fehler tatsächlich festgestellt hat. Für andere diagnostizierte Zweige Code und Feedback fachlich passend ergänzen. Pro ausgegebenem PRT-Pfad höchstens **einen** Diagnose-Marker ausgeben, jeweils innerhalb des Containers `ai-tutor-feedback` (Lesestelle für `get_content`); der Container muss erhalten bleiben. Der Marker-Inhalt bleibt `[[entityescape]]{#ans1#}[[/entityescape]]` — die Bindung prüft die Antwort, nicht den sichtbaren Text; sichtbare Zweigtexte dürfen CAS-Variablen wie `{@pp@}` für variantenkorrekte Formulierungen nutzen. Kein Marker in nicht bewerteten, ungültigen oder nicht eindeutig diagnostizierten Fällen. Die gültige Antwort und die PRT-Logik nicht durch JavaScript ersetzen.
6. Mehrere Zufallsvarianten und die unten aufgeführten Moodle-Testpunkte prüfen. Das Backend muss auf den zugehörigen Stand mit `funktion`, generischem `question_text_template` und Variantenschutz aktualisiert sein.

Der Baustein setzt bewusst **kein** `[[feedback:...]]`-Tag in den Fragetext:
Das PRT-Feedback erscheint als spezifisches Feedback gemäß den Moodle-/Test-
Einstellungen. Ist es dort nicht sichtbar (z. B. Review-Optionen in Tests oder
abgeschaltetes Feedback), kann der Baustein keinen Diagnose-Marker lesen; der
Tutor-Link bleibt dann bei `unknown_error` und es gibt nur allgemeine Hinweise [3].

## Migration

| Alter Dateiname | Neuer Dateiname |
| --- | --- |
| `questiontext.js` | `fragetext_castext.html` |
| `PRT feedback.html` | `prt_feedback.html` |
| `variables.txt` | `question_variables.txt` |

Das alte rohe `<script>` vollständig durch den STACK-JS-Baustein ersetzen,
nicht parallel betreiben. Globale IDs, Moodle-DOM-Suche und `MutationObserver`
entfallen. Alle alten PRT-Marker ebenfalls ersetzen: Der bisherige leere
`span` konnte eine Diagnose nicht an eine konkrete bewertete Antwort binden.

`url` und `urlencode_basic` sind in `question_variables.txt` als
**auskommentierter Referenzblock** erhalten (Maxima kennt keine verschachtelten
Blockkommentare; der innere Kommentar wurde darum als Klartext eingefügt). Zum
Einkommentieren nur dann greifen, wenn eine alte Frage noch `urlencode_basic`
oder den Validator `validate_listlength` referenziert; anschließend die
Input-Extra-Optionen prüfen. Die geprüfte Definition von `validate_listlength`
validierte keine Listenlänge, sondern rief das Encoding-Experiment auf und gab
immer `""` zurück. Im geprüften Moodle-Verzeichnis liegt kein Fragenexport mit
den tatsächlichen Input-Optionen vor.
**Deshalb in Moodle unter Eingabe `ans1` → Extra options / Zusätzliche Optionen
gezielt `validator:validate_listlength` entfernen**, falls vorhanden. Auch
`feedback:validate_listlength`, andere Eingaben und PRT-/Feedbackvariablen auf
Verweise auf diese experimentellen Namen prüfen. Nur diese experimentellen
Einträge entfernen, nicht andere echte Validatoren. Ein in Moodle unter demselben
Namen inzwischen fachlich geänderter Validator muss zunächst gesondert geprüft
werden. Ein verbleibender Verweis auf eine gelöschte Funktion kann die
Validierung fehlschlagen lassen; die grundlegende STACK-Validierung bleibt
aktiv [6].

## STACK-Anforderungen

Die offizielle Dokumentation und der öffentliche STACK-Quellcode wurden am
2026-09-21 geprüft, Quellstand `610fb70e37a2d04041b0c1fa07c4308b40dc5553` [1-7].
Die installierte Moodle-/STACK-Version ist hier nicht bekannt. STACK führte
die Sandbox-Blöcke mit 4.4.3 ein; **4.4.3 allein ist keine hinreichende
Versionsgarantie**. Benötigt werden auf beiden Seiten der Bridge:

- `[[javascript]]`, das eine versteckte Sandbox mit automatisch importiertem `stack_js` erzeugt. Kein eigener Import und keine externen JS-Abhängigkeiten [2].
- `request_access_to_input("ans1", true, true)`, einschließlich der Fragebegrenzung im dritten Argument (STACK-JS 1.3.0). Das Promise liefert die ID eines **lokalen versteckten Spiegel-Inputs**, nicht das Moodle-Eingabefeld. Moodle-`input`- und `change`-Ereignisse kommen dort als `change` an [1, 7].
- `get_content(id)` (STACK-JS 1.1.0), das asynchron `innerHTML` oder `null` liefert; `register_external_button_listener(id, callback)` (1.2.0); die korrigierte `switch_content`-Implementierung (1.0.1) [1, 7].
- `register_validation_state_listener(name, callback, limittoquestion)` für die automatische Diagnoseübernahme nach abgeschlossener Eingabevalidierung. Fehlt die API in der installierten STACK-Version, warnt der Baustein in der Konsole; Änderungs-Nachfragen, Aktualisieren-Button und Seiten-Neuladen bleiben funktionsfähig [1].
- `[[quid id='...'/]]` für frage-/verwendungs-eindeutige IDs, auch bei mehreren `ans1`-Fragen auf einer Seite [5].
- CASText `{#...#}`, `[[jsstring]]` und `[[entityescape]]` sowie die vorhandenen STACK-Zufallsfunktionen [3-5]. Moderne Browser mit `URL`, `URLSearchParams`, Promises, `async`/`await` und HTML-`template`.

Die Funktionsanforderungen auf dem Zielsystem prüfen, statt aus einer
Moodle-Versionsnummer auf vorhandene STACK-JS-Funktionen zu schließen.
Weder Sandbox-Schutz noch Moodle-Sicherheitsfilter abschalten.

## CASText und Daten

Der sichtbare Fragetext verwendet weiterhin `{@v@}` und `{@p@}` für Mathematik.
Der Baustein überträgt **nur die konkret instanziierte Funktion**, keine
Satzstruktur und keine Musterlösung. Die Arbeitsanweisung liefert der
generische Textbaustein `question_text_template` der Backend-Aufgabe
(`{funktion}`-Platzhalter); zusätzliche Bedingungen gehören in den
sichtbaren Fragetext und bei Bedarf in diesen Baustein.

Die Einbettung erfolgt ausdrücklich so:

```text
const FUNKTION = [[jsstring]]f({#v#})={#p#}[[/jsstring]];
```

`{#v#}` und `{#p#}` liefern Maxima-Rohdarstellungen, keine LaTeX-Anzeige.
`[[jsstring]]` serialisiert den **gesamten** Text mittels STACKs `json_encode`
als JavaScript-Stringliteral, einschließlich Anführungszeichen, Backslashes,
Zeilenumbrüchen und escapten Slashes. Keine zusätzlichen JS-Anführungszeichen
darum setzen. Insbesondere nicht `"{@string(p)@}"` als vermeintlich sicheres
JS-Literal verwenden. `stackjson_stringify` wurde ebenfalls im STACK-Quellcode
geprüft; für dieses einzelne CASText-Stringliteral ist die zusätzliche
Maxima-JSON-Schicht unnötig [3, 4, 7]. Die Formel wird nicht in JS ausgewertet
und nicht von Maxima- in JavaScript-Syntax umgeschrieben.

Die PRT-Antwort `{#ans1#}` steht innerhalb von `[[entityescape]]`, also als
HTML-sicherer Text im Marker, nicht in JavaScript. `get_content` liest nur den
eigenen Feedback-Container. Das gelesene HTML wird in einem **inerten lokalen
`template`** ausgewertet; `querySelectorAll` dort greift nicht auf das Moodle-DOM
zu. Es wird kein Feedback-Code ausgeführt.

`URL.searchParams.set` übernimmt das URL-Encoding genau einmal: `+` wird
`%2B`, `%` wird `%25`, `&` wird `%26`; ein Leerzeichen darf als `+` codiert
werden. Nach normalem Query-Decoding kommen die ursprünglichen Werte an.
Zusätzlich wird die erzeugte URL für HTML-Attribute und Klartext escaped.
URL-Encoding und HTML-Escaping sind unterschiedliche Schritte.

| `/start`-Parameter | Wert |
| --- | --- |
| `qid` | Konfigurierte Backend-Aufgaben-ID |
| `diagnosis` | Zugeordneter PRT-Code, sonst `unknown_error` |
| `ans1` | Aktueller Spiegelwert, nicht mathematisch normalisiert oder vorcodiert |
| `hint_level` | `1` |
| `model` | Nur bei nichtleerem `MODEL` |
| `funktion` | Instanziierte Funktion `f({#v#})={#p#}`, maximal 5000 Zeichen; das Backend setzt sie in den generischen Textbaustein ein |

## Diagnose und Timing

Beim Start wird die Eingabe synchronisiert, ein allgemeiner Link erzeugt und
einmal PRT-Feedback gelesen. Danach aktualisiert sich der Link **automatisch**:

- Jede `change`-Meldung des Sandbox-Spiegels baut den Link für den aktuellen
  Wert neu und setzt eine vorhandene Diagnose auf `unknown_error` zurück, weil
  STACK die neue Antwort noch nicht bewertet hat. Die Änderung löst **keine**
  Bewertung aus. Anschließend fragt der Baustein das Feedback **begrenzt**
  nach (zwei versetzte Abrufe, ca. 0,8 s und 3 s), um Feedback zu finden, das
  Moodle nach einem „Check“ programmatisch aktualisiert hat.
- Nach einer abgeschlossenen Eingabevalidierung („instant validation“ der
  Eingabe) übernimmt `register_validation_state_listener` die Diagnose
  automatisch: sofort plus zwei versetzte Abrufe (ca. 1,2 s und 3,5 s).
- Der Moodle-Button „Tutor-Link aktualisieren“ ist der Fallback, wird über
  STACK-JS angebunden (nicht per Inline-Handler oder direktem DOM-Zugriff),
  ist `type="button"` und löst keine Abgabe aus.
- Nach einem kompletten Neu-Render der Frage initialisiert sich der Block neu
  und liest das Feedback beim Start.

Kein Dauer-Polling: Es gibt keine `setInterval`-Schleife. Nachfragen sind an
Änderungen, Validierungsabschlüsse oder Button-Klicks gebunden, werden bei
jedem neuen Trigger neu gestartet (Debouncing) und enden von selbst.
Überlappende `get_content`-Abrufe derselben ID werden unterbunden.

Eine Diagnose wird nur übernommen, wenn genau ein Marker vorliegt, sein Code
aus 1 bis 100 Kleinbuchstaben/Ziffern/Unterstrichen besteht und sein Text
**exakt** mit der aktuellen Antwort übereinstimmt. Das Backend muss den Code
zusätzlich gegen die Aufgabe prüfen. Eine Änderung während eines laufenden
Abrufs verwirft dessen Ergebnis, auch bei anschließendem Zurückändern; der
nächste Abruf liest dann den aktuellen Stand neu.

Abrufe setzen eine bestehende Zuordnung nie selbst herab: Findet ein Abruf
keinen passenden Marker, bleibt die zuletzt übernommene Diagnose bestehen, bis
die Antwort geändert wird. Zurückgesetzt wird ausschließlich durch eine
Eingabeänderung. Das ist absichtlich konservativ: STACK kann die bewertete
Antwort anders schreiben, etwa `exp(x)` als `%e^x`, Terme umordnen oder
Leerzeichen entfernen. Auch dann bleibt `unknown_error`, selbst wenn die
Ausdrücke mathematisch gleich sind. JavaScript versucht keine
Äquivalenzprüfung. So wird eine alte Bewertung nie mit einer anderen Antwort
kombiniert. Ein erneuter Abruf darf eine vorhandene PRT-Diagnose zur exakt
gleichen Antwort übernehmen; er behauptet keine erneute Bewertung. Bei
fehlendem, widersprüchlichem, unlesbarem oder nicht passendem Feedback wird
keine Diagnose erfunden, auch kein vermeintlicher Syntaxfehler.

Die Bridge arbeitet asynchron, der Anchor ist eine Momentaufnahme: bei
Instant-Validation kann das PRT-Feedback erst nach kurzer Verzögerung
eintreffen; die versetzten Nachfragen fangen das ab. Bereits geöffnete
Tutor-Tabs werden nicht synchronisiert.

## Grenzen und Debugging

- Der normale Anchor wird mittels `switch_content` **im VLE** erzeugt, mit `target="_blank"` und `rel="noopener noreferrer"`. Kein `window.open`, kein Sandbox-Popup, kein `parent.document`. STACK/Moodle filtern das übertragene HTML. Falls die Installation `href` entfernt, steht dieselbe escaped URL unter „Linkdetails / Klartext-URL“ zur Verfügung; Sicherheitsfilter nicht umgehen [1, 7].
- Eine normale Navigation zu `/start` benötigt keine CORS-Freigabe des Tutors. STACK muss allerdings seine eigenen Sandbox-Module ausliefern können. Browserkonsole, CSP und die lokale STACK-JS-Konfiguration prüfen, wenn der Starttext stehen bleibt.
- Leere Antworten erzeugen keinen Link. Funktionen über 5000 Zeichen werden nicht abgeschnitten und nicht übertragen. `ans1` unterliegt weiterhin dem Backend-Limit `MAX_STUDENT_ANSWER_LENGTH` (standardmäßig 2000); das Snippet dupliziert diesen deploymentabhängigen Wert nicht. HTTP 422 weist unter anderem auf ungültige Parameter hin.
- GET-URLs können durch Browser, Reverse Proxy oder Webserver schon unterhalb dieser Zeichenlimits begrenzt sein; Encoding vergrößert die URL. Bei HTTP 414 die Infrastruktur/Transportform klären, nicht die Aufgabe still kürzen.
- `unknown_error` ist kein Nachweis einer falschen Antwort. Markerposition, den exakten Antworttext, die Sichtbarkeit des spezifischen Feedbacks (Review-Optionen), mehrere Marker, Rendering-Zeitpunkt und Backend-Diagnosekatalog prüfen. Bei Bridge-Timeouts erscheint eine feste Warnung ohne Schülerdaten in der Konsole; gegebenenfalls Seite neu laden.
- Linkdetails enthalten Antwort und Funktion. Keine personenbezogenen Daten oder Secrets übertragen, Links nicht öffentlich teilen. HTTPS und `noreferrer` verhindern nicht, dass die GET-URL in Browserhistorie und Server-/Proxy-Logs landet. Logging und Aufbewahrung entsprechend konfigurieren.
- Die URL ist editierbar und keine signierte STACK-Bewertung oder Authentifizierung. Backend-Validierung bleibt nötig; keine Noten oder Zugriffsrechte aus diesen Parametern ableiten.

## Randomisierte Varianten

**Backend-Verhalten:** `/start` übernimmt die optionale `funktion`
(standardmäßig maximal 5000 Zeichen) und setzt sie in den generischen
Textbaustein `question_text_template` der Aufgabe ein. Der so gebildete
Aufgabentext bleibt im Chat-Kontext gespeichert und gilt für Folgehints und
Rückfragen; ein bestehender Chat lehnt eine abweichende Funktion, Antwort oder
Diagnose ab (dafür einen neuen Tutorlink ohne `chat_id` öffnen). Alternativ
akzeptiert `/start` weiterhin einen vollständigen `question_text`; beide
Parameter zusammen werden abgewiesen. Das Snippet sendet **keine**
variantenspezifische Musterlösung.

Die Backend-Aufgaben sind generisch aufgebaut: `question_text` (allgemeine
Anweisung), der Textbaustein `question_text_template`, Lernziele, Regeln und
Diagnosetitel enthalten keine festen Zufallswerte mehr; `given_data` trägt nur
noch die Variable. Auch bei Moodle-Varianten bleiben diese Daten aktiv. Die
feste lokale Beispiel-Musterlösung (`model_solution`) ist Demodaten für lokale
Tests und wird bei Varianten niemals angehängt — auch nicht auf höheren
Hinweisstufen oder in Folgemeldungen. Vollständige Lösungen für Varianten
erfordern später eine separat verifizierte, zur Variante passende Quelle
(STACK-/Maxima-Integration) und weiterhin beide Kontext-/Hinweisstufenfreigaben.

Die Diagnose bleibt ausschließlich der PRT-Code; das LLM darf daraus keine
neue mathematische Bewertung erfinden. `hint_level=1` allein ist kein
Variantenschutz.

## Prüfung

Lokaler Smoke-/Regressionstest ab Repo-Wurzel, ohne externe Dienste oder npm:

```bash
node --test code/tests/test_moodle_snippets.js
```

Unter WSL ist hier nur die Windows-Runtime vorhanden; äquivalent:

```bash
"/mnt/c/Program Files/nodejs/node.exe" --test code/tests/test_moodle_snippets.js
```

Der Test rendert die wenigen CASText-Platzhalter als Testdoubles und führt den
extrahierten JS-Block in `node:vm` mit gemockter `stack_js`-API aus. Er prüft
Sandbox-Zugriffe, Parameter-Roundtrips, HTML-Escaping, zufällige Formeldaten,
fehlende/veraltete/verspätete Diagnosen, die automatische Aktualisierung mit
gemockten Timern und Fehlerfälle. Er ersetzt **keinen** CASText-/Maxima-Lauf
und **keinen** echten HTML-Parser-/Moodle-Filtertest. Lokal ausgeführt mit
`node.exe` v26.9.0: zwölf Tests erfolgreich.

Kein Moodle-Zugang vorhanden. Vor Freigabe auf echtem Moodle prüfen:

1. Felder speichern und STACK-Fragentests ausführen, einschließlich der bereinigten Input-Extra-Optionen. Mehrere Seeds: sichtbare Formel und decodierte `funktion` müssen dieselbe Aufgabe beschreiben; richtige Antwort/PRTs funktionieren unverändert.
2. Ohne Antwort kein Link; ohne Bewertung ein allgemeiner Link. Mit passendem PRT-Marker exakte Diagnose; bei normalisierter Schreibweise konservatives `unknown_error`. Korrekte und ungültige Antworten dürfen keinen falschen Diagnose-Marker erhalten.
3. Nach Bewertung `ans1` ändern, löschen und zurückändern. Vor erneuter Zuordnung darf keine spezifische alte Diagnose an einer anderen Antwort hängen. Änderung während verzögertem Feedback und schnelle Mehrfachklicks testen; der Link muss sich bei jeder Änderung selbstständig neu aufbauen.
4. Asynchrone Bewertung, erneute Abgabe, Moodle-Neu-Render, Navigation zurück sowie Wiederaufnahme eines Versuchs testen. Aktualisieren-Button darf keine Bewertung/Abgabe auslösen und muss nach Neu-Render wieder funktionieren.
5. Automatische Diagnoseübernahme: Mit aktivierter Instant-Validation nach „Check“ warten, ohne den Button zu nutzen — die Diagnose muss innerhalb weniger Sekunden im Link erscheinen. Mit deaktivierter Instant-Validation bleibt der Button der Weg. Browserkonsole auf die Warnung zur fehlenden Listener-API sowie auf unerwartete Dauer-Nachfragen prüfen.
6. Zwei Fragen mit jeweils `ans1` auf derselben Seite: Links, Feedback und Spiegelwerte strikt getrennt. Frage ohne passendes Input darf nicht die Antwort der Nachbarfrage lesen.
7. `+`, `%`, `&`, Anführungszeichen, Backslashes, Umlaute und Leerzeichen in Testeingaben exakt nach URL-Decoding vergleichen; testweise HTML darf weder im Tutorbereich noch im PRT-Marker ausführbar werden.
8. Anchor/HTTPS-Ziel, neuer Tab, `noopener`/`noreferrer`, Klartext-Fallback bei gefiltertem `href`, CSP, Tastaturbedienung sowie Desktop-/Mobilansicht prüfen. Getrennt lokale und Hochschuladresse testen.
9. Backend-Grenzen, Proxy-URL-Limits und Variantenschutz bis zu späteren Hinweisstufen prüfen. Keine feste Beispiel-Lösung oder fremde Variantendaten im Tutor-Kontext.

## Quellen

1. [STACK-JS: Funktionen und Sicherheitsgrenzen](https://docs.stack-assessment.org/en/Specialist_tools/STACK-JS/)
2. [Iframe-Blöcke: JavaScript-Sandbox und automatischer Import](https://docs.stack-assessment.org/en/Authoring/Question_blocks/Iframe_blocks/)
3. [CASText: Rohwerte, Anzeige und Feedback-Felder](https://docs.stack-assessment.org/en/Authoring/CASText/)
4. [Dynamic blocks: JSString- und JavaScript-Block](https://docs.stack-assessment.org/en/Authoring/Question_blocks/Dynamic_blocks/)
5. [Static blocks: QUID und Entity Escape](https://docs.stack-assessment.org/en/Authoring/Question_blocks/Static_blocks/)
6. [Bespoke validators: `validator`-/`feedback`-Input-Optionen](https://docs.stack-assessment.org/en/CAS/Validator/)
7. Öffentlicher STACK-Quellcode, geprüft bei `610fb70e37a2d04041b0c1fa07c4308b40dc5553`: [Sandbox-API](https://github.com/maths/moodle-qtype_stack/blob/610fb70e37a2d04041b0c1fa07c4308b40dc5553/corsscripts/stackjsiframe.js), [VLE-Filter und Bridge](https://github.com/maths/moodle-qtype_stack/blob/610fb70e37a2d04041b0c1fa07c4308b40dc5553/amd/src/stackjsvle.js), [JSString/JSON-Rendering](https://github.com/maths/moodle-qtype_stack/blob/610fb70e37a2d04041b0c1fa07c4308b40dc5553/stack/cas/castext2/blocks/jsstring.block.php), [Maxima-JSON](https://github.com/maths/moodle-qtype_stack/blob/610fb70e37a2d04041b0c1fa07c4308b40dc5553/stack/maxima/stackstrings.mac), [STACK-Entwicklungsgeschichte](https://docs.stack-assessment.org/en/Developer/Development_history/).
