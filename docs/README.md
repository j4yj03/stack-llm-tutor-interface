# Ordner `docs/`

Arbeits- und Forschungsdokumentation zur Masterarbeit.
Lebende Schnittstellen-/Betriebsdokumentation liegt woanders:

- Übersicht & Setup: `README.md` (Repo-Root) und `code/README.md`
- Architektur, Konventionen, Definition of Done: `AGENTS.md` (Repo-Root)
- Verzeichnisdokus: siehe README je Unterordner

## Dateien (Auswahl, chronologisch grob sortiert)

| Datei | Inhalt |
|---|---|
| `kickoff.txt`, `ssh.txt` | Ausgangsinformationen, Server-/SSH-Zugang für Recherche |
| `expose.md`, `expose/`, `expose_*.pdf` | Forschungsdesign (Exposé, deutsche/englische Fassungen) |
| `ai_tutor_stack_masterarbeit.md` | Grundlegende Konzeptsammlung zur Arbeit |
| `softwarearchitektur.md` | detaillierte Softwarearchitektur (historisch: noch Ollama-fokussiert) |
| `Infrastrukturprobleme.tex`, `vorlaufige_doku.tex` | LaTeX-Ausarbeitung der HTW-Infrastrukturproblematik (native Ollama 404, LiteLLM 401) |
| `Vorgehen bis Anfang September.md` | Arbeitsplan und Fehleranalyse bis zur Abschaltung der HTW-API |
| `llm_api_alternative_vorschlaege.md` | Alternativenvergleich für den Backend-Wechsel |
| `auswertung_kontextsteuerung.md` | Ergebnisse zur Kontextsteuerung im Prompt |
| `evaluation_protocol.md` | Protokoll der fachlichen Evaluations-Suite (`code/evaluation/`) |
| `json_schema_info.md`, `neu.md`, `neu - Kopie.md` | Schema-/Formatarbeitsentwürfe (Arbeitsnotizen) |
| `files/` | exportierte Einzelnotizen/Snippets (siehe `files/README.md`) |

## Hinweise

- Teile der Dokumentation beschreiben den **historischen** Zustand (native Ollama, LiteLLM ohne Key). Seit 15.09.2026 läuft der Betrieb produktiv über die GWDG SAIA-Plattform — siehe `AGENTS.md` (Abschnitt `app/llm/`) und `code/app/llm/README.md`.
- LaTeX-Dateien sind Rohfassungen für die Thesis; Meilenstand der Architektur immer an `AGENTS.md` abgleichen.
