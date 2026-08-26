# ENWEN Mental Wellness Companion

ENWEN is a web-based, non-diagnostic mental-wellness companion for Kenyan university students. The planned system combines secure mood tracking, private journaling, emotional trend visualization, approved wellness resources, and a Llama 3 conversational assistant grounded through retrieval-augmented generation (RAG).

## Project status

Initial development setup. The first implementation milestone is authentication, consent, mood tracking, and journal management before AI integration.

## Planned architecture

- Frontend: HTML, CSS, and JavaScript
- Backend API: Python and FastAPI
- Database: PostgreSQL
- AI: Llama 3 with RAG over approved wellness resources
- Testing: Pytest, integration tests, safety evaluation, and user acceptance testing

## Core modules

1. User registration, authentication, profile, and informed consent
2. Daily mood recording and emotional trend visualization
3. Private journal entry management
4. Approved wellness-resource library
5. AI wellness conversations and grounded recommendations
6. Safety screening and professional-help referral flow
7. Administration of users and approved resources

## Safety boundary

ENWEN is intended for wellness support and self-reflection. It must not diagnose mental-health conditions or replace qualified professional care. Crisis and severe-distress language must lead to a safe response and an appropriate professional-help referral.

## Repository layout

```text
backend/     FastAPI application and automated tests
frontend/    Browser-based user interface
docs/        Requirements, architecture, diagrams, and research documentation
```

## Development roadmap

- Phase 1: Repository, requirements, database design, and development environment
- Phase 2: Authentication, consent, profiles, mood tracking, and journaling
- Phase 3: Wellness resources, Llama 3, RAG, and chat persistence
- Phase 4: Safety controls, testing, evaluation, deployment, and documentation



