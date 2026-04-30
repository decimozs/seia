# seia: Smart Expense & Invoice Auditor

Agentic pipeline bridging unstructured document ingestion and structured enterprise accounting. Uses RAG-powered auditing to verify invoices against company policy.

## Features
- **UiPath RPA Integration**: Automated workflows for document retrieval and downstream ERP entry.
- **Unstructured Ingestion**: Process PDF invoices using `PyPDFLoader`.
- **Structured Extraction**: AI-driven data extraction via LangChain and Ollama.
- **RAG-based Auditing**: Semantic search (Qdrant) to retrieve relevant company policies for expense validation.
- **Human-in-the-Loop**: Automated escalation to manual review for policy violations.
- **FastAPI Integration**: Asynchronous processing with background tasks.

## Tech Stack
- **Framework**: [LangGraph](https://github.com/langchain-ai/langgraph)
- **LLM Engine**: [Ollama](https://ollama.com/) (running `gemini-3-flash-preview:cloud`)
- **Vector DB**: [Qdrant](https://qdrant.tech/)
- **API**: FastAPI
- **Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2`)

## Architecture
The agent follows a cyclic graph:
1. `extract`: Converts raw text to structured JSON.
2. `audit`: Retrieves policies and flags violations.
3. `human_review`: (Conditional) Manual approval if audit fails.
4. `output`: Final state export.

## Setup

### Prerequisites
- Python 3.14+
- Ollama
- Qdrant instance

### Installation
1. Install dependencies:
   ```bash
   uv sync
   ```
2. Configure `.env`:
   ```env
   QDRANT_URL=your_qdrant_url
   QDRANT_API_KEY=your_api_key
   ```

## Usage
1. Seed the policy database:
   ```bash
   python -m app.seed
   ```
2. Start the server:
   ```bash
   fastapi dev app/main.py
   ```
3. Process an invoice:
   ```bash
   curl -X POST -F "file=@invoice.pdf" http://localhost:8000/process-invoice
   ```
