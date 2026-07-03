from __future__ import annotations
from pathlib import Path
from typing import Any
import json, re
from PIL import Image
from .core import connect, now_iso, project_state, REQUIRED_PAGE_QC, current_formal_gate, current_actual_audit, current_video_prompt, latest_receipt
from .docx_ops import audit_docx_media
from .render_docx_local import render_docx


def natural_key(p: Path):
    m = re.search(r'(\d+)', p.stem)
    return int(m.group(1)) if m else 0


def blank_ratio(im: Image.Image) -> float:
    thumb = im.convert('L').resize((100, 100))
    hist = thumb.histogram()
    return round(sum(hist[248:]) / 10000, 4)


def content_bbox_ratio(im: Image.Image) -> tuple[float, float]:
    g = im.convert('L').resize((400, 400))
    pix = g.load()
    xs, ys = [], []
    for y in range(g.height):
        for x in range(g.width):
            if pix[x, y] < 245:
                xs.append(x)
                ys.append(y)
    if not xs:
        return (0, 0)
    return (round((max(xs) - min(xs) + 1) / g.width, 4), round((max(ys) - min(ys) + 1) / g.height, 4))


def render_structural(db_path: Path, project_id: str, docx_path: Path, out_dir: Path, dpi: int = 300) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    returncode, stdout, stderr, pdf, pages = render_docx(docx_path, out_dir, dpi)
    pages = sorted(pages, key=natural_key)
    info, errors, warnings = [], [], []
    for p in pages:
        with Image.open(p) as im:
            br = blank_ratio(im)
            bw, bh = content_bbox_ratio(im)
            info.append({'page': len(info) + 1, 'file': p.name, 'pixels': list(im.size),
                         'orientation': 'LANDSCAPE' if im.width > im.height else 'PORTRAIT',
                         'blank_ratio': br, 'bbox_width_ratio': bw, 'bbox_height_ratio': bh,
                         'bytes': p.stat().st_size})
            if br > 0.9995:
                errors.append(f'{p.name}: effectively blank page')
            elif bw < 0.35 or bh < 0.20:
                warnings.append(f'{p.name}: sparse content; explicit visual review required')
    if not pages:
        errors.append('no rendered pages')
    report = {'returncode': returncode, 'stdout': stdout[-2000:], 'stderr': stderr[-2000:],
              'pages': info, 'page_count': len(info), 'pdfs': [str(pdf)] if pdf else [],
              'errors': errors, 'warnings': warnings, 'pass': returncode == 0 and bool(pages) and not errors}
    rp = out_dir / 'render_structural_report.json'
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with connect(db_path) as con:
        con.execute("INSERT OR REPLACE INTO audits VALUES(?,?,?,?,?,?)", (project_id, 'RENDER_STRUCTURAL', 'PASS' if report['pass'] else 'FAIL', str(rp), json.dumps(report, ensure_ascii=False), now_iso()))
        con.execute('UPDATE projects SET preview_pdf_path=?,render_dir=?,visual_page_qc_status="PENDING" WHERE project_id=?', (str(pdf) if pdf else None, str(out_dir), project_id))
    return report


def store_ppi_audit(db_path: Path, project_id: str, docx_path: Path, out_json: Path) -> dict[str, Any]:
    report = audit_docx_media(db_path, project_id, docx_path)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with connect(db_path) as con:
        con.execute("INSERT OR REPLACE INTO audits VALUES(?,?,?,?,?,?)", (project_id, 'PPI_MEDIA', 'PASS' if report['pass'] else 'FAIL', str(out_json), json.dumps(report, ensure_ascii=False), now_iso()))
    return report


