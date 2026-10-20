from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _store():
    from app.db.models import LLMUsageEvent, WorkflowRun
    from app.services.run_store import RunStore

    engine = create_engine("sqlite://", poolclass=StaticPool)
    LLMUsageEvent.__table__.create(engine)
    WorkflowRun.__table__.create(engine)
    return RunStore(sessionmaker(bind=engine)())


def _event(wid, section, tokens, minutes_ago, workflow_type="proposal_generation"):
    from app.db.models import LLMUsageEvent

    return LLMUsageEvent(
        id=uuid.uuid4(), workflow_id=wid, workflow_type=workflow_type, agent="generation" if section else "supervisor",
        model="m", section_key=section, total_tokens=tokens, cost_usd=tokens / 1e6,
        created_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago),
    )


def test_usage_by_run_splits_sections_and_orders_newest_first():
    from app.db.models import WorkflowRun, WorkflowStatus

    store = _store()
    older, newer, chat = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    store.db.add(WorkflowRun(
        id=older, workflow_type="proposal_generation", status=WorkflowStatus.completed,
        payload_json={"client_name": "Chimp.ai", "title": "ThinkTree"}, result_json={},
    ))
    store.db.add_all([
        _event(older, "executive_summary", 2000, 10),
        _event(older, "solution_overview", 2500, 10),
        _event(older, None, 9000, 10),
        _event(newer, "executive_summary", 1500, 5),
        _event(newer, None, 4000, 5),
        _event(chat, None, 700, 1, workflow_type="intent_detection"),  # not a proposal run
    ])
    store.db.commit()

    runs = store.usage_by_run(days=7)["runs"]

    assert [r["workflow_id"] for r in runs] == [str(newer), str(older)]
    first, second = runs
    assert first["saved"] is False and first["client_name"] == ""
    assert first["total_tokens"] == 5500 and first["other_tokens"] == 4000
    assert second["saved"] is True and second["client_name"] == "Chimp.ai" and second["title"] == "ThinkTree"
    assert {s["section_key"]: s["total_tokens"] for s in second["sections"]} == {
        "executive_summary": 2000, "solution_overview": 2500,
    }
    assert second["other_tokens"] == 9000


def test_usage_by_run_respects_limit():
    store = _store()
    for i in range(5):
        store.db.add(_event(uuid.uuid4(), "executive_summary", 100, i))
    store.db.commit()
    assert len(store.usage_by_run(days=7, limit=3)["runs"]) == 3
