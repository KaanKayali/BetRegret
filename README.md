# BetRegret - Intelligenter Fussball-Chatbot

BetRegret ist ein Chatbot, der Fragen rund um den internationalen Fussball, Ligen, Teams und Live-Spiele beantworten kann. Das Projekt ist aus den Anforderungen des Kurses "Hands on Chatbots" entstanden.

## Idee & Projektauftrag

Die Inspiration für BetRegret kam von unserem Intresse an Fussball.

Das Ziel war eine saubere Trennung: Ein ansprechendes React-Frontend für den Benutzer, ein FastAPI-Backend für die Agentenlogik und ein abgetrennter MCP-Server als Quelle für die Informationen und Daten.

## Ablauf

Unsere Entwicklung baute schrittweise aufeinander auf:

1.  **Grundgerüst & Setup**:
    *   Initialisierung des Backends (FastAPI) und Frontends (React).
    *   Integration von LangChain und OpenAI als Sprachmodell.
2.  **Der MCP-Server (`soccer-mcp-server`)**:
    *   Entwicklung des eigenen MCP-Servers mit `FastMCP`.
    *   Implementierung der Tools (z.B. `get_league_fixtures`, `get_team_fixtures`, `get_live_match_for_team`).
3.  **Frontend-Design & UI**:
    *   Einbau von SASS/SCSS für ein modernes Styling.
    *   Erstellung von abgetrennten Komponenten (`Chatview`, `Chatfield`, `AIMessage`).
    *   Einbau von Lade-Animationen (`MessageLoader`) für ein besseres User-Feedback während die API abfragt wird.
4.  **Refactoring & Kontext-Integration (Gedächtnis)**:
    *   Umbau der Nachrichten-Logik: Anfänglich war der Bot "amnesisch" (ohne Gedächtnis).
    *   Anpassung des Backends, um Listen von Nachrichten zu akzeptieren.
    *   Anpassung des Frontends (`App.js`), sodass der gesamte Chat-Verlauf bei jedem Request mitgesendet wird.
5.  **Monitoring mit Langfuse**:
    *   Als finalen Schritt (gemäß Exercise 2) haben wir Langfuse für das Tracing integriert, um Tool-Aufrufe, Token-Verbrauch und Prompt-Verläufe genau analysieren zu können.

## Getroffene Entscheidungen & Implementierungsdetails

Wir haben uns bewusst für bestimmte Architekturen entschieden, um das System robust zu machen:

*   **Agentic RAG statt Vektordatenbank**: Bei Fussballdaten macht eine statische PDF-Vektordatenbank keinen Sinn. Der Agent nutzt stattdessen die `football-data.org` REST API als Datenquelle.

*   **Custom Parser im Frontend**: Anstatt eine schwere Markdown-Bibliothek zu laden, haben wir in der `AIMessage`-Komponente einen eigenen Parser geschrieben, der Listen und Fettdruck (`**Text**`) sauber in HTML rendert.

## Probleme & Schwierigkeiten

Auf dem Weg gab es einige technische Hürden, die wir überwinden mussten:

*   **Git Merge-Konflikte**: Bei der Zusammenführung der Frontend-Branches (z.B. bei der `postMessage`-Funktion) kam es zu Konflikten in der `App.js` und `Chatfield.jsx`, die Syntaxfehler verursachten und manuell bereinigt werden mussten.
*   **Chat-Kontext (Memory)**: LangChain speichert den Zustand nicht automatisch, wenn man über eine zustandslose API (REST) kommuniziert. Die Schwierigkeit bestand darin, die React-State-Logik so umzubauen, dass das Frontend als "Gedächtnis" fungiert und das Array asynchron korrekt ans Backend schickt.

*   **API-Wechsel**: Ursprünglich war geplant, die "API-Football" über RapidAPI zu nutzen. Es stellte sich jedoch heraus, dass diese eine kostenpflichtige Subscription voraussetzte. Wir mussten daher  auf die `football-data.org` API umsteigen. Dies erforderte eine  Anpassung der MCP-Server-Logik in der 'soccer_server.py'-Datei des Repositorys, da die Endpunkte und Datenstrukturen (z.B. Team-IDs und Match-Objekte) unterschiedlich waren.

*   **Striktes Prompt-Engineering**: Das LLM tendierte anfangs dazu, API-Fehler (wie z.B. Rate-Limits der kostenlosen Football-API) zu verschlucken oder falsche Teamnamen direkt an die Tools durchzureichen. Der System-Prompt musste stark angepasst werden, um das Modell zur Selbstkorrektur und zur Ausgabe der genutzten Tools zu zwingen.

## Setup & Installation

Um das Projekt lokal zu starten muss man:

### 1. API-Keys besorgen

Bevor du startest, benötigst du einige API-Schlüssel:
*   **OpenAI API Key**: Für das Sprachmodell (GPT).
*   **Football-Data API Key**: Für die Livedaten aus dem Fussball [football-data.org](https://www.football-data.org/).


### 2. Umgebungsvariablen (.env) konfigurieren

Navigiere in den `backend` Ordner. Falls nicht vorhanden, erstelle eine Datei namens `.env`. Trage dort die Keys so ein:

```env
OPENAI_API_KEY="openai-key"
FOOTBALL_DATA_API_KEY="football-data-key"
```

### 3. Backend starten

Öffne ein Terminal und wechsle in den `backend` Ordner:
```bash
cd backend
```
Installiere die Abhängigkeiten und starte den Server mit `uv`:
```bash
uv sync
uv run main.py
```
*Der FastAPI-Server läuft nun auf `http://127.0.0.1:8000`.*

### 4. Frontend starten

Öffne ein zweites Terminal und wechsle in den `frontend` Ordner:
```bash
cd frontend
```
Installiere die Node-Pakete und starte die React-App:
```bash
npm install
npm start
```
*Die App öffnet sich automatisch in deinem Browser unter `http://localhost:3000`.
