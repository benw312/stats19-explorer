-- FU-055: feedback from the app's users (the pilot), kept so it can be triaged.
-- In the app schema, so the daily app backup includes it; organisation-aware like schemes.
CREATE TABLE IF NOT EXISTS app.feedback (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id      uuid NOT NULL REFERENCES app.org (id),
    kind        text NOT NULL CHECK (kind IN ('problem', 'idea', 'question', 'liked')),
    message     text NOT NULL CHECK (length(message) BETWEEN 1 AND 2000),
    url         text NOT NULL CHECK (length(url) <= 2000),
    version     text CHECK (length(version) <= 40),
    user_agent  text CHECK (length(user_agent) <= 500),
    viewport    text CHECK (length(viewport) <= 40),
    error_ref   text CHECK (error_ref ~ '^[0-9a-f]{6,12}$'),
    request_ref text,  -- the API log line of the request that saved it
    contact_ok  boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  text NOT NULL,
    status      text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'seen', 'done')),
    note        text CHECK (length(note) <= 2000)
);

CREATE INDEX IF NOT EXISTS feedback_status_idx ON app.feedback (status, created_at);

-- The API may add feedback and read it back; triage (status, note) is the owner's, via the CLI.
GRANT SELECT, INSERT ON app.feedback TO stats19_api;
