# Architecture

The system will consist of:

1. Data layer
- PostgreSQL database
- pgvector for embeddings

2. Ingestion layer
- Python scripts for data import
- future: API connectors

3. AI layer
- Ollama (local LLM)
- embedding generation
- semantic search

4. Interface layer
- future: simple web UI or CLI
