# Ordner `docs/`

**Status: Dokumentationswegweiser, 2026-10-02.** Der aktuelle empirische Entwurf
steht in [eval-protocol-2](evaluation_protocol.md). Er beginnt ohne PRT mit
kontrollierten synthetischen Aufgabenantworten und untersucht Kontext,
Diagnosehypothesen, Tutorregeln, Generierung, Startstufen und Skriptadaptation.
Eine Referenzhypothese ist keine bereits verifizierte STACK-Bewertung.

## Aktueller Einstieg

- [Evaluationsprotokoll](evaluation_protocol.md): Bloecke A-D, Baseline-/Held-out-Auswahl, Aussagegrenzen, reale versus Demoausgaben und optionaler Zweitmodell-Judge.
- [Kontextsteuerung](auswertung_kontextsteuerung.md): aktueller technischer Abgleich, konfigurierbare Regeln, beobachtete statt rekonstruierte Prompts.
- [Architektur](softwarearchitektur.md): aktueller Nachtrag vor dem unveraenderten historischen Architekturentwurf.
- [Literaturnotizen](literatur/literatur.md): zwei lokal gesichtete Kapitel, korrigierte PDF-Pagination und Grenzen der Uebertragung.
- [Setup](../code/README.md), [App](../code/app/README.md), [Evaluation](../code/evaluation/README.md) und [Moodle-Snippets](../code/moodle/README.md): Bedienung und Implementierungsdetails. Alte Protokoll-/Presetangaben dort nicht automatisch als neue Studienbedingungen behandeln.

Die Serverdefaults bleiben Start 1, `fixed`, `provided`, `tutor`, `text` und
Adaptation aus, bis eine andere Bedingung explizit gewaehlt wird. Welche Regeln
spaeter im Betrieb verwendet werden, ist empirisch zu begruenden. Fuer einzelne
Laeufe aktive Policy, Serverkonfiguration/hash und tatsaechliche Prompts sichern;
ein Repo-Text oder lokaler Preview ist kein Deploymentnachweis.

Der integrierte Stand verwendet angeforderte API-Optionen auch fuer die
Stufe-0-Startwahl und dieselbe beim Start geladene Policy fuer Generierung,
Health und Konfigurations-GET; Aenderungen brauchen einen Neustart, keinen
GET-Hot-Swap. Die Notebookvorbereitung nutzt `eval-protocol-2`. Judgeversion
`judge-rubric-1.0-v2` erhaelt getrennte Hypothesen-/Folgeturn-Evidenz und aktive
Regelschalter; Modellratings bleiben je Bedingung/Turn getrennt.
Die gemeinsame Startbaseline ist noch manuell nach vorab festzulegenden Pilotkriterien
und Belegen auszuwählen, nicht als bereits optimiert anzusehen.

## Historische Unterlagen

| Datei | Einordnung und aktueller Nachtrag |
|---|---|
| [expose.md](expose.md) | Markdown-Vorversion; datierte Aenderung des Untersuchungsumfangs vor dem Originaltext |
| [expose/README.md](expose/README.md) | Versionsindex der unveraenderten Expose-PDFs und LaTeX-Quelle |
| [ai_tutor_stack_masterarbeit.md](ai_tutor_stack_masterarbeit.md) | Fruehe Konzept-/Forschungsfragen; kein Nachweis einer lokalen Lernstudie |
| [Vorgehen bis Anfang September.md](Vorgehen%20bis%20Anfang%20September.md) | HTW-Infrastrukturnotiz, historische Endpunktbefunde und deren Grenzen |
| [llm_api_alternative_vorschlaege.md](llm_api_alternative_vorschlaege.md) | Historischer Backendvergleich; Nachtrag zur aktuellen `LLM_*`-Abstraktion und Governance |
| [json_schema_info.md](json_schema_info.md) | Archivierter Schemaentwurf; Nachtrag zum getrennten Task-/Caseformat und `evaluation_examples` |
| [neu.md](neu.md), [neu - Kopie.md](neu%20-%20Kopie.md) | Fruehe Erlaeuterungsentwuerfe, keine zweite aktuelle App-/Schemainstruktion |
| [files/README.md](files/README.md) | Quellenindex der Einzelnotizen; Beispieltexte sind keine beobachteten Modellantworten |

`Infrastrukturprobleme.tex`, `vorlaufige_doku.tex`, `expose_3*.pdf` und die PDFs
unter `expose/` bleiben wissenschaftliche bzw. historische Arbeitsartefakte.
Ihre Inhalte werden nicht rueckwirkend auf den aktuellen Stand umgeschrieben.
`kickoff.txt` und `ssh.txt` sind Arbeitsmaterialien, keine oeffentlichen
Betriebsanleitungen; vor Weitergabe auf Zugangs-/Personeninformationen pruefen.

## Nachweise und Grenzen

Der aktuelle Defaultbackend ist GWDG SAIA, mit lokalem Ollama als austauschbarem
Fallback. Dies beschreibt die Konfiguration, keine erneute Live-Verifikation
des Dienstes, der Modellgewichte oder einer produktiven Deploymentfreigabe.
Historische `OLLAMA_*`-/HTW-Konfigurationen nicht als aktuelle Anleitung ausfuehren.

Die 15 Task-Beispiele und der aeltere 12-Faelle-Korpus bleiben getrennte
synthetische Quellen mit offener Evidenz. Offline-Tests sind technische
Nachweise; ausgewaehlte Live-Ausgaben, Expertenratings und Ergebnisse der
Versuchsblöcke muessen erst tatsaechlich erhoben werden. Skriptzeit plus
Verwirrung prueft eine Entscheidung bei der naechsten Nachricht, nicht einen
autonomen Timer oder einen Lerneffekt.
Das reale Intervall wird monoton seit erfolgreicher Antwort nur innerhalb
desselben Serverprozesses mit passender Uhridentitaet gemessen; bei Neustart
oder anderem Worker bleibt es unbekannt. Leerlauf ist keine aktive Lernzeit.
Authentifizierte Skriptintervalle von hoechstens 86400 Sekunden sind Simulation,
keine gemessene studentische Bearbeitungszeit.

Institutioneller Betrieb und TLS beweisen keine Datenschutzkonformitaet.
GET-Antwortdaten, Logs, SQLite, Laufartefakte, Exports und ein optionaler Judge
sind in einem eigenen Zugriffs-, Aufbewahrungs- und Verarbeitungsplan zu erfassen;
Details im [Governance-Abschnitt](evaluation_protocol.md#9-governance-und-aussagegrenzen).
