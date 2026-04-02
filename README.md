# CDD Rapportage Tool

Interne Streamlit-applicatie die analisten ondersteunt bij het schrijven van Customer Due Diligence (CDD) rapportages. De tool gebruikt een multi-agent architectuur via LangGraph om het Wwft-beleid strikt toe te passen op basis van een toelichting en geüploade bewijsstukken (PDF's).

## Azure Setup

### 1. Azure AI Document Intelligence

1. Ga naar de [Azure Portal](https://portal.azure.com) en maak een **Document Intelligence** resource aan (S0 tier).
2. Noteer de **Endpoint** en **Key** vanuit *Keys and Endpoint*.

### 2. Azure OpenAI Service

1. Maak een **Azure OpenAI** resource aan via [Azure AI Foundry](https://ai.azure.com).
2. Maak twee model-deployments aan:
   - **Heavy** (bijv. `gpt-4o`) — gebruikt voor Recon, Manager en Senior agents.
   - **Light** (bijv. `gpt-4o-mini`) — gebruikt voor Junior en Report agents.
3. Noteer de **Endpoint**, **API Key** en de exacte **deployment-namen**.

### 3. Environment configuratie

Kopieer `.env.example` naar `.env` en vul de waarden in:

```bash
cp .env.example .env
```

## Installatie

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Starten

```bash
streamlit run app.py
```

## Architectuur

```
Recon (heavy) → Manager (heavy) → ┬─ Junior Structuur (light)
                                   ├─ Junior Herkomst  (light)
                                   └─ Junior Vermogen  (light)
                                          ↓
                                   Senior (heavy) ──→ Report (light)
                                     ↑       │
                                     └───────┘  (feedback loop, max 3 iteraties)
```

## Projectstructuur

```
├── .env.example          # Environment template
├── requirements.txt      # Dependencies
├── app.py                # Streamlit UI
├── config.py             # Settings & LLM factory
├── doc_processor.py      # Azure Document Intelligence wrapper
├── cdd_graph.py          # LangGraph state machine
├── agents/               # Agent node functies
│   ├── recon.py
│   ├── manager.py
│   ├── juniors.py
│   ├── senior.py
│   └── report.py
└── prompts/              # System prompts met Wwft-beleid
    └── system_prompts.py
```
