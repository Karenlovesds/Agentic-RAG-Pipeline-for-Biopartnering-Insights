# ChromaDB Vector Database Explanation

## What is ChromaDB?

**ChromaDB** is a vector embeddings database that stores text as mathematical vectors (embeddings) for semantic search. Instead of keyword matching, it understands **meaning** and finds similar content.

## How It Works: One Complete Example

### Step 1: Storing Data

**Original Text** (from Ground Truth Excel):
```
Drug: Pembrolizumab
Brand: KEYTRUDA
Company: Merck & Co
Target: PD-1
Mechanism: Monoclonal antibody
```

**Gets Converted to:**
- **Text Chunk**: `"Drug: Pembrolizumab | Brand: KEYTRUDA | Company: Merck & Co | Target: PD-1 | Mechanism: Monoclonal antibody"`
- **Vector Embedding**: `[0.0234, -0.1234, 0.5678, ..., 0.2345]` (384 numbers)
- **Metadata**: `{source: "ground_truth", company: "Merck & Co", target: "PD-1", ...}`

**Stored in ChromaDB as:**
```
┌─────────────┬─────────────────────────────────┬──────────────┬──────────────┐
│ ID          │ Document (Text)                 │ Embedding    │ Metadata     │
├─────────────┼─────────────────────────────────┼──────────────┼──────────────┤
│ chunk_123   │ Drug: Pembrolizumab | Brand:    │ [0.023, ...] │ {source:     │
│             │ KEYTRUDA | Company: Merck & Co  │ (384 dims)   │  "ground_    │
│             │ | Target: PD-1 | Mechanism:...  │              │   truth",    │
│             │                                 │              │  company:    │
│             │                                 │              │  "Merck & Co"│
│             │                                 │              │  target:     │
│             │                                 │              │  "PD-1"}     │
└─────────────┴─────────────────────────────────┴──────────────┴──────────────┘
```

### Step 2: Searching Data

**User Query:** `"companies targeting PD-1"`

**Process:**
1. Query text → Embedding: `[0.567, -0.234, 0.891, ...]` (384 dims)
2. ChromaDB compares query embedding with all stored embeddings
3. Finds most similar chunks (cosine similarity)
4. Returns top results with relevance scores

**Result:**
```python
{
    "documents": [
        "Drug: Pembrolizumab | Brand: KEYTRUDA | Company: Merck & Co | Target: PD-1",
        "Drug: Nivolumab | Brand: OPDUALAG | Company: Bristol Myers Squibb | Target: PD-1",
        ...
    ],
    "metadatas": [
        {"source": "ground_truth", "company": "Merck & Co", "target": "PD-1"},
        {"source": "database", "company": "Bristol Myers Squibb", "target": "PD-1"},
        ...
    ],
    "distances": [0.23, 0.45, ...]  # Lower distance = more similar
}
```

### Step 3: Why It Works

✅ **Semantic Understanding**: "PD-1 inhibitor" matches "drugs targeting PD-1"  
✅ **Typo Tolerance**: "PD1" ≈ "PD-1"  
✅ **Context Aware**: Understands relationships (drug → company → target)

## Physical Storage

**File Structure** (`chroma_db/` directory, ~53MB):
```
chroma_db/
├── chroma.sqlite3              # Metadata database (32MB)
│   └── Stores IDs, metadata, collection info
│
└── [UUID folders]/
    ├── data_level0.bin        # Vector embeddings (binary)
    ├── index_metadata.pickle  # Index configuration
    └── [other index files]
```

## Summary

**ChromaDB = Specialized database for finding similar text by comparing mathematical vectors**

- All your data sources (Ground Truth, Database, FDA, Clinical Trials, Drugs.com) → converted to vectors → stored in ChromaDB
- One semantic search finds relevant information across all sources
- No SQL queries needed - pure vector similarity search
