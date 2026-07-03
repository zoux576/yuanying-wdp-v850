from __future__ import annotations
from pathlib import Path
from typing import Any
import os, json, uuid
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .core import *
from .docx_ops import save_anchors, source_docx_preflight, register_source_docx_media, store_embed_plan, build_docx, validate_embed_plan
from .storyboard import compose_board
from .audits import store_ppi_audit, render_structural, confirm_visual_qc, evaluate_release

BASE = Path(os.getenv('WDP_DATA_DIR', '/data')).resolve()
BASE.mkdir(parents=True, exist_ok=True)
DB = BASE / 'wdp.sqlite3'
STORAGE = BASE / 'projects'
init_db(DB)
API_KEY = os.getenv('WDP_API_KEY', 'change-me')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
app = FastAPI(title='Yuanying WDP Hard Gate API', version='8.5.0')


def auth(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, 'invalid API key')


def err(e: Exception):
    if isinstance(e, HTTPException):
        raise e
    raise HTTPException(400, str(e))


class SceneSpec(BaseModel):
    scene_id: str
    expected_formal_count: int = Field(ge=1, le=10)
    expected_storyboard_frames: int = Field(default=0, ge=0, le=12)


class CreateProject(BaseModel):
    name: str
    scenes: list[SceneSpec]


class FileUpload(BaseModel):
    openaiFileIdRefs: list[Any]


class AssetMeta(BaseModel):
    asset_id: str
    scene_id: str | None = None
    kind: str
    source_kind: str = 'UNVERIFIED'
    orig_fig_no: str | None = None
    shot_id: str | None = None
    timecode: str | None = None
    prompt_version: str | None = None


class RegisterAssets(BaseModel):
    openaiFileIdRefs: list[Any]
    assets: list[AssetMeta]


class QCBody(BaseModel):
    asset_id: str
    qc_status: str
    evidence: dict[str, Any]


class ActualAudit(BaseModel):
    delta_items: list[dict[str, Any]] = Field(default_factory=list)
    no_difference_confirmed: bool = False


class VideoPromptBody(BaseModel):
    content: str
    source_asset_ids: list[str]
    quality_evidence: dict[str, Any]


class ComposeBody(BaseModel):
    board_asset_id: str
    cols: int = Field(default=4, ge=1, le=4)
    cell_w: int = Field(default=1920, ge=1280, le=2560)
    cell_h: int = Field(default=1080, ge=720, le=1440)


class EmbedPlanBody(BaseModel):
    operations: list[dict[str, Any]]


class VisualQCBody(BaseModel):
    page_results: list[dict[str, Any]]
    note: str


@app.get('/health', operation_id='healthCheck')
def health():
    return {'ok': True, 'version': '8.5.0', 'api_key_is_default': API_KEY == 'change-me'}


