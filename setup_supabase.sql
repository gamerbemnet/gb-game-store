CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  collection TEXT NOT NULL,
  data JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection);
CREATE INDEX IF NOT EXISTS idx_documents_data ON documents USING GIN(data);
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access" ON documents FOR ALL USING (true) WITH CHECK (true);
