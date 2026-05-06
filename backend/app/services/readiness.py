"""Build the product-facing API Readiness summary (spec §4.5).

Wraps the existing score / calibration / vibe-check primitives but layers
publish blockers, evidence coverage, schema maturity, regression health,
and risky fields on top. Critically: an empty counterexample pool surfaces
as `no_production_feedback`, NOT 100% certainty.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.recompute import (
    DEFAULT_JUDGE_MODEL_VERSION,
    recompute_project_score,
    vibe_check_includes_corrected,
    vibe_check_predictions_query,
)
from app.engine.score import (
    beta_posterior,
    precision_ci_95,
    precision_point_estimate,
)
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.judge_calibration import JudgeCalibration
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.schemas.readiness import (
    APIReadinessOut,
    EvidenceCoverageOut,
    QualityEstimateOut,
    RegressionHealthOut,
    RiskyFieldOut,
    SchemaMaturityOut,
)


def _count_scalar_fields(value) -> int:
    """Count scalar (non-container) fields recursively in an entity / output blob."""
    if isinstance(value, dict):
        n = 0
        for v in value.values():
            n += _count_scalar_fields(v)
        return n
    if isinstance(value, list):
        n = 0
        for v in value:
            n += _count_scalar_fields(v)
        return n
    return 1  # leaf scalar (str/number/bool/null)


def _count_evidence_fields(evidence) -> int:
    """Count leaf entries inside per_field_evidence: { entity_idx: { field: {...} } }."""
    if not isinstance(evidence, dict):
        return 0
    n = 0
    for ent in evidence.values():
        if isinstance(ent, dict):
            n += len(ent)
    return n


async def build_readiness(
    *, project_id: int, session: AsyncSession
) -> APIReadinessOut:
    proj = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one()

    # 1. quality estimate (judge / score)
    score_result = await recompute_project_score(
        project_id=project_id, session=session, rerun=None
    )
    cal = (
        await session.execute(
            select(JudgeCalibration).where(
                JudgeCalibration.project_id == project_id,
                JudgeCalibration.judge_model_version == DEFAULT_JUDGE_MODEL_VERSION,
            )
        )
    ).scalar_one_or_none()
    tp = cal.tp if cal else 0
    fp = cal.fp if cal else 0
    obs = cal.observation_count if cal else 0
    a, b = beta_posterior(tp=tp, fp=fp)
    judge_precision = precision_point_estimate(a, b)
    ci_low, ci_high = precision_ci_95(a, b)
    quality = QualityEstimateOut(
        score=score_result.score,
        judge_component=score_result.judge_component,
        judge_precision=judge_precision,
        ci_low=ci_low,
        ci_high=ci_high,
        observation_count=obs,
        vibe_check_size=score_result.vibe_check_size,
    )

    # 2. evidence coverage from saved Annotations (role=none)
    saved_anns = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                # Dogfood #1: only Lab-side Annotations count toward the
                # editor's evidence coverage. Counterexamples (queried below)
                # come from public feedback regardless of Document.source, so
                # this filter is intentionally only on the saved-Annotation
                # leg.
                Document.source == "lab",
                Annotation.role == AnnotationRole.NONE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
                # Mirror versions.lock_status (CSE C2): exclude flag-only
                # rows whose `notes` carries `[lab_flag]={...}` — they are
                # markers, not corrections, and must not drive the
                # `lock_candidate` heuristic or the user-facing "Schema
                # ready to lock" message. SQL `NULL NOT LIKE` evaluates to
                # NULL, so notes IS NULL must be explicit.
                or_(
                    Annotation.notes.is_(None),
                    ~Annotation.notes.like("[lab_flag]=%"),
                ),
            )
        )
    ).scalars().all()
    annotated_docs = len({a.document_id for a in saved_anns})
    annotated_entities = sum(len(a.output or []) for a in saved_anns)
    annotated_fields = sum(_count_scalar_fields(a.output or []) for a in saved_anns)

    # Field-level evidence coverage from latest predictions on reviewed docs.
    field_evidence_fields = 0
    if saved_anns:
        latest_preds = (
            await session.execute(
                select(Prediction).where(
                    Prediction.document_id.in_({a.document_id for a in saved_anns})
                )
            )
        ).scalars().all()
        # Count once per document — pick latest by id.
        by_doc: dict[int, Prediction] = {}
        for p in latest_preds:
            existing = by_doc.get(p.document_id)
            if existing is None or p.id > existing.id:
                by_doc[p.document_id] = p
        for p in by_doc.values():
            field_evidence_fields += _count_evidence_fields(p.per_field_evidence)
    field_evidence_coverage_ratio = (
        field_evidence_fields / annotated_fields if annotated_fields else 0.0
    )
    evidence_coverage = EvidenceCoverageOut(
        annotated_docs=annotated_docs,
        annotated_entities=annotated_entities,
        annotated_fields=annotated_fields,
        field_evidence_fields=field_evidence_fields,
        field_evidence_coverage_ratio=field_evidence_coverage_ratio,
    )

    # 3. counterexamples / regression health
    ce_total = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.COUNTEREXAMPLE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
            )
        )
    ).scalars().all()
    ce_count = len(ce_total)
    if ce_count == 0:
        # Spec rule: never present empty pool as 100% — surface explicit signal.
        regression = RegressionHealthOut(
            counterexamples_total=0,
            counterexample_component=None,
            status="no_production_feedback",
        )
    else:
        # Without a live `rerun`, recompute returns ce_component=1.0 as fallback;
        # we re-use score_result.ce_component when available but mark status=unknown.
        regression = RegressionHealthOut(
            counterexamples_total=ce_count,
            counterexample_component=score_result.ce_component,
            status="unknown",
        )

    # 4. active version, schema, maturity, blockers
    active_v: ProjectVersion | None = None
    if proj.active_version_id is not None:
        active_v = (
            await session.execute(
                select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
            )
        ).scalar_one_or_none()

    publish_blockers: list[str] = []
    warnings: list[str] = []
    if active_v is None:
        publish_blockers.append("no_active_version")
    else:
        if not active_v.locked:
            publish_blockers.append("active_version_unlocked")
        if not active_v.schema_snapshot:
            publish_blockers.append("empty_schema")

    # Schema maturity heuristic — deliberately conservative (spec §2.3).
    maturity_status = "draft"
    if active_v is not None and active_v.locked:
        maturity_status = "locked"
    elif annotated_docs >= 5 and annotated_entities >= 20 and field_evidence_fields > 0:
        maturity_status = "lock_candidate"
    elif annotated_docs >= 3:
        maturity_status = "stabilizing"
    maturity_message = {
        "draft": "Keep reviewing — schema is still moving.",
        "stabilizing": "Schema looks stable. Review risky fields before locking.",
        "lock_candidate": "Schema ready to lock. Confirm evidence coverage first.",
        "locked": "Schema is locked.",
    }[maturity_status]
    schema_maturity = SchemaMaturityOut(
        status=maturity_status,
        annotated_docs=annotated_docs,
        annotated_entities=annotated_entities,
        # No project-wide breaking-change history yet; conservative 0.
        recent_schema_breaking_changes=0,
        message=maturity_message,
    )
    if maturity_status in ("draft", "stabilizing"):
        warnings.append("schema_still_stabilizing")
    if maturity_status == "draft":
        publish_blockers.append("schema_not_lock_candidate")

    # 5. risky fields from vibe-check predictions' per_field_confidence verdicts.
    include_corrected = await vibe_check_includes_corrected(session, project_id)
    doc_ids = (
        await session.execute(
            vibe_check_predictions_query(
                project_id, ignore_annotations=include_corrected
            )
        )
    ).scalars().all()
    risky_count: dict[str, int] = {}
    for did in doc_ids:
        latest = (
            await session.execute(
                select(Prediction)
                .where(Prediction.document_id == did)
                .order_by(Prediction.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is None:
            continue
        for ent in (latest.per_field_confidence or {}).values():
            if not isinstance(ent, dict):
                continue
            for fname, verdict in ent.items():
                if verdict in ("down", "uncertain"):
                    risky_count[fname] = risky_count.get(fname, 0) + 1
    risky_fields = [
        RiskyFieldOut(field_name=name, count=count)
        for name, count in sorted(risky_count.items(), key=lambda kv: kv[1], reverse=True)[:10]
    ]
    if risky_fields:
        warnings.append("risky_fields_present")

    # 6. additional warnings
    if ce_count == 0:
        warnings.append("no_production_feedback")
    if annotated_docs < 3 or obs < 10:
        warnings.append("low_evidence")
    if field_evidence_fields == 0 or field_evidence_coverage_ratio < 0.1:
        warnings.append("low_field_evidence")

    return APIReadinessOut(
        quality_estimate=quality,
        evidence_coverage=evidence_coverage,
        schema_maturity=schema_maturity,
        regression_health=regression,
        risky_fields=risky_fields,
        publish_blockers=publish_blockers,
        warnings=warnings,
    )
