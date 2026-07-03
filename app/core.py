from __future__ import annotations
from pathlib import Path
from typing import Any
import base64, hashlib, json, re, sqlite3, time, uuid
import requests
from PIL import Image

PASS_FORMAL = {"IMG-PASS", "IMG-PASS-WITH-FIX"}
PASS_SB = {"SB-PASS", "SB-PASS-WITH-FIX"}
FORMAL_SOURCE_KINDS = {"DALL_E_GENERATED", "API_GENERATED", "USER_UPLOADED", "MANUAL_APPROVED", "INDEPENDENT_GENERATION"}
STORYBOARD_SOURCE_KINDS = {"DALL_E_GENERATED", "API_GENERATED", "USER_UPLOADED", "MANUAL_APPROVED", "INDEPENDENT_GENERATION"}
ASSET_KINDS = {"FORMAL_IMAGE", "STORYBOARD_FRAME", "STORYBOARD_BOARD", "CONCEPT", "PROMPT_CARD", "DOCUMENT", "RENDER_PAGE", "EXTRA"}
SLOT_KIND_MAP = {"FORMAL_SLOT": "FORMAL_IMAGE", "STORYBOARD_SLOT": "STORYBOARD_BOARD", "CONCEPT_APPENDIX": "CONCEPT"}
BANNED_FORMAL_SOURCE_KINDS = {"PROMPT_CARD", "CONCEPT_COMPOSITE", "CONTACT_SHEET", "PAGE_SCREENSHOT", "RENDER_CROP", "PLACEHOLDER", "UNVERIFIED", "PROGRAMMATIC"}
SUSPICIOUS_NAME_RE = re.compile(r"(prompt.?card|contact.?sheet|screenshot|page[-_ ]?\d+|thumbnail|render.?crop|overview|总览|提示卡|占位)", re.I)
DRAFT_PROMPT_RE = re.compile(r"PRECOMPILED-DRAFT|TEMP-MANUAL-PREVIS|ASSET-PRECOMPILED|待正式图|未获得实际图", re.I)
REQUIRED_FORMAL_EVIDENCE = [
    "identity_match", "costume_match", "weapon_match", "handedness_match",
    "scene_match", "time_light_match", "action_or_role_match", "aspect_ratio_match",
    "no_placeholder", "no_page_ui", "no_duplicate_body", "resolution_pass", "source_proof"
]
REQUIRED_SB_EVIDENCE = [
    "identity_match", "scene_match", "shot_match", "continuity_match", "cinematic_frame",
    "not_reused_crop", "no_placeholder", "no_page_ui", "resolution_pass"
]
REQUIRED_VIDEO_EVIDENCE = [
    "references_actual_assets", "actual_image_delta_applied", "character_equipment_synced",
    "scene_light_synced", "timeline_complete", "entry_exit_complete", "camera_sound_complete",
    "platform_char_limit_pass", "not_draft"
]
REQUIRED_PAGE_QC = [
    "no_wrong_asset", "no_cropping", "no_overlap", "text_legible",
    "storyboard_readable", "section_order_correct", "header_footer_ok"
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_json_hash(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = """
    CREATE TABLE IF NOT EXISTS projects(
      project_id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL,
      created_at TEXT NOT NULL, source_docx_path TEXT, source_docx_sha TEXT,
      anchor_map_path TEXT, output_docx_path TEXT, preview_pdf_path TEXT,
      render_dir TEXT, visual_page_qc_status TEXT DEFAULT 'PENDING',
      release_status TEXT DEFAULT 'PENDING', download_token TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS scenes(
      project_id TEXT NOT NULL, scene_id TEXT NOT NULL, expected_formal_count INTEGER NOT NULL,
      expected_storyboard_frames INTEGER DEFAULT 0,
      formal_gate_status TEXT DEFAULT 'PENDING', actual_image_audit_status TEXT DEFAULT 'PENDING',
      video_prompt_status TEXT DEFAULT 'PENDING', storyboard_gate_status TEXT DEFAULT 'PENDING',
      checkpoint_status TEXT DEFAULT 'PENDING',
      PRIMARY KEY(project_id, scene_id), FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS assets(
      project_id TEXT NOT NULL, asset_id TEXT NOT NULL, scene_id TEXT, kind TEXT NOT NULL,
      source_kind TEXT NOT NULL DEFAULT 'UNVERIFIED', qc_status TEXT NOT NULL DEFAULT 'GENERATED',
      file_path TEXT NOT NULL, sha256 TEXT NOT NULL, width INTEGER, height INTEGER,
      mime_type TEXT, original_name TEXT, orig_fig_no TEXT, shot_id TEXT, timecode TEXT,
      prompt_version TEXT, allowed_for_embed INTEGER NOT NULL DEFAULT 0,
      allowed_for_recompile INTEGER NOT NULL DEFAULT 0, allowed_for_board INTEGER NOT NULL DEFAULT 0,
      evidence_json TEXT DEFAULT '{}', flags_json TEXT DEFAULT '[]', created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY(project_id, asset_id), UNIQUE(project_id, sha256),
      FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS receipts(
      project_id TEXT NOT NULL, scene_id TEXT, receipt_type TEXT NOT NULL, status TEXT NOT NULL,
      version INTEGER NOT NULL, input_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL, PRIMARY KEY(project_id, scene_id, receipt_type, version)
    );
    CREATE TABLE IF NOT EXISTS actual_image_audits(
      project_id TEXT NOT NULL, scene_id TEXT NOT NULL, status TEXT NOT NULL,
      no_difference_confirmed INTEGER NOT NULL, delta_json TEXT NOT NULL,
      receipt_version INTEGER NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(project_id, scene_id)
    );
    CREATE TABLE IF NOT EXISTS video_prompts(
      project_id TEXT NOT NULL, scene_id TEXT NOT NULL, version INTEGER NOT NULL,
      status TEXT NOT NULL, content TEXT NOT NULL, char_count INTEGER NOT NULL,
      source_asset_ids_json TEXT NOT NULL, quality_evidence_json TEXT NOT NULL,
      content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(project_id, scene_id, version)
    );
    CREATE TABLE IF NOT EXISTS anchors(
      project_id TEXT NOT NULL, anchor_id TEXT NOT NULL, container_type TEXT NOT NULL,
      container_path TEXT NOT NULL, scene_id TEXT, semantic_tag TEXT,
      exact_text TEXT, text_hash TEXT NOT NULL, heading_path_json TEXT NOT NULL,
      source_docx_sha TEXT NOT NULL, PRIMARY KEY(project_id, anchor_id)
    );
    CREATE TABLE IF NOT EXISTS embed_plan(
      project_id TEXT NOT NULL, op_order INTEGER NOT NULL, anchor_id TEXT NOT NULL,
      op_type TEXT NOT NULL, asset_id TEXT, scene_id TEXT, slot_kind TEXT,
      insert_relation TEXT NOT NULL, orientation TEXT NOT NULL, width_cm REAL,
      caption TEXT, title TEXT, page_break_before INTEGER DEFAULT 0,
      page_break_after INTEGER DEFAULT 0, text_content TEXT,
      PRIMARY KEY(project_id, op_order)
    );
    CREATE TABLE IF NOT EXISTS audits(
      project_id TEXT NOT NULL, audit_type TEXT NOT NULL, status TEXT NOT NULL,
      report_path TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(project_id, audit_type)
    );
    CREATE TRIGGER IF NOT EXISTS trg_embed_asset_must_be_allowed
    BEFORE INSERT ON embed_plan
    WHEN NEW.op_type='IMAGE'
    BEGIN
      SELECT CASE WHEN COALESCE((SELECT allowed_for_embed FROM assets WHERE project_id=NEW.project_id AND asset_id=NEW.asset_id),0)<>1
        THEN RAISE(ABORT,'asset not allowed_for_embed') END;
    END;
    CREATE TRIGGER IF NOT EXISTS trg_formal_slot_kind
    BEFORE INSERT ON embed_plan
    WHEN NEW.op_type='IMAGE' AND NEW.slot_kind='FORMAL_SLOT'
    BEGIN
      SELECT CASE WHEN COALESCE((SELECT kind FROM assets WHERE project_id=NEW.project_id AND asset_id=NEW.asset_id),'')<>'FORMAL_IMAGE'
        THEN RAISE(ABORT,'FORMAL_SLOT requires FORMAL_IMAGE') END;
    END;
    CREATE TRIGGER IF NOT EXISTS trg_storyboard_slot_kind
    BEFORE INSERT ON embed_plan
    WHEN NEW.op_type='IMAGE' AND NEW.slot_kind='STORYBOARD_SLOT'
    BEGIN
      SELECT CASE WHEN COALESCE((SELECT kind FROM assets WHERE project_id=NEW.project_id AND asset_id=NEW.asset_id),'')<>'STORYBOARD_BOARD'
        THEN RAISE(ABORT,'STORYBOARD_SLOT requires STORYBOARD_BOARD') END;
    END;
    """
    with connect(db_path) as con:
        con.executescript(schema)


def project_dir(storage_root: Path, project_id: str) -> Path:
    p = storage_root / project_id
    p.mkdir(parents=True, exist_ok=True)
    for sub in ["assets", "source", "boards", "output", "render", "reports", "archive"]:
        (p / sub).mkdir(exist_ok=True)
    return p


def _require_project(con: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = con.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
    if not row:
        raise KeyError(f"project not found: {project_id}")
    return row


def _require_scene(con: sqlite3.Connection, project_id: str, scene_id: str) -> sqlite3.Row:
    row = con.execute("SELECT * FROM scenes WHERE project_id=? AND scene_id=?", (project_id, scene_id)).fetchone()
    if not row:
        raise KeyError(f"scene not found: {scene_id}")
    return row


def create_project(db_path: Path, storage_root: Path, name: str, scenes: list[dict[str, Any]]) -> str:
    if not name.strip():
        raise ValueError("project name required")
    scene_ids = [str(s["scene_id"]).strip() for s in scenes]
    if not scene_ids or len(scene_ids) != len(set(scene_ids)):
        raise ValueError("scenes must be non-empty with unique scene_id")
    project_id = "prj_" + uuid.uuid4().hex[:16]
    project_dir(storage_root, project_id)
    with connect(db_path) as con:
        con.execute("INSERT INTO projects(project_id,name,status,created_at,download_token) VALUES(?,?,?,?,?)",
                    (project_id, name.strip(), "ACTIVE", now_iso(), uuid.uuid4().hex))
        for s in scenes:
            expected = int(s["expected_formal_count"])
            sb = int(s.get("expected_storyboard_frames", 0))
            if not (1 <= expected <= 10):
                raise ValueError("expected_formal_count must be 1..10")
            if not (0 <= sb <= 12):
                raise ValueError("expected_storyboard_frames must be 0..12")
            con.execute("INSERT INTO scenes(project_id,scene_id,expected_formal_count,expected_storyboard_frames) VALUES(?,?,?,?)",
                        (project_id, str(s["scene_id"]).strip(), expected, sb))
    return project_id


def normalize_file_ref(ref: Any) -> dict[str, Any]:
    if isinstance(ref, dict):
        return ref
    raise ValueError("openaiFileIdRefs runtime item must be an object with download_link")


def safe_ext(name: str, mime: str | None) -> str:
    ext = Path(name).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".docx", ".pdf"}:
        return ext
    return {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/pdf": ".pdf"}.get(mime or "", ".bin")


def download_ref(ref: Any, dest: Path, max_bytes: int = 80_000_000) -> dict[str, Any]:
    r = normalize_file_ref(ref)
    url = r.get("download_link")
    if not url:
        raise ValueError("file ref missing download_link")
    with requests.get(url, timeout=35, stream=True) as resp:
        resp.raise_for_status()
        length = int(resp.headers.get("content-length", "0") or 0)
        if length and length > max_bytes:
            raise ValueError(f"file too large: {length} bytes")
        total = 0
        with dest.open("wb") as f:
            for chunk in resp.iter_content(1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("file exceeds size limit")
                f.write(chunk)
    return {"name": r.get("name", dest.name), "id": r.get("id"), "mime_type": r.get("mime_type"), "bytes": total}


def inspect_image(path: Path) -> tuple[int, int, str, str]:
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        return im.width, im.height, im.mode, (im.format or "").upper()


def shutil_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        import shutil
        shutil.copy2(src, dst)


def _asset_id_valid(scene_id: str | None, kind: str, asset_id: str) -> bool:
    if kind == "FORMAL_IMAGE" and scene_id:
        return bool(re.fullmatch(re.escape(scene_id) + r"-IMG-\d{2}", asset_id))
    if kind == "STORYBOARD_FRAME" and scene_id:
        return bool(re.fullmatch(re.escape(scene_id) + r"-SB-F\d{2}", asset_id))
    if kind == "STORYBOARD_BOARD" and scene_id:
        return bool(re.fullmatch(re.escape(scene_id) + r"-SB-(?:\d{2}|[A-Z])", asset_id))
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", asset_id))


def invalidate_document(db_path: Path, project_id: str, reason: str) -> None:
    with connect(db_path) as con:
        _require_project(con, project_id)
        con.execute("DELETE FROM audits WHERE project_id=? AND audit_type IN ('PPI_MEDIA','RENDER_STRUCTURAL','VISUAL_PAGE_QC')", (project_id,))
        con.execute("UPDATE projects SET output_docx_path=NULL,preview_pdf_path=NULL,render_dir=NULL,visual_page_qc_status='PENDING',release_status='PENDING' WHERE project_id=?", (project_id,))
        v = next_receipt_version(con, project_id, None, "DOCUMENT_INVALIDATED")
        payload = {"reason": reason, "at": now_iso()}
        con.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)", (project_id, None, "DOCUMENT_INVALIDATED", "OUTDATED", v, stable_json_hash(payload), json.dumps(payload, ensure_ascii=False), now_iso()))


def invalidate_scene(db_path: Path, project_id: str, scene_id: str, level: str, reason: str) -> None:
    with connect(db_path) as con:
        _require_scene(con, project_id, scene_id)
        if level == "FORMAL":
            con.execute("UPDATE scenes SET formal_gate_status='PENDING',actual_image_audit_status='PENDING',video_prompt_status='PENDING',storyboard_gate_status='PENDING',checkpoint_status='PENDING' WHERE project_id=? AND scene_id=?", (project_id, scene_id))
            con.execute("UPDATE assets SET qc_status='OUTDATED',allowed_for_embed=0,allowed_for_recompile=0,allowed_for_board=0,updated_at=? WHERE project_id=? AND scene_id=? AND kind IN ('STORYBOARD_FRAME','STORYBOARD_BOARD')", (now_iso(), project_id, scene_id))
        elif level == "VIDEO":
            con.execute("UPDATE scenes SET video_prompt_status='PENDING',storyboard_gate_status='PENDING',checkpoint_status='PENDING' WHERE project_id=? AND scene_id=?", (project_id, scene_id))
            con.execute("UPDATE assets SET qc_status='OUTDATED',allowed_for_embed=0,allowed_for_board=0,updated_at=? WHERE project_id=? AND scene_id=? AND kind IN ('STORYBOARD_FRAME','STORYBOARD_BOARD')", (now_iso(), project_id, scene_id))
        elif level == "STORYBOARD":
            con.execute("UPDATE scenes SET storyboard_gate_status='PENDING',checkpoint_status='PENDING' WHERE project_id=? AND scene_id=?", (project_id, scene_id))
        else:
            raise ValueError(f"unknown invalidation level: {level}")
        v = next_receipt_version(con, project_id, scene_id, "INVALIDATION")
        payload = {"level": level, "reason": reason, "at": now_iso()}
        con.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)", (project_id, scene_id, "INVALIDATION", "OUTDATED", v, stable_json_hash(payload), json.dumps(payload, ensure_ascii=False), now_iso()))
    invalidate_document(db_path, project_id, f"{scene_id}/{level}: {reason}")


def register_asset_file(db_path: Path, storage_root: Path, project_id: str, meta: dict[str, Any], source_path: Path,
                        original_name: str | None = None, mime_type: str | None = None) -> dict[str, Any]:
    kind = meta.get("kind", "EXTRA")
    if kind not in ASSET_KINDS:
        raise ValueError(f"invalid kind: {kind}")
    asset_id = str(meta["asset_id"]).strip()
    scene_id = meta.get("scene_id")
    source_kind = meta.get("source_kind", "UNVERIFIED")
    with connect(db_path) as con:
        _require_project(con, project_id)
        if kind in {"FORMAL_IMAGE", "STORYBOARD_FRAME", "STORYBOARD_BOARD"}:
            if not scene_id:
                raise ValueError(f"{kind} requires scene_id")
            _require_scene(con, project_id, scene_id)
    if not _asset_id_valid(scene_id, kind, asset_id):
        raise ValueError(f"invalid asset_id for kind/scene: {asset_id}")
    if kind == "FORMAL_IMAGE" and source_kind in BANNED_FORMAL_SOURCE_KINDS:
        raise ValueError(f"formal image source_kind blocked: {source_kind}")
    if kind == "STORYBOARD_FRAME" and source_kind not in STORYBOARD_SOURCE_KINDS:
        raise ValueError(f"storyboard frame source_kind blocked: {source_kind}")
    pd = project_dir(storage_root, project_id)
    ext = source_path.suffix.lower() or safe_ext(original_name or "", mime_type)
    if kind in {"FORMAL_IMAGE", "STORYBOARD_FRAME", "STORYBOARD_BOARD", "CONCEPT", "PROMPT_CARD"} and ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("image asset must be PNG/JPEG/WEBP")
    width = height = None
    flags: list[str] = []
    image_format = None
    if kind in {"FORMAL_IMAGE", "STORYBOARD_FRAME", "STORYBOARD_BOARD", "CONCEPT", "PROMPT_CARD"}:
        width, height, _, image_format = inspect_image(source_path)
        if SUSPICIOUS_NAME_RE.search((original_name or "") + " " + source_path.name):
            flags.append("SUSPECT_SOURCE_NAME")
        if width < 1024 or height < 576:
            flags.append("LOW_RESOLUTION")
        if image_format not in {"PNG", "JPEG", "WEBP"}:
            flags.append("UNEXPECTED_IMAGE_FORMAT")
    sha = sha256_file(source_path)
    with connect(db_path) as con:
        same_sha = con.execute("SELECT asset_id FROM assets WHERE project_id=? AND sha256=?", (project_id, sha)).fetchone()
        if same_sha and same_sha["asset_id"] != asset_id:
            raise ValueError(f"duplicate file hash already registered as {same_sha['asset_id']}")
        old = con.execute("SELECT * FROM assets WHERE project_id=? AND asset_id=?", (project_id, asset_id)).fetchone()
    dest = pd / ("boards" if kind == "STORYBOARD_BOARD" else "assets") / f"{asset_id}{ext}"
    if old and Path(old["file_path"]).exists() and old["sha256"] != sha:
        archive = pd / "archive" / f"{asset_id}_{old['sha256'][:10]}{Path(old['file_path']).suffix}"
        shutil_copy(Path(old["file_path"]), archive)
    shutil_copy(source_path, dest)
    ts = now_iso()
    with connect(db_path) as con:
        if old:
            con.execute("""UPDATE assets SET scene_id=?,kind=?,source_kind=?,qc_status='GENERATED',file_path=?,sha256=?,width=?,height=?,mime_type=?,original_name=?,orig_fig_no=?,shot_id=?,timecode=?,prompt_version=?,allowed_for_embed=0,allowed_for_recompile=0,allowed_for_board=0,evidence_json='{}',flags_json=?,updated_at=? WHERE project_id=? AND asset_id=?""",
                        (scene_id, kind, source_kind, str(dest), sha, width, height, mime_type, original_name, meta.get("orig_fig_no"), meta.get("shot_id"), meta.get("timecode"), meta.get("prompt_version"), json.dumps(flags, ensure_ascii=False), ts, project_id, asset_id))
        else:
            con.execute("""INSERT INTO assets(project_id,asset_id,scene_id,kind,source_kind,qc_status,file_path,sha256,width,height,mime_type,original_name,orig_fig_no,shot_id,timecode,prompt_version,allowed_for_embed,allowed_for_recompile,allowed_for_board,evidence_json,flags_json,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,'{}',?,?,?)""",
                        (project_id, asset_id, scene_id, kind, source_kind, "GENERATED", str(dest), sha, width, height, mime_type, original_name, meta.get("orig_fig_no"), meta.get("shot_id"), meta.get("timecode"), meta.get("prompt_version"), json.dumps(flags, ensure_ascii=False), ts, ts))
    if kind == "FORMAL_IMAGE":
        invalidate_scene(db_path, project_id, scene_id, "FORMAL", f"formal asset registered/replaced: {asset_id}")
    elif kind in {"STORYBOARD_FRAME", "STORYBOARD_BOARD"}:
        invalidate_scene(db_path, project_id, scene_id, "STORYBOARD", f"storyboard asset registered/replaced: {asset_id}")
    else:
        invalidate_document(db_path, project_id, f"asset registered/replaced: {asset_id}")
    return get_asset(db_path, project_id, asset_id)


def get_asset(db_path: Path, project_id: str, asset_id: str) -> dict[str, Any]:
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM assets WHERE project_id=? AND asset_id=?", (project_id, asset_id)).fetchone()
    if not row:
        raise KeyError(asset_id)
    d = dict(row)
    d["evidence"] = json.loads(d.pop("evidence_json") or "{}")
    d["flags"] = json.loads(d.pop("flags_json") or "[]")
    return d


def list_assets(db_path: Path, project_id: str, scene_id: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    q = "SELECT * FROM assets WHERE project_id=?"
    params: list[Any] = [project_id]
    if scene_id is not None:
        q += " AND scene_id=?"
        params.append(scene_id)
    if kind is not None:
        q += " AND kind=?"
        params.append(kind)
    q += " ORDER BY asset_id"
    with connect(db_path) as con:
        rows = con.execute(q, params).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["evidence"] = json.loads(d.pop("evidence_json") or "{}")
        d["flags"] = json.loads(d.pop("flags_json") or "[]")
        out.append(d)
    return out


def record_qc(db_path: Path, project_id: str, asset_id: str, qc_status: str, evidence: dict[str, Any]) -> dict[str, Any]:
    asset = get_asset(db_path, project_id, asset_id)
    kind = asset["kind"]
    merged = dict(asset.get("evidence") or {})
    merged.update(evidence or {})
    allow_embed = allow_recompile = allow_board = 0
    if kind == "FORMAL_IMAGE":
        if qc_status in PASS_FORMAL:
            missing = [k for k in REQUIRED_FORMAL_EVIDENCE if merged.get(k) is not True]
            if missing:
                raise ValueError(f"formal QC evidence failed/missing: {missing}")
            if asset["source_kind"] not in FORMAL_SOURCE_KINDS:
                raise ValueError("formal source_kind not allowed")
            if "LOW_RESOLUTION" in asset["flags"] or "UNEXPECTED_IMAGE_FORMAT" in asset["flags"]:
                raise ValueError(f"formal technical flags block PASS: {asset['flags']}")
            allow_embed = allow_recompile = 1
    elif kind == "STORYBOARD_FRAME":
        if qc_status in PASS_SB:
            missing = [k for k in REQUIRED_SB_EVIDENCE if merged.get(k) is not True]
            if missing:
                raise ValueError(f"storyboard QC evidence failed/missing: {missing}")
            if asset["source_kind"] not in STORYBOARD_SOURCE_KINDS:
                raise ValueError("storyboard source_kind not allowed")
            if not asset.get("shot_id") or not asset.get("timecode"):
                raise ValueError("storyboard frame requires shot_id and timecode")
            if "LOW_RESOLUTION" in asset["flags"]:
                raise ValueError("storyboard frame below minimum resolution")
            allow_board = 1
    elif kind == "STORYBOARD_BOARD":
        if qc_status in PASS_SB:
            for key in ["source_frames_verified", "layout_readable", "labels_readable", "no_placeholder_frames"]:
                if merged.get(key) is not True:
                    raise ValueError(f"board QC evidence incomplete: {key}")
            if not merged.get("source_frame_ids") or not merged.get("source_frame_hashes"):
                raise ValueError("board missing source frame provenance")
            allow_embed = 1
    elif kind == "CONCEPT":
        allow_embed = 1 if qc_status == "CONCEPT-APPROVED" and merged.get("appendix_only") is True else 0
    elif kind == "PROMPT_CARD":
        if qc_status in PASS_FORMAL | PASS_SB:
            raise ValueError("PROMPT_CARD cannot receive media PASS status")
    with connect(db_path) as con:
        con.execute("UPDATE assets SET qc_status=?,allowed_for_embed=?,allowed_for_recompile=?,allowed_for_board=?,evidence_json=?,updated_at=? WHERE project_id=? AND asset_id=?",
                    (qc_status, allow_embed, allow_recompile, allow_board, json.dumps(merged, ensure_ascii=False), now_iso(), project_id, asset_id))
    if asset.get("scene_id"):
        if kind == "FORMAL_IMAGE":
            invalidate_scene(db_path, project_id, asset["scene_id"], "FORMAL", f"formal QC changed: {asset_id}")
        elif kind in {"STORYBOARD_FRAME", "STORYBOARD_BOARD"}:
            invalidate_scene(db_path, project_id, asset["scene_id"], "STORYBOARD", f"storyboard QC changed: {asset_id}")
    return get_asset(db_path, project_id, asset_id)


def next_receipt_version(con: sqlite3.Connection, project_id: str, scene_id: str | None, receipt_type: str) -> int:
    row = con.execute("SELECT MAX(version) v FROM receipts WHERE project_id=? AND scene_id IS ? AND receipt_type=?", (project_id, scene_id, receipt_type)).fetchone()
    return int(row["v"] or 0) + 1


def store_receipt(db_path: Path, project_id: str, scene_id: str | None, receipt_type: str, status: str, payload: dict[str, Any]) -> dict[str, Any]:
    input_hash = stable_json_hash(payload)
    with connect(db_path) as con:
        v = next_receipt_version(con, project_id, scene_id, receipt_type)
        con.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)", (project_id, scene_id, receipt_type, status, v, input_hash, json.dumps(payload, ensure_ascii=False), now_iso()))
    return {"project_id": project_id, "scene_id": scene_id, "receipt_type": receipt_type, "status": status, "version": v, "input_hash": input_hash, "payload": payload}


def latest_receipt(db_path: Path, project_id: str, scene_id: str | None, receipt_type: str) -> dict[str, Any] | None:
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM receipts WHERE project_id=? AND scene_id IS ? AND receipt_type=? ORDER BY version DESC LIMIT 1", (project_id, scene_id, receipt_type)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["payload"] = json.loads(d.pop("payload_json"))
    return d


def formal_fingerprint(db_path: Path, project_id: str, scene_id: str) -> dict[str, Any]:
    with connect(db_path) as con:
        s = _require_scene(con, project_id, scene_id)
    assets = list_assets(db_path, project_id, scene_id, "FORMAL_IMAGE")
    return {"expected": s["expected_formal_count"], "assets": [{"asset_id": a["asset_id"], "sha256": a["sha256"], "qc_status": a["qc_status"], "source_kind": a["source_kind"], "allowed_for_embed": a["allowed_for_embed"], "allowed_for_recompile": a["allowed_for_recompile"]} for a in assets]}


def current_formal_gate(db_path: Path, project_id: str, scene_id: str) -> dict[str, Any]:
    gate = latest_receipt(db_path, project_id, scene_id, "FORMAL_GATE")
    if not gate or gate["status"] != "PASS":
        raise ValueError("FORMAL_GATE not PASS")
    current_hash = stable_json_hash(formal_fingerprint(db_path, project_id, scene_id))
    if gate["payload"].get("fingerprint_hash") != current_hash:
        raise ValueError("FORMAL_GATE stale; re-evaluate after asset/QC change")
    return gate


def evaluate_formal_gate(db_path: Path, project_id: str, scene_id: str) -> dict[str, Any]:
    fp = formal_fingerprint(db_path, project_id, scene_id)
    assets = list_assets(db_path, project_id, scene_id, "FORMAL_IMAGE")
    reasons: list[str] = []
    if len(assets) != fp["expected"]:
        reasons.append(f"formal_count {len(assets)} != expected {fp['expected']}")
    for a in assets:
        if a["qc_status"] not in PASS_FORMAL:
            reasons.append(f"{a['asset_id']}: qc={a['qc_status']}")
        if a["source_kind"] not in FORMAL_SOURCE_KINDS:
            reasons.append(f"{a['asset_id']}: source={a['source_kind']}")
        if not a["allowed_for_embed"] or not a["allowed_for_recompile"]:
            reasons.append(f"{a['asset_id']}: permissions")
        if a["flags"]:
            reasons.append(f"{a['asset_id']}: flags={a['flags']}")
        path = Path(a["file_path"])
        if not path.exists() or sha256_file(path) != a["sha256"]:
            reasons.append(f"{a['asset_id']}: file/hash")
    status = "PASS" if not reasons and len(assets) > 0 else "BLOCKED"
    payload = {"fingerprint": fp, "fingerprint_hash": stable_json_hash(fp), "asset_ids": [a["asset_id"] for a in assets], "hashes": [a["sha256"] for a in assets], "failed_reasons": reasons}
    receipt = store_receipt(db_path, project_id, scene_id, "FORMAL_GATE", status, payload)
    with connect(db_path) as con:
        con.execute("UPDATE scenes SET formal_gate_status=? WHERE project_id=? AND scene_id=?", (status, project_id, scene_id))
    return receipt


def record_actual_image_audit(db_path: Path, project_id: str, scene_id: str, delta_items: list[dict[str, Any]], no_difference_confirmed: bool) -> dict[str, Any]:
    gate = current_formal_gate(db_path, project_id, scene_id)
    asset_ids = set(gate["payload"]["asset_ids"])
    if not delta_items and not no_difference_confirmed:
        raise ValueError("empty delta requires no_difference_confirmed=true")
    seen: set[str] = set()
    rejects = []
    normalized = []
    for item in delta_items:
        aid = item.get("asset_id")
        if aid not in asset_ids:
            raise ValueError(f"audit asset not in formal gate: {aid}")
        if aid in seen:
            raise ValueError(f"duplicate audit item: {aid}")
        seen.add(aid)
        if item.get("decision") not in {"ACCEPT", "REJECT"}:
            raise ValueError(f"audit decision must be ACCEPT/REJECT: {aid}")
        if not isinstance(item.get("planned_facts"), dict) or not isinstance(item.get("visible_facts"), dict):
            raise ValueError(f"planned_facts and visible_facts required: {aid}")
        normalized.append(item)
        if item["decision"] == "REJECT":
            rejects.append(item)
    if not no_difference_confirmed and seen != asset_ids:
        raise ValueError(f"audit must cover every formal asset; missing={sorted(asset_ids-seen)}")
    status = "BLOCKED" if rejects else "COMPLETE"
    payload = {"delta_items": normalized, "no_difference_confirmed": bool(no_difference_confirmed), "formal_gate_hash": gate["input_hash"], "formal_fingerprint_hash": gate["payload"]["fingerprint_hash"], "audited_asset_ids": sorted(seen), "rejected": rejects}
    receipt = store_receipt(db_path, project_id, scene_id, "ACTUAL_IMAGE_AUDIT", status, payload)
    with connect(db_path) as con:
        con.execute("INSERT OR REPLACE INTO actual_image_audits VALUES(?,?,?,?,?,?,?)", (project_id, scene_id, status, int(no_difference_confirmed), json.dumps(normalized, ensure_ascii=False), receipt["version"], now_iso()))
        con.execute("UPDATE scenes SET actual_image_audit_status=?,video_prompt_status='PENDING',storyboard_gate_status='PENDING' WHERE project_id=? AND scene_id=?", (status, project_id, scene_id))
    invalidate_document(db_path, project_id, f"actual image audit updated: {scene_id}")
    return receipt


def current_actual_audit(db_path: Path, project_id: str, scene_id: str) -> dict[str, Any]:
    gate = current_formal_gate(db_path, project_id, scene_id)
    audit = latest_receipt(db_path, project_id, scene_id, "ACTUAL_IMAGE_AUDIT")
    if not audit or audit["status"] != "COMPLETE":
        raise ValueError("actual image audit not COMPLETE")
    if audit["payload"].get("formal_gate_hash") != gate["input_hash"]:
        raise ValueError("actual image audit stale")
    return audit


def register_video_prompt(db_path: Path, project_id: str, scene_id: str, content: str, source_asset_ids: list[str], quality_evidence: dict[str, Any]) -> dict[str, Any]:
    gate = current_formal_gate(db_path, project_id, scene_id)
    audit = current_actual_audit(db_path, project_id, scene_id)
    expected = set(gate["payload"]["asset_ids"])
    if set(source_asset_ids) != expected or len(source_asset_ids) != len(expected):
        raise ValueError("video prompt source_asset_ids must exactly equal passed formal assets")
    if DRAFT_PROMPT_RE.search(content):
        raise ValueError("draft marker in FINAL prompt")
    if len(content.strip()) < 120:
        raise ValueError("FINAL video prompt is too short to carry timeline and continuity")
    missing = [k for k in REQUIRED_VIDEO_EVIDENCE if quality_evidence.get(k) is not True]
    if missing:
        raise ValueError(f"video prompt quality evidence failed/missing: {missing}")
    with connect(db_path) as con:
        row = con.execute("SELECT MAX(version) v FROM video_prompts WHERE project_id=? AND scene_id=?", (project_id, scene_id)).fetchone()
        v = int(row["v"] or 0) + 1
        ch = hashlib.sha256(content.encode("utf-8")).hexdigest()
        con.execute("INSERT INTO video_prompts VALUES(?,?,?,?,?,?,?,?,?,?)", (project_id, scene_id, v, "FINAL", content, len(content), json.dumps(source_asset_ids), json.dumps(quality_evidence, ensure_ascii=False), ch, now_iso()))
    invalidate_scene(db_path, project_id, scene_id, "VIDEO", f"FINAL video prompt v{v} registered")
    with connect(db_path) as con:
        con.execute("UPDATE scenes SET video_prompt_status='FINAL' WHERE project_id=? AND scene_id=?", (project_id, scene_id))
    payload = {"version": v, "content_hash": ch, "source_asset_ids": source_asset_ids, "char_count": len(content), "quality_evidence": quality_evidence, "actual_audit_hash": audit["input_hash"], "formal_gate_hash": gate["input_hash"]}
    return store_receipt(db_path, project_id, scene_id, "VIDEO_PROMPT", "FINAL", payload)


def current_video_prompt(db_path: Path, project_id: str, scene_id: str) -> dict[str, Any]:
    gate = current_formal_gate(db_path, project_id, scene_id)
    audit = current_actual_audit(db_path, project_id, scene_id)
    receipt = latest_receipt(db_path, project_id, scene_id, "VIDEO_PROMPT")
    if not receipt or receipt["status"] != "FINAL":
        raise ValueError("FINAL video prompt required")
    if receipt["payload"].get("formal_gate_hash") != gate["input_hash"] or receipt["payload"].get("actual_audit_hash") != audit["input_hash"]:
        raise ValueError("FINAL video prompt stale")
    return receipt


def storyboard_fingerprint(db_path: Path, project_id: str, scene_id: str) -> dict[str, Any]:
    with connect(db_path) as con:
        s = _require_scene(con, project_id, scene_id)
    frames = list_assets(db_path, project_id, scene_id, "STORYBOARD_FRAME")
    return {"expected": s["expected_storyboard_frames"], "frames": [{"asset_id": a["asset_id"], "sha256": a["sha256"], "qc_status": a["qc_status"], "allowed_for_board": a["allowed_for_board"], "shot_id": a.get("shot_id"), "timecode": a.get("timecode")} for a in frames]}


def evaluate_storyboard_gate(db_path: Path, project_id: str, scene_id: str, board_asset_id: str | None = None) -> dict[str, Any]:
    video = current_video_prompt(db_path, project_id, scene_id)
    fp = storyboard_fingerprint(db_path, project_id, scene_id)
    frames = list_assets(db_path, project_id, scene_id, "STORYBOARD_FRAME")
    reasons: list[str] = []
    if fp["expected"] and len(frames) != fp["expected"]:
        reasons.append(f"frame_count {len(frames)} != expected {fp['expected']}")
    for a in frames:
        if a["qc_status"] not in PASS_SB or not a["allowed_for_board"]:
            reasons.append(f"{a['asset_id']}: frame not board-ready")
        if not a.get("shot_id") or not a.get("timecode"):
            reasons.append(f"{a['asset_id']}: missing shot/timecode")
        if not Path(a["file_path"]).exists() or sha256_file(Path(a["file_path"])) != a["sha256"]:
            reasons.append(f"{a['asset_id']}: file/hash")
    board = None
    if board_asset_id:
        board = get_asset(db_path, project_id, board_asset_id)
        if board["scene_id"] != scene_id or board["kind"] != "STORYBOARD_BOARD" or board["qc_status"] not in PASS_SB or not board["allowed_for_embed"]:
            reasons.append(f"{board_asset_id}: board not embed-ready")
        else:
            expected_ids = [a["asset_id"] for a in frames]
            expected_hashes = [a["sha256"] for a in frames]
            if board["evidence"].get("source_frame_ids") != expected_ids or board["evidence"].get("source_frame_hashes") != expected_hashes:
                reasons.append(f"{board_asset_id}: source frame provenance stale")
            if board["evidence"].get("video_prompt_hash") != video["input_hash"]:
                reasons.append(f"{board_asset_id}: video prompt provenance stale")
    status = "PASS" if not reasons and len(frames) > 0 and board is not None else "BLOCKED"
    payload = {"fingerprint": fp, "fingerprint_hash": stable_json_hash(fp), "frame_ids": [a["asset_id"] for a in frames], "frame_hashes": [a["sha256"] for a in frames], "board_asset_id": board_asset_id, "board_hash": board["sha256"] if board else None, "video_prompt_hash": video["input_hash"], "failed_reasons": reasons}
    receipt = store_receipt(db_path, project_id, scene_id, "STORYBOARD_GATE", status, payload)
    with connect(db_path) as con:
        con.execute("UPDATE scenes SET storyboard_gate_status=?,checkpoint_status=? WHERE project_id=? AND scene_id=?", (status, "PASS" if status == "PASS" else "PENDING", project_id, scene_id))
    return receipt


def project_state(db_path: Path, project_id: str) -> dict[str, Any]:
    with connect(db_path) as con:
        p = con.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        scenes = con.execute("SELECT * FROM scenes WHERE project_id=? ORDER BY scene_id", (project_id,)).fetchall()
    if not p:
        raise KeyError(project_id)
    return {"project": dict(p), "scenes": [dict(s) for s in scenes], "assets": list_assets(db_path, project_id)}


def file_response(path: Path, public_url: str | None = None, inline_limit: int = 9_000_000) -> dict[str, Any]:
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if path.suffix.lower() == ".docx" else "application/pdf"
    if path.stat().st_size <= inline_limit:
        return {"openaiFileResponse": [{"name": path.name, "mime_type": mime, "content": base64.b64encode(path.read_bytes()).decode("ascii")}]}
    if not public_url:
        return {"artifact_path": str(path), "warning": "file exceeds inline action limit; configure PUBLIC_BASE_URL"}
    return {"artifact_url": public_url, "name": path.name, "bytes": path.stat().st_size}
