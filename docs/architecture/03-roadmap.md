# Incremental Implementation Roadmap

## Phase 1 (done in this commit)
- architecture docs
- project skeleton
- domain lifecycle state machine + unit tests

## Phase 2
- DB migrations (Alembic)
- repositories and conversation service implementation
- FAQ-backed bot response flow
- session-based conversation restore APIs

## Phase 3
- realtime gateway wiring (Socket.IO)
- live agent dashboard APIs
- assignment queue + retry worker

## Phase 4
- hardening: rate limiting, observability, chaos tests for disconnect paths
- load test and scale tuning
