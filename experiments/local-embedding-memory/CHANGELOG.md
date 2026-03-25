# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-22

### Added

- **Web UI Interface** (`web_ui.py`)
  - Browser-based semantic search interface
  - Real-time search results with similarity scores
  - Visual comparison of semantic vs text search
  - Port configuration support (`--port` option)

- **Interactive Demo** (`interactive_demo.py`)
  - Command-line interface for semantic search
  - Real-time query and response
  - Compare semantic vs text search side-by-side

- **Core Memory Embedder** (`memory_embedder.py`)
  - Semantic chunking by Markdown headers (##, ###)
  - Incremental indexing with content hashing
  - Cosine similarity-based search
  - Support for multiple memory files (MEMORY.md + memory/*.md)
  - Local embeddings using sentence-transformers (no API required)

- **Documentation**
  - Complete README with quick start guide
  - Comprehensive TUTORIAL.md (19KB)
  - Full API reference in API.md (12KB)
  - Installation and usage examples

### Features

- **Incremental Indexing**: Only reindexes changed files
- **Semantic Search**: Understands query meaning, not just keywords
- **Local Processing**: No external API calls required
- **Fast Performance**: Lightweight 80MB model runs on CPU
- **Multiple Interfaces**: CLI, Web UI, and programmatic API

### Technical Details

- **Model**: sentence-transformers (all-MiniLM-L6-v2)
- **Vector Store**: JSON-based local storage
- **Chunking Strategy**: Header-based semantic chunking
- **Similarity Metric**: Cosine similarity
- **Supported Files**: MEMORY.md, memory/*.md

## [0.9.0] - 2026-03-21

### Added

- Initial semantic search implementation
- Basic embedding generation
- Simple chunking strategy
- Core search functionality

### Changed

- Improved chunking algorithm
- Enhanced search relevance

## [0.1.0] - 2026-03-19

### Added

- Project initialization
- Basic project structure
- Initial concept development

---

## Roadmap

### [1.1.0] - Planned

- **Performance Improvements**
  - Batch processing for large memory sets
  - Caching layer for frequent queries
  - Async indexing support

- **Enhanced Features**
  - Date range filtering
  - Tag-based search
  - Custom chunking strategies
  - Export search results

### [1.2.0] - Planned

- **Advanced Search**
  - Hybrid search (semantic + keyword)
  - Faceted search by metadata
  - Search suggestions
  - Query history

- **Integration**
  - OpenClaw CLI integration
  - REST API server
  - Webhook support

### [2.0.0] - Future

- **Architecture**
  - Vector database support (ChromaDB, Qdrant)
  - Distributed indexing
  - Real-time index updates

- **AI Features**
  - Automatic summarization
  - Memory deduplication
  - Smart memory linking

---

## Upgrade Guide

### From 0.9.0 to 1.0.0

1. **New Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Reindex Required**
   ```bash
   python memory_embedder.py --index
   ```
   The new version uses an improved chunking strategy.

3. **Web UI Available**
   ```bash
   python web_ui.py --port 8080
   ```

### From 0.1.0 to 0.9.0

1. **Complete Reinstall**
   ```bash
   pip install sentence-transformers numpy --upgrade
   ```

2. **Delete Old Index**
   ```bash
   rm memory/.embedding_index.json
   ```

3. **Fresh Index**
   ```bash
   python memory_embedder.py --index
   ```

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 1.0.0 | 2026-03-22 | Web UI, interactive demo, full documentation |
| 0.9.0 | 2026-03-21 | Semantic search, incremental indexing |
| 0.1.0 | 2026-03-19 | Project initialization |

---

## Contributing

See [DOCUMENTATION-GUIDE.md](../../DOCUMENTATION-GUIDE.md) for guidelines on maintaining this changelog.

---

*Last updated: 2026-03-26*
*Maintainer: OpenClaw Workspace Team*
