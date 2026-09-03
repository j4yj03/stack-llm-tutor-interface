# Moodle-Integration des KI-Tutors

## Überblick

Die Integration des KI-Tutors in Moodle erfolgt über drei Komponenten, die zusammenarbeiten:

1. **PRT feedback.html** – Überträgt die Diagnose vom STACK-Evaluationsergebnis
2. **questiontext.js** – Erstellt dynamisch den Link zum KI-Tutor
3. **variables.txt** – Definiert Maxima-Variablen und URL-Encoding

```
┌─────────────────────────────────────────────────────────────────┐
│                        Moodle STACK Frage                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌──────────────────┐                    │
│  │ variables.txt   │    │ questiontext.js  │                    │
│  │ (Maxima-Vars)   │───▶│ (Link-Builder)   │───▶ KI-Tutor      │
│  └─────────────────┘    └──────────────────┘     Server         │
│                                ▲                                │
│                                │                                │
│                       ┌─────────────────┐                       │
│                       │ PRT feedback.html│                       │
│                       │ (Diagnose-Code) │                       │
│                       └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

## Datei 1: PRT feedback.html

**Pfad:** `code/moodle/PRT feedback.html`

### Zweck

Enthält den **Diagnose-Code**, der vonSTACKs Potential Response Trees (PRT) generiert wird und beschreibt, welchen Fehler der Schüler gemacht hat.

### Aufbau

```html
<p><span class="ai-tutor-diagnosis" style="display: none;"
    data-diagnosis="missing_chain_rule_inner_derivative"> </span></p>