def confirm_visual_qc(db_path: Path, project_id: str, page_results: list[dict[str, Any]], note: str) -> dict[str, Any]:
    with connect(db_path) as con:
        rr = con.execute("SELECT * FROM audits WHERE project_id=? AND audit_type='RENDER_STRUCTURAL'", (project_id,)).fetchone()
    if not rr or rr['status'] != 'PASS':
        raise ValueError('structural render must PASS before visual page QC')
    render_payload = json.loads(rr['payload_json'])
    page_count = int(render_payload.get('page_count', 0))
    if len(page_results) != page_count:
        raise ValueError(f'visual QC must cover every page: {len(page_results)} != {page_count}')
    seen = set()
    failures = []
    normalized = []
    for row in page_results:
        page = int(row.get('page', 0))
        if page < 1 or page > page_count or page in seen:
            raise ValueError(f'invalid/duplicate page result: {page}')
        seen.add(page)
        missing = [k for k in REQUIRED_PAGE_QC if row.get(k) is not True]
        status = row.get('status')
        if status != 'PASS' or missing:
            failures.append({'page': page, 'status': status, 'failed_checks': missing})
        normalized.append(dict(row))
    status = 'PASS' if not failures else 'FAIL'
    payload = {'page_results': sorted(normalized, key=lambda x: int(x['page'])), 'note': note, 'status': status, 'failed_pages': failures, 'render_report_hash': rr['created_at']}
    with connect(db_path) as con:
        con.execute("INSERT OR REPLACE INTO audits VALUES(?,?,?,?,?,?)", (project_id, 'VISUAL_PAGE_QC', status, None, json.dumps(payload, ensure_ascii=False), now_iso()))
        con.execute('UPDATE projects SET visual_page_qc_status=? WHERE project_id=?', (status, project_id))
    return payload


def _validate_current_scene(db_path: Path, project_id: str, scene: dict[str, Any], reasons: list[str]) -> None:
    sid = scene['scene_id']
    try:
        current_formal_gate(db_path, project_id, sid)
    except Exception as e:
        reasons.append(f'{sid}: formal gate current check failed: {e}')
    try:
        current_actual_audit(db_path, project_id, sid)
    except Exception as e:
        reasons.append(f'{sid}: actual audit current check failed: {e}')
    try:
        current_video_prompt(db_path, project_id, sid)
    except Exception as e:
        reasons.append(f'{sid}: video prompt current check failed: {e}')
    sb = latest_receipt(db_path, project_id, sid, 'STORYBOARD_GATE')
    if not sb or sb['status'] != 'PASS':
        reasons.append(f'{sid}: storyboard gate not PASS')


def evaluate_release(db_path: Path, project_id: str) -> dict[str, Any]:
    state = project_state(db_path, project_id)
    reasons = []
    for scene in state['scenes']:
        _validate_current_scene(db_path, project_id, scene, reasons)
        for field, expected in [('formal_gate_status', 'PASS'), ('actual_image_audit_status', 'COMPLETE'), ('video_prompt_status', 'FINAL'), ('storyboard_gate_status', 'PASS'), ('checkpoint_status', 'PASS')]:
            if scene[field] != expected:
                reasons.append(f"{scene['scene_id']}: {field}={scene[field]}")
    with connect(db_path) as con:
        p = con.execute('SELECT * FROM projects WHERE project_id=?', (project_id,)).fetchone()
        audits = {r['audit_type']: dict(r) for r in con.execute('SELECT * FROM audits WHERE project_id=?', (project_id,))}
        plan_count = con.execute('SELECT COUNT(*) n FROM embed_plan WHERE project_id=?', (project_id,)).fetchone()['n']
    if not plan_count:
        reasons.append('embed plan missing')
    if not p['output_docx_path'] or not Path(p['output_docx_path']).exists():
        reasons.append('output DOCX missing')
    for audit_name in ['SOURCE_PREFLIGHT', 'PPI_MEDIA', 'RENDER_STRUCTURAL', 'VISUAL_PAGE_QC']:
        if audit_name not in audits or audits[audit_name]['status'] != 'PASS':
            reasons.append(f'{audit_name} not PASS')
    status = 'RELEASED' if not reasons else 'PARTIAL'
    payload = {'status': status, 'failed_reasons': sorted(set(reasons)), 'scene_count': len(state['scenes']),
               'formal_assets': len([a for a in state['assets'] if a['kind'] == 'FORMAL_IMAGE']),
               'storyboard_boards': len([a for a in state['assets'] if a['kind'] == 'STORYBOARD_BOARD']),
               'embedded_docx': p['output_docx_path']}
    with connect(db_path) as con:
        con.execute('UPDATE projects SET release_status=? WHERE project_id=?', (status, project_id))
    return payload
