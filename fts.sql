CREATE VIRTUAL TABLE IF NOT EXISTS nortaxa_fts USING FTS5(namestring, tokenize="trigram", content="nortaxa", content_rowid="rowid");
DELETE FROM nortaxa_fts;
INSERT INTO nortaxa_fts (rowid, namestring) SELECT rowid, namestring FROM nortaxa;
