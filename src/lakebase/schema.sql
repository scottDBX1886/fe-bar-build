-- Dedicated operational schema. Task 11 transfers ownership to the deployed app SP.
CREATE SCHEMA IF NOT EXISTS student_retention_app;

CREATE TABLE IF NOT EXISTS student_retention_app.interventions (
  intervention_id UUID PRIMARY KEY,
  student_id TEXT NOT NULL,
  advisor_id TEXT NOT NULL,
  intervention_type TEXT NOT NULL
    CHECK (intervention_type IN ('outreach', 'academic_support', 'financial_support', 'case_review')),
  priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'in_progress', 'pending_follow_up', 'closed')),
  next_follow_up_at TIMESTAMPTZ,
  outcome TEXT,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ,
  CHECK ((status = 'closed' AND closed_at IS NOT NULL) OR
         (status <> 'closed' AND closed_at IS NULL))
);

CREATE TABLE IF NOT EXISTS student_retention_app.intervention_events (
  event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  intervention_id UUID NOT NULL
    REFERENCES student_retention_app.interventions(intervention_id),
  event_type TEXT NOT NULL
    CHECK (event_type IN ('created', 'updated', 'note_added', 'follow_up_scheduled', 'closed')),
  actor_identity TEXT NOT NULL,
  event_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  note TEXT,
  prior_status TEXT,
  new_status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  result_version INTEGER NOT NULL CHECK (result_version > 0)
);

CREATE INDEX IF NOT EXISTS interventions_student_status_idx
  ON student_retention_app.interventions (student_id, status);
CREATE INDEX IF NOT EXISTS interventions_advisor_follow_up_idx
  ON student_retention_app.interventions (advisor_id, next_follow_up_at)
  WHERE status <> 'closed';
CREATE INDEX IF NOT EXISTS intervention_events_intervention_time_idx
  ON student_retention_app.intervention_events (intervention_id, event_at, event_id);

ALTER TABLE student_retention_app.interventions REPLICA IDENTITY FULL;
ALTER TABLE student_retention_app.intervention_events REPLICA IDENTITY FULL;

CREATE OR REPLACE FUNCTION student_retention_app.reject_event_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'intervention_events is immutable';
END;
$$;

DROP TRIGGER IF EXISTS intervention_events_immutable
  ON student_retention_app.intervention_events;
CREATE TRIGGER intervention_events_immutable
BEFORE UPDATE OR DELETE ON student_retention_app.intervention_events
FOR EACH ROW EXECUTE FUNCTION student_retention_app.reject_event_mutation();

CREATE OR REPLACE FUNCTION student_retention_app.create_intervention(
  p_intervention_id UUID,
  p_student_id TEXT,
  p_advisor_id TEXT,
  p_intervention_type TEXT,
  p_priority TEXT,
  p_actor_identity TEXT,
  p_idempotency_key TEXT
)
RETURNS TABLE(result_status TEXT, intervention_id UUID, version INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
  existing_event student_retention_app.intervention_events%ROWTYPE;
BEGIN
  SELECT * INTO existing_event
  FROM student_retention_app.intervention_events
  WHERE idempotency_key = p_idempotency_key;
  IF FOUND THEN
    RETURN QUERY SELECT 'replayed'::TEXT, existing_event.intervention_id,
      existing_event.result_version;
    RETURN;
  END IF;

  INSERT INTO student_retention_app.interventions (
    intervention_id, student_id, advisor_id, intervention_type, priority,
    status, version, created_by, updated_by
  ) VALUES (
    p_intervention_id, p_student_id, p_advisor_id, p_intervention_type, p_priority,
    'open', 1, p_actor_identity, p_actor_identity
  );

  INSERT INTO student_retention_app.intervention_events (
    intervention_id, event_type, actor_identity, prior_status, new_status,
    idempotency_key, result_version
  ) VALUES (
    p_intervention_id, 'created', p_actor_identity, NULL, 'open',
    p_idempotency_key, 1
  );
  RETURN QUERY SELECT 'applied'::TEXT, p_intervention_id, 1;
END;
$$;

CREATE OR REPLACE FUNCTION student_retention_app.transition_intervention(
  p_intervention_id UUID,
  p_expected_version INTEGER,
  p_event_type TEXT,
  p_new_status TEXT,
  p_actor_identity TEXT,
  p_note TEXT,
  p_next_follow_up_at TIMESTAMPTZ,
  p_outcome TEXT,
  p_idempotency_key TEXT
)
RETURNS TABLE(result_status TEXT, intervention_id UUID, version INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
  existing_event student_retention_app.intervention_events%ROWTYPE;
  prior_status_value TEXT;
  new_version INTEGER;
  current_version INTEGER;
BEGIN
  SELECT * INTO existing_event
  FROM student_retention_app.intervention_events
  WHERE idempotency_key = p_idempotency_key;
  IF FOUND THEN
    RETURN QUERY SELECT 'replayed'::TEXT, existing_event.intervention_id,
      existing_event.result_version;
    RETURN;
  END IF;

  SELECT status INTO prior_status_value
  FROM student_retention_app.interventions
  WHERE interventions.intervention_id = p_intervention_id;

  UPDATE student_retention_app.interventions
  SET status = p_new_status,
      next_follow_up_at = p_next_follow_up_at,
      outcome = COALESCE(p_outcome, outcome),
      version = interventions.version + 1,
      updated_by = p_actor_identity,
      updated_at = now(),
      closed_at = CASE WHEN p_new_status = 'closed' THEN now() ELSE NULL END
  WHERE interventions.intervention_id = p_intervention_id
    AND interventions.version = p_expected_version
  RETURNING interventions.version INTO new_version;

  IF new_version IS NULL THEN
    SELECT interventions.version INTO current_version
    FROM student_retention_app.interventions
    WHERE interventions.intervention_id = p_intervention_id;
    RETURN QUERY SELECT 'conflict'::TEXT, p_intervention_id, current_version;
    RETURN;
  END IF;

  INSERT INTO student_retention_app.intervention_events (
    intervention_id, event_type, actor_identity, note, prior_status, new_status,
    idempotency_key, result_version
  ) VALUES (
    p_intervention_id, p_event_type, p_actor_identity, p_note,
    prior_status_value, p_new_status, p_idempotency_key, new_version
  );
  RETURN QUERY SELECT 'applied'::TEXT, p_intervention_id, new_version;
END;
$$;
