"""Perception API: methods, analyses (derived), human annotations (user_generated), evaluation,
pair matching and benchmarks."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import select

from mars_explorer.api import schemas
from mars_explorer.api.deps import SessionDep
from mars_explorer.core.errors import InvalidRequestError, NotFoundError
from mars_explorer.core.provenance import Provenance
from mars_explorer.db.models import Annotation, ImageRecord, VisionAnalysis
from mars_explorer.ingest.cameras import CATALOG
from mars_explorer.vision.methods import METHODS
from mars_explorer.vision.pathsketch import ASSUMPTIONS, LIMITATIONS, SketchParams, png_data_url
from mars_explorer.vision.service import VisionService, summarize

router = APIRouter(tags=["vision"])

EVALUATION_CAVEATS = [
    "Precision/recall assume you marked every rock you consider relevant in the analysed region.",
    "Human annotation is interpretation, not ground truth confirmed by the mission.",
]


def _vision(request: Request) -> VisionService:
    return request.app.state.vision


def _analysis_out(record: VisionAnalysis) -> schemas.VisionAnalysisOut:
    spec = METHODS[record.method]
    return schemas.VisionAnalysisOut.model_validate(
        {
            "id": record.id,
            "image_id": record.image_id,
            "method": record.method,
            "title": spec.title,
            "method_kind": spec.kind,
            "provenance": Provenance.DERIVED,
            "rendition": record.rendition,
            "params": record.params,
            "algorithm_version": record.algorithm_version,
            "width": record.width,
            "height": record.height,
            "timings_ms": record.timings_ms,
            "stats": record.stats,
            "detections": record.detections,
            "layers": [
                {**layer, "url": f"/api/vision/analyses/{record.id}/layers/{layer['name']}.png"}
                for layer in record.layers
            ],
            "score_definition": spec.score_definition,
            "limitations": list(spec.limitations),
            "created_at": record.created_at,
        }
    )


def _annotation_out(note: Annotation) -> schemas.AnnotationOut:
    return schemas.AnnotationOut.model_validate(
        {**note.model_dump(), "provenance": Provenance.USER_GENERATED}
    )


@router.get("/vision/methods", response_model=list[schemas.VisionMethod])
def list_methods() -> list[schemas.VisionMethod]:
    return [
        schemas.VisionMethod(
            name=spec.name,
            title=spec.title,
            category=spec.category,
            kind=spec.kind,
            summary=spec.summary,
            params=[
                schemas.ParamSpecOut(
                    name=p.name,
                    label=p.label,
                    type=p.type,
                    default=p.default,
                    help=p.help,
                    min=p.min,
                    max=p.max,
                    step=p.step,
                    choices=list(p.choices),
                )
                for p in spec.params
            ],
            limitations=list(spec.limitations),
            score_definition=spec.score_definition,
            experimental=spec.experimental,
            produces_detections=spec.category == "detection",
        )
        for spec in METHODS.values()
    ]


@router.post("/vision/analyses", response_model=schemas.VisionAnalysisOut)
def create_analysis(request: Request, body: schemas.AnalysisRequest) -> schemas.VisionAnalysisOut:
    record = _vision(request).analyze(body.image_id, body.method, body.params, body.rendition)
    return _analysis_out(record)


@router.get("/vision/analyses/{analysis_id}", response_model=schemas.VisionAnalysisOut)
def get_analysis(request: Request, analysis_id: str) -> schemas.VisionAnalysisOut:
    return _analysis_out(_vision(request).get(analysis_id))


@router.get(
    "/vision/analyses/{analysis_id}/layers/{layer}.png",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_layer(request: Request, analysis_id: str, layer: str) -> FileResponse:
    path = _vision(request).layer_path(analysis_id, layer)
    if not path.is_file():
        raise NotFoundError(
            f"No layer {layer!r} for analysis {analysis_id!r}", code="layer_not_found"
        )
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )


@router.get("/vision/analyses/{analysis_id}/evaluation", response_model=schemas.EvaluationOut)
def evaluate(request: Request, analysis_id: str) -> schemas.EvaluationOut:
    result = _vision(request).evaluate(analysis_id)
    counts = result.counts
    return schemas.EvaluationOut(
        analysis_id=result.analysis_id,
        annotations=result.annotations,
        detections=counts.true_positives + counts.false_positives,
        true_positives=counts.true_positives,
        false_positives=counts.false_positives,
        false_negatives=counts.false_negatives,
        precision=counts.precision,
        recall=counts.recall,
        f1=counts.f1,
        tolerance_px=result.tolerance_px,
        matching="one-to-one, closest first; a pair matches within "
        "max(candidate radius, tolerance)",
        caveats=EVALUATION_CAVEATS,
    )


@router.get("/images/{image_id}/annotations", response_model=list[schemas.AnnotationOut])
def list_annotations(session: SessionDep, image_id: str) -> list[schemas.AnnotationOut]:
    notes = session.exec(
        select(Annotation).where(Annotation.image_id == image_id).order_by(Annotation.id)  # type: ignore[arg-type]
    ).all()
    return [_annotation_out(n) for n in notes]


@router.post(
    "/images/{image_id}/annotations", response_model=schemas.AnnotationOut, status_code=201
)
def add_annotation(
    session: SessionDep, image_id: str, body: schemas.AnnotationIn
) -> schemas.AnnotationOut:
    if session.get(ImageRecord, image_id) is None:
        raise NotFoundError(f"No ingested image with id {image_id!r}", code="image_not_found")
    note = Annotation(image_id=image_id, x=body.x, y=body.y, label=body.label)
    session.add(note)
    session.commit()
    session.refresh(note)
    return _annotation_out(note)


@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_annotation(session: SessionDep, annotation_id: int) -> Response:
    note = session.get(Annotation, annotation_id)
    if note is None:
        raise NotFoundError(f"No annotation {annotation_id}", code="annotation_not_found")
    session.delete(note)
    session.commit()
    return Response(status_code=204)


@router.post("/vision/match", response_model=schemas.MatchOut)
def match(request: Request, body: schemas.MatchRequest) -> schemas.MatchOut:
    result = _vision(request).match(body.image_a, body.image_b, body.rendition)
    notes = [
        "Matches: ORB descriptors, Lowe ratio test, RANSAC fundamental matrix (epipolar geometry).",
        "Disparity is in image pixels (B − A). Converting to distance needs camera models and the "
        "stereo baseline, which this analysis does not use.",
    ]
    if not result.stereo_pair:
        notes.append("Not a verified stereo pair: offsets mix viewpoint change and scene change.")
    return schemas.MatchOut(
        image_a=result.image_a,
        image_b=result.image_b,
        stereo_pair=result.stereo_pair,
        width_a=result.width_a,
        height_a=result.height_a,
        width_b=result.width_b,
        height_b=result.height_b,
        keypoints_a=result.keypoints_a,
        keypoints_b=result.keypoints_b,
        tentative=result.tentative,
        inliers=result.inliers,
        inlier_ratio=round(result.inliers / result.tentative, 3) if result.tentative else None,
        disparity=result.disparity,
        matches=[schemas.DrawnMatch.model_validate(m) for m in result.drawn],
        elapsed_ms=result.elapsed_ms,
        provenance=Provenance.DERIVED,
        notes=notes,
    )


@router.post("/vision/benchmark", response_model=schemas.BenchmarkOut)
def benchmark(request: Request, body: schemas.BenchmarkRequest) -> schemas.BenchmarkOut:
    unknown = sorted(set(body.cameras) - set(CATALOG))
    if unknown:
        raise InvalidRequestError(f"Unknown instrument(s): {', '.join(unknown)}")
    report = _vision(request).benchmark(body.cameras, body.limit)
    methods = []
    for bench in report.methods:
        counts = bench.counts
        methods.append(
            schemas.MethodBenchmarkOut(
                method=bench.method,
                title=METHODS[bench.method].title,
                images=len(bench.runtimes_ms),
                runtime_ms=summarize(bench.runtimes_ms),  # type: ignore[arg-type]
                candidates=summarize([float(c) for c in bench.candidates]),  # type: ignore[arg-type]
                annotated_images=bench.annotated_images,
                true_positives=counts.true_positives,
                false_positives=counts.false_positives,
                false_negatives=counts.false_negatives,
                precision=counts.precision,
                recall=counts.recall,
                f1=counts.f1,
            )
        )
    return schemas.BenchmarkOut(
        images=len(report.images),
        cameras=report.cameras,
        methods=methods,
        agreement_f1=summarize(report.agreement),  # type: ignore[arg-type]
        notes=[
            "Default parameters; images already cached locally (large rendition); no downloads.",
            "Runtime measured on this machine, single thread, excluding image decoding.",
            "Agreement = F1 between the two detectors' candidates (how often they point at the "
            "same places), not accuracy.",
            "Precision/recall only over images you annotated.",
        ],
    )


@router.post("/vision/path-sketch", response_model=schemas.PathSketchOut)
def path_sketch(request: Request, body: schemas.PathSketchRequest) -> schemas.PathSketchOut:
    """Image-space route around rock candidates: an illustration, never a drivable route."""
    params = SketchParams(
        detector=body.detector,
        clearance=body.clearance,
        roughness_weight=body.roughness_weight,
        horizon=body.horizon,
    )
    start = (body.start.x, body.start.y) if body.start else None
    sketch = _vision(request).path_sketch(
        body.image_id, (body.goal.x, body.goal.y), start, params, body.rendition
    )
    rows, cols = sketch.grid_shape
    detour = (
        round((sketch.length_px / sketch.straight_px - 1) * 100, 1)
        if sketch.found and sketch.straight_px
        else None
    )
    return schemas.PathSketchOut(
        image_id=body.image_id,
        width=sketch.width,
        height=sketch.height,
        found=sketch.found,
        reason=sketch.reason,
        path=[[round(x, 1), round(y, 1)] for x, y in sketch.path],
        start=[round(v, 1) for v in sketch.start],
        goal=[round(v, 1) for v in sketch.goal],
        horizon=sketch.horizon,
        horizon_auto=sketch.horizon_auto,
        detector=body.detector,
        obstacles=[
            schemas.SketchObstacle(x=round(c.x, 1), y=round(c.y, 1), r=round(c.r, 1))
            for c in sketch.obstacles
        ],
        cost_layer=png_data_url(sketch.cost_png),
        metrics=schemas.PathSketchMetrics(
            length_px=round(sketch.length_px, 1),
            straight_px=round(sketch.straight_px, 1),
            detour_pct=detour,
            min_clearance_px=None
            if sketch.min_clearance_px is None
            else round(sketch.min_clearance_px, 1),
            obstacles=len(sketch.obstacles),
            blocking_straight_line=sketch.blocking_straight,
            grid=[rows, cols],
            cell_px=round(sketch.cell_px, 2),
            elapsed_ms=round(sketch.elapsed_ms, 1),
        ),
        explanation=sketch.explanation,
        assumptions=ASSUMPTIONS,
        limitations=LIMITATIONS,
        provenance=Provenance.DERIVED,
    )