@app.post('/projects', operation_id='createProject')
def create(req: CreateProject, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return {'project_id': create_project(DB, STORAGE, req.name, [s.model_dump() for s in req.scenes])}
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/source-docx', operation_id='uploadSourceDocx')
def source_docx(project_id: str, req: FileUpload, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        if len(req.openaiFileIdRefs) != 1:
            raise ValueError('exactly one DOCX required')
        ref = normalize_file_ref(req.openaiFileIdRefs[0])
        ext = safe_ext(ref.get('name', 'source.docx'), ref.get('mime_type'))
        if ext != '.docx':
            raise ValueError('source must be DOCX')
        pd = project_dir(STORAGE, project_id)
        dest = pd / 'source' / 'source.docx'
        download_ref(ref, dest)
        sha = sha256_file(dest)
        preflight = source_docx_preflight(dest)
        amap = pd / 'source' / 'anchors.json'
        rows = save_anchors(DB, project_id, dest, amap)
        baseline_media = register_source_docx_media(DB, STORAGE, project_id, dest)
        with connect(DB) as con:
            con.execute('UPDATE projects SET source_docx_path=?,source_docx_sha=?,release_status="PENDING",visual_page_qc_status="PENDING" WHERE project_id=?', (str(dest), sha, project_id))
            con.execute('DELETE FROM embed_plan WHERE project_id=?', (project_id,))
            con.execute('DELETE FROM audits WHERE project_id=?', (project_id,))
            con.execute("INSERT INTO audits VALUES(?,?,?,?,?,?)", (project_id,'SOURCE_PREFLIGHT',preflight['status'],str(amap),json.dumps(preflight,ensure_ascii=False),now_iso()))
        return {'source_sha': sha, 'source_preflight': preflight, 'anchors': len(rows), 'baseline_media_registered': len(baseline_media), 'anchor_map': str(amap), 'semantic_anchor_summary': [{'anchor_id': a['anchor_id'], 'scene_id': a['scene_id'], 'semantic_tag': a['semantic_tag'], 'text': a['exact_text'][:120]} for a in rows]}
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/assets', operation_id='registerAssets')
def register_assets(project_id: str, req: RegisterAssets, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        if len(req.openaiFileIdRefs) != len(req.assets):
            raise ValueError('files and asset metadata counts differ')
        if not req.assets or len(req.assets) > 10:
            raise ValueError('one to ten files required per action call')
        out = []
        for ref, meta_obj in zip(req.openaiFileIdRefs, req.assets):
            meta = meta_obj.model_dump()
            r = normalize_file_ref(ref)
            ext = safe_ext(r.get('name', 'asset'), r.get('mime_type'))
            tmp = project_dir(STORAGE, project_id) / 'assets' / ('_incoming_' + uuid.uuid4().hex + ext)
            info = download_ref(r, tmp)
            out.append(register_asset_file(DB, STORAGE, project_id, meta, tmp, info['name'], info['mime_type']))
            tmp.unlink(missing_ok=True)
        return {'registered': out, 'note': 'permissions remain off until structured QC passes'}
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/assets/qc', operation_id='recordAssetQC')
def asset_qc(project_id: str, req: QCBody, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return record_qc(DB, project_id, req.asset_id, req.qc_status, req.evidence)
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/scenes/{scene_id}/formal-gate', operation_id='evaluateFormalGate')
def formal_gate(project_id: str, scene_id: str, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return evaluate_formal_gate(DB, project_id, scene_id)
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/scenes/{scene_id}/actual-image-audit', operation_id='recordActualImageAudit')
def actual_audit(project_id: str, scene_id: str, req: ActualAudit, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return record_actual_image_audit(DB, project_id, scene_id, req.delta_items, req.no_difference_confirmed)
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/scenes/{scene_id}/video-prompt', operation_id='registerFinalVideoPrompt')
def video_prompt(project_id: str, scene_id: str, req: VideoPromptBody, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return register_video_prompt(DB, project_id, scene_id, req.content, req.source_asset_ids, req.quality_evidence)
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/scenes/{scene_id}/storyboard/compose', operation_id='composeStoryboard')
def compose(project_id: str, scene_id: str, req: ComposeBody, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return compose_board(DB, STORAGE, project_id, scene_id, req.board_asset_id, req.cols, req.cell_w, req.cell_h)
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/scenes/{scene_id}/storyboard-gate', operation_id='evaluateStoryboardGate')
def sb_gate(project_id: str, scene_id: str, board_asset_id: str, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return evaluate_storyboard_gate(DB, project_id, scene_id, board_asset_id)
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/embed-plan', operation_id='setEmbedPlan')
def embed_plan(project_id: str, req: EmbedPlanBody, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        store_embed_plan(DB, project_id, req.operations)
        return {'operations': len(req.operations), 'status': 'VALID', 'note': 'completeness is rechecked before build'}
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/build-preview', operation_id='buildDocxPreview')
def build_preview(project_id: str, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        with connect(DB) as con:
            p = con.execute('SELECT * FROM projects WHERE project_id=?', (project_id,)).fetchone()
            scenes = [dict(r) for r in con.execute('SELECT * FROM scenes WHERE project_id=? ORDER BY scene_id', (project_id,))]
            ops = [dict(r) for r in con.execute('SELECT * FROM embed_plan WHERE project_id=? ORDER BY op_order', (project_id,))]
        if not p or not p['source_docx_path']:
            raise ValueError('source DOCX missing')
        with connect(DB) as con:
            source_audit = con.execute("SELECT status,payload_json FROM audits WHERE project_id=? AND audit_type='SOURCE_PREFLIGHT'", (project_id,)).fetchone()
        if not source_audit or source_audit['status'] != 'PASS':
            details = json.loads(source_audit['payload_json']) if source_audit else {}
            raise ValueError('source DOCX preflight blocked: ' + json.dumps(details, ensure_ascii=False))
        failures = []
        for s in scenes:
            try:
                current_formal_gate(DB, project_id, s['scene_id'])
                current_actual_audit(DB, project_id, s['scene_id'])
                current_video_prompt(DB, project_id, s['scene_id'])
                sb = latest_receipt(DB, project_id, s['scene_id'], 'STORYBOARD_GATE')
                if not sb or sb['status'] != 'PASS':
                    raise ValueError('storyboard gate not PASS')
            except Exception as e:
                failures.append(f"{s['scene_id']}: {e}")
        if failures:
            raise ValueError('prebuild hard gate failed: ' + '; '.join(failures))
        validate_embed_plan(DB, project_id, ops, require_complete=True)
        pd = project_dir(STORAGE, project_id)
        out = pd / 'output' / f'{project_id}_PREVIEW.docx'
        build_docx(DB, project_id, Path(p['source_docx_path']), out)
        ppi = store_ppi_audit(DB, project_id, out, pd / 'reports' / 'ppi.json')
        render = render_structural(DB, project_id, out, pd / 'render', 300)
        pdf = Path(render['pdfs'][0]) if render.get('pdfs') else None
        response = {'docx_path': str(out), 'ppi_pass': ppi['pass'], 'render_pass': render['pass'], 'page_count': render.get('page_count'), 'visual_page_qc_required': True, 'ppi_errors': ppi.get('errors', []), 'render_errors': render.get('errors', [])}
        if pdf and pdf.exists() and pdf.stat().st_size <= 9_000_000:
            response.update(file_response(pdf))
        elif pdf:
            response['preview_pdf_path'] = str(pdf)
        return response
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/visual-page-qc', operation_id='confirmVisualPageQC')
def visual_qc(project_id: str, req: VisualQCBody, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return confirm_visual_qc(DB, project_id, req.page_results, req.note)
    except Exception as e:
        err(e)


@app.post('/projects/{project_id}/release', operation_id='evaluateAndRelease')
def release(project_id: str, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        result = evaluate_release(DB, project_id)
        if result['status'] != 'RELEASED':
            return result
        with connect(DB) as con:
            p = con.execute('SELECT * FROM projects WHERE project_id=?', (project_id,)).fetchone()
        out = Path(p['output_docx_path'])
        final = out.with_name(out.name.replace('_PREVIEW', '_FINAL'))
        final.write_bytes(out.read_bytes())
        with connect(DB) as con:
            con.execute('UPDATE projects SET output_docx_path=? WHERE project_id=?', (str(final), project_id))
        public = None
        if PUBLIC_BASE_URL:
            public = f"{PUBLIC_BASE_URL}/downloads/{project_id}/{final.name}?token={p['download_token']}"
        result.update(file_response(final, public))
        return result
    except Exception as e:
        err(e)


@app.get('/projects/{project_id}', operation_id='getProjectState')
def get_state(project_id: str, x_api_key: str | None = Header(None)):
    auth(x_api_key)
    try:
        return project_state(DB, project_id)
    except Exception as e:
        err(e)


@app.get('/downloads/{project_id}/{filename}')
def download(project_id: str, filename: str, token: str = Query(...)):
    with connect(DB) as con:
        pinfo = con.execute('SELECT download_token FROM projects WHERE project_id=?', (project_id,)).fetchone()
    if not pinfo or token != pinfo['download_token']:
        raise HTTPException(403, 'invalid download token')
    p = project_dir(STORAGE, project_id) / 'output' / Path(filename).name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', filename=p.name)
