CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    number INTEGER NOT NULL UNIQUE CHECK (number BETWEEN 1 AND 120),
    title TEXT NOT NULL,
    source_file TEXT NOT NULL,
    original_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter_cards (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    plot_chain JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_events JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_characters JSONB NOT NULL DEFAULT '[]'::jsonb,
    foreshadowing JSONB NOT NULL DEFAULT '[]'::jsonb,
    later_association_relation_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    quotable_fact_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieval_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    understanding_focus JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_card JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    generated_at TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    brief TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'name',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, alias)
);

CREATE TABLE IF NOT EXISTS relations (
    id TEXT PRIMARY KEY,
    subject_entity_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_entity_id TEXT NOT NULL,
    chapters JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance TEXT NOT NULL DEFAULT 'curated',
    confidence TEXT NOT NULL DEFAULT 'explicit',
    description TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    chapter_id TEXT REFERENCES chapters(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL,
    location TEXT,
    quote TEXT,
    evidence_text TEXT NOT NULL,
    entity_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    relation_id TEXT,
    confidence TEXT NOT NULL,
    provenance TEXT NOT NULL,
    derived_from_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter_annotations (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset INTEGER NOT NULL CHECK (end_offset > start_offset),
    surface_text TEXT NOT NULL,
    annotation_type TEXT NOT NULL,
    entity_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
    relation_id TEXT REFERENCES relations(id) ON DELETE SET NULL,
    evidence_id TEXT REFERENCES evidence(id) ON DELETE SET NULL,
    display_priority INTEGER NOT NULL DEFAULT 100,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trace_items (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    relation_id TEXT REFERENCES relations(id) ON DELETE SET NULL,
    evidence_id TEXT REFERENCES evidence(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    trace_type TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    importance INTEGER NOT NULL DEFAULT 50,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    model TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chapter_cards_chapter ON chapter_cards(chapter_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias ON entity_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_relations_subject ON relations(subject_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_object ON relations(object_entity_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chapter ON evidence(chapter_id);
CREATE INDEX IF NOT EXISTS idx_chapter_annotations_chapter ON chapter_annotations(chapter_id, start_offset);
CREATE INDEX IF NOT EXISTS idx_chapter_annotations_entity ON chapter_annotations(entity_id);
CREATE INDEX IF NOT EXISTS idx_trace_items_entity ON trace_items(entity_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_trace_items_chapter ON trace_items(chapter_id);
