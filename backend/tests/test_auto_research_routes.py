import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "ar@ar.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ar@ar.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_run_creates_new_version_and_run_record(client, db_session, app):
    h, pid = await _auth_and_project(client)
    # set a baseline schema (creates active version v1)
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [
                {"name": "shop_name", "type": "string", "description": "店名"},
            ],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )

    from app.services.autoresearch.actions import EditFieldDescriptionAction
    from app.services.autoresearch.researcher import (
        DiagnosisResult,
        FakeResearcherProvider,
        ResearcherProvider,
    )

    fake = FakeResearcherProvider(
        canned=[
            DiagnosisResult(
                diagnosis="improve description",
                actions=[
                    EditFieldDescriptionAction(
                        field_name="shop_name", new_text="店名 (look near logo)"
                    )
                ],
            )
        ]
    )

    from app.api.routes.auto_research import (
        get_researcher_provider_dep,
        get_scorer_dep,
    )

    app.dependency_overrides[get_researcher_provider_dep] = lambda: fake
    app.dependency_overrides[get_scorer_dep] = lambda: (lambda schema, notes: 0.95)

    resp = await client.post(
        f"/api/v1/projects/{pid}/auto-research/run", json={"max_turn": 5}, headers=h
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["termination_reason"] == "threshold_met"
    assert body["status"] == "completed"
    assert body["output_version_id"] is not None

    # active version is NOT changed (never auto-promoted)
    active = (
        await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    ).json()
    assert active["id"] != body["output_version_id"]


@pytest.mark.asyncio
async def test_concurrent_run_returns_conflict(client, db_session, app):
    from app.models.auto_research_run import AutoResearchRun, AutoResearchStatus

    h, pid = await _auth_and_project(client)
    db_session.add(
        AutoResearchRun(
            project_id=pid,
            status=AutoResearchStatus.RUNNING.value,
            judge_model_id="m",
            researcher_model_id="m",
            turn_count=0,
            max_turn=10,
            turn_history=[],
        )
    )
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/projects/{pid}/auto-research/run", json={}, headers=h
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_runs_returns_history(client, db_session):
    h, pid = await _auth_and_project(client)
    from app.models.auto_research_run import AutoResearchRun, AutoResearchStatus

    db_session.add(
        AutoResearchRun(
            project_id=pid,
            status=AutoResearchStatus.COMPLETED.value,
            judge_model_id="m",
            researcher_model_id="m",
            turn_count=2,
            max_turn=10,
            turn_history=[{"turn": 0}],
            termination_reason="threshold_met",
        )
    )
    await db_session.commit()
    resp = await client.get(f"/api/v1/projects/{pid}/auto-research/runs", headers=h)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert rows[0]["status"] == "completed"
