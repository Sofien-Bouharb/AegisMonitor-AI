-- P24: Persist AI analyses and associated human feedback.

CREATE TABLE ai_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis TEXT NOT NULL CHECK (length(trim(analysis)) > 0),
    context JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ai_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL
        REFERENCES ai_analyses(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL
        CHECK (verdict IN ('helpful', 'not_helpful', 'correct', 'incorrect')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_feedback_analysis_created_at
    ON ai_feedback (analysis_id, created_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('002_ai_feedback');