<p>Die innere Ableitung der Kettenregel fehlt.</p>
```

### Funktionsweise

| Element | Beschreibung |
|---------|--------------|
| `.ai-tutor-diagnosis` | CSS-Klasse zum Identifizieren des Diagnose-Elements |
| `data-diagnosis` | Attribut mit dem Diagnose-Code (z.B. `missing_chain_rule_inner_derivative`) |
| `style="display: none;"` | Element ist unsichtbar (nur für JavaScript) |
| Zweiter `<p>` | Sichtbare Feedback-Nachricht für den Schüler |

### Diagnose-Codes

Jeder PRT-Ergebniswert kann einen eigenen Diagnose-Code haben:

- `missing_chain_rule_inner_derivative` – Innere Ableitung fehlt
- `wrong_product_rule_application` – Falsche Produktregel-Anwendung
- `syntax_error` – Syntaxfehler in der Eingabe
- `unknown_error` – Unbekannter Fehler (Fallback)

## Datei 2: questiontext.js

**Pfad:** `code/moodle/questiontext.js`

### Zweck

Dynamisches JavaScript, das den **Link zum KI-Tutor** basierend auf aktueller Eingabe und Diagnose erstellt.

### Aufbau

```html
<!-- Frage mit Eingabefeld -->
<p>\(\large f'({@v@})=\,\) [[input:ans1]] [[validation:ans1]]</p>

<!-- KI-Tutor Box -->
<div style="margin-top: 1em; padding: 0.8em; border: 1px solid #ccc; background: #f7f7f7;">
  <strong>KI-Tutor:</strong><br>
  <a id="ai-tutor-dynamic-link" target="_blank" href="#">
     AI Tutor öffnen
  </a>
  <div id="ai-tutor-link-debug" style="margin-top: 0.5em; font-size: 0.85em; color: #666;">
    Link wird erzeugt ...
  </div>
</div>

<!-- PRT Feedback Bereich -->
<div id="stack-prt-feedback-area">
  [[feedback:Result]]
</div>

<script>
// JavaScript Code zum Erstellen des dynamischen Links
</script>
```

### Kernkomponenten

#### Konstanten

```javascript
const BASE_URL = "http://127.0.0.1:8000/start";
const QID = "ableitung_kettenregel_exp_001";
const DEFAULT_DIAGNOSIS = "unknown_error";
```

#### Hauptfunktion: `updateTutorLink()`

```javascript
function updateTutorLink() {
    const input = findAns1Input();          // Eingabefeld finden
    const answer = input.value || "";       // Aktuelle Antwort lesen
    const encodedAnswer = encodeURIComponent(answer);  // URL-encodieren
    const diagnosis = findDiagnosisCode();  // Diagnose aus HTML lesen

    // URL zusammenbauen
    const url = BASE_URL
        + "?qid=" + encodeURIComponent(QID)
        + "&diagnosis=" + encodeURIComponent(diagnosis)
        + "&ans1=" + encodedAnswer
        + "&hint_level=1";

    link.href = url;  // Link aktualisieren
}
```

#### DOM-Traversal Funktionen

```javascript
// Eingabefeld finden
function findAns1Input() {
    return document.querySelector(
        'input[name*="ans1"], textarea[name*="ans1"]'
    );
}

// Diagnose-Code aus PRT feedback lesen
function findDiagnosisCode() {
    const diagnosisElement = document.querySelector(".ai-tutor-diagnosis");
    if (!diagnosisElement) {
        return DEFAULT_DIAGNOSIS;
    }
    const code = diagnosisElement.getAttribute("data-diagnosis")
              || diagnosisElement.textContent
              || DEFAULT_DIAGNOSIS;
    return code.trim() || DEFAULT_DIAGNOSIS;
}
```

#### Event-Listener

```javascript
// Bei DOM-Laden: Input-Listener setzen und initialen Link erstellen
document.addEventListener("DOMContentLoaded", function () {
    const input = findAns1Input();
    if (input) {
        input.addEventListener("input", updateTutorLink);  // Bei jeder Eingabe
    }
    updateTutorLink();

    // MutationObserver für PRT-Feedback-Änderungen
    const feedbackArea = document.getElementById("stack-prt-feedback-area");
    if (feedbackArea) {
        const observer = new MutationObserver(function () {
            updateTutorLink();
        });
        observer.observe(feedbackArea, {
            childList: true, subtree: true, characterData: true, attributes: true
        });
    }
});
```

### URL-Parameter

| Parameter | Beschreibung | Beispiel |
|-----------|--------------|----------|
| `qid` | Question ID (Aufgaben-Identifier) | `ableitung_kettenregel_exp_001` |
| `diagnosis` | Diagnose-Code vom PRT | `missing_chain_rule_inner_derivative` |
| `ans1` | URL-encodierte Schülerantwort | `2*x*sin(x)%2Bx%5E2*cos(x)` |
| `hint_level` | Start-Hinweis-Stufe (immer 1) | `1` |

## Datei 3: variables.txt

**Pfad:** `code/moodle/variables.txt`

### Zweck

Definiert **Maxima-Variablen** für die STACK-Frage und eine **URL-Encoding-Funktion**.

### Aufbau

```maxima
v:x;                          /* Ableitungsvariable */
rdm:-1-rand(9);               /* Zufallszahl -1 bis -9 */
rdm2: rand_with_prohib(-9,9,[0]);  /* Zufallszahl -9 bis 9, ohne 0 */
pp:v^-rdm+rdm*exp(v);        /* Funktionsteil */
p:rdm2*exp(pp);               /* Vollständige Funktion */

/* URL-Encoding Funktion */
urlencode_basic(s) := block([r],
  r : string(s),
  r : ssubst("%25", "%", r),
  /* ... weitere Ersetzungen ... */
  url:r
)$

validate_listlength(ex) := block([l],
  urlencode_basic(ex),
  ""
);
```

### Variablen-Beschreibung

| Variable | Beschreibung |
|----------|--------------|
| `v` | Ableitungsvariable (z.B. `x`) |
| `rdm` | Zufallszahl für Exponenten |
| `rdm2` | Zufallszahl für Koeffizienten |
| `pp` | Innerer Funktionsteil |
| `p` | Vollständige Funktion `f(x)` |

### URL-Encoding Funktion

`urlencode_basic()` konvertiert Sonderzeichen in URL-safe Format:

| Zeichen | Encoding | Verwendung |
|---------|----------|------------|
| `%` | `%25` | Prozentsymbol |
| ` ` | `%20` | Leerzeichen |
| `+` | `%2B` | Pluszeichen |
| `^` | `%5E` | Potenz |
| `(` | `%28` | Klammer auf |
| `)` | `%29` | Klammer zu |
| `*` | `%2A` | Multiplikation |
| `,` | `%2C` | Komma |

## Ablauf der Integration

```
1. Schüler gibt Antwort ein
         │
         ▼
2. STACK evaluiert Antwort (PRT)
         │
         ▼
3. PRT generiert Diagnose-Code
   └─▶ PRT feedback.html: data-diagnosis="missing_chain_rule_inner_derivative"
         │
         ▼
4. JavaScript erstellt dynamischen Link
   └─▶ questiontext.js: updateTutorLink()
         │
         ▼
5. Schüler klickt auf "AI Tutor öffnen"
         │
         ▼
6. Browser öffnet KI-Tutor mit URL-Parametern
   └─▶ /start?qid=...&diagnosis=...&ans1=...&hint_level=1
         │
         ▼
7. KI-Tutor-Server verarbeitet Anfrage
   └─▶ Lädt Aufgabe, baut Prompt, ruft LLM auf
         │
         ▼
8. Schüler erhält adaptiven Hinweis
```

## Konfiguration für neue Aufgaben

### Schritt 1: PRT feedback.html anpassen

```html
<p><span class="ai-tutor-diagnosis" style="display: none;"
    data-diagnosis="DEIN_DIAGNOSE_CODE"> </span></p>
<p>Deine Feedback-Nachricht hier.</p>
```

### Schritt 2: questiontext.js anpassen

```javascript
const QID = "deine_aufgaben_id";  // Muss mit task-JSON übereinstimmen
```

### Schritt 3: variables.txt anpassen

```maxima
/* Neue Variablen für deine Aufgabe */
deine_variable: wert;
```

## Sicherheits-Hinweise

- **URL-Encoding** ist essenziell, um Sonderzeichen in der Antwort sicher zu übertragen
- **Diagnose-Codes** sollten keine sensiblen Informationen enthalten
- **JavaScript** wird clientseitig ausgeführt – keine Geheimnisse im Code speichern
- **CORS** muss am KI-Tutor-Server für Moodle-Domäne konfiguriert werden

## Debugging

Die `questiontext.js` enthält einen **Debug-Bereich** (`ai-tutor-link-debug`), der zeigt:

- Aktuelle Diagnose
- Aktuelle Antwort
- Generierter Link

Bei Problemen:
1. Browser-Konsole prüfen
2. Prüfen ob `.ai-tutor-diagnosis` Element vorhanden ist
3. Prüfen ob `ans1`-Eingabefeld existiert
4. URL im Debug-Bereich überprüfen