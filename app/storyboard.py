from __future__ import annotations
from pathlib import Path
from typing import Any
from PIL import Image, ImageOps, ImageDraw, ImageFont
import math
from .core import list_assets, register_asset_file, get_asset, current_video_prompt


def font(size: int):
    for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def entropy(im: Image.Image) -> float:
    hist = im.convert("L").histogram()
    total = sum(hist)
    return -sum((h / total) * math.log2(h / total) for h in hist if h)


def compose_board(db_path: Path, storage_root: Path, project_id: str, scene_id: str, board_asset_id: str,
                  cols: int = 4, cell_w: int = 1920, cell_h: int = 1080, gap: int = 20, header: int = 90) -> dict[str, Any]:
    video = current_video_prompt(db_path, project_id, scene_id)
    frames = list_assets(db_path, project_id, scene_id, "STORYBOARD_FRAME")
    if not frames:
        raise ValueError("no storyboard frames")
    for fr in frames:
        if fr["qc_status"] not in {"SB-PASS", "SB-PASS-WITH-FIX"} or not fr["allowed_for_board"]:
            raise ValueError(f"frame not board-ready: {fr['asset_id']}")
        if not fr.get("shot_id") or not fr.get("timecode"):
            raise ValueError(f"frame missing shot/timecode: {fr['asset_id']}")
    frames = sorted(frames, key=lambda x: (x.get("timecode") or "", x["asset_id"]))
    if len(frames) > 9:
        raise ValueError("more than 9 frames must be split into A/B boards before composition")
    cols = max(1, min(cols, len(frames)))
    rows = math.ceil(len(frames) / cols)
    W = cols * cell_w + (cols + 1) * gap
    H = rows * (cell_h + header) + (rows + 1) * gap
    board = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(board)
    ft = font(max(28, header // 2))
    warnings = []
    for i, fr in enumerate(frames):
        r, c = divmod(i, cols)
        x = gap + c * (cell_w + gap)
        y = gap + r * (cell_h + header + gap)
        with Image.open(fr["file_path"]).convert("RGB") as im:
            ent = entropy(im)
            if ent < 3.5:
                warnings.append(f"low visual entropy (must be confirmed by visual QC): {fr['asset_id']}")
            fitted = ImageOps.fit(im, (cell_w, cell_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        board.paste(fitted, (x, y))
        draw.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], outline="black", width=4)
        label = f"{fr.get('shot_id') or fr['asset_id']}  {fr.get('timecode') or ''}".strip()
        draw.text((x + 20, y + cell_h + 15), label, font=ft, fill="black")
    tmp = storage_root / project_id / "boards" / f"{board_asset_id}.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    board.save(tmp, format="PNG", compress_level=3)
    asset = register_asset_file(db_path, storage_root, project_id,
                                {"asset_id": board_asset_id, "scene_id": scene_id, "kind": "STORYBOARD_BOARD", "source_kind": "PROGRAMMATIC"},
                                tmp, board_asset_id + ".png", "image/png")
    # Store immutable provenance before human/model board QC. record_qc merges rather than overwrites it.
    evidence = dict(asset.get("evidence") or {})
    evidence.update({
        "source_frame_ids": [f["asset_id"] for f in frames],
        "source_frame_hashes": [f["sha256"] for f in frames],
        "video_prompt_hash": video["input_hash"],
        "programmatic_composite": True,
        "composition_pixels": [W, H],
    })
    from .core import connect, now_iso
    import json
    with connect(db_path) as con:
        con.execute("UPDATE assets SET evidence_json=?,updated_at=? WHERE project_id=? AND asset_id=?",
                    (json.dumps(evidence, ensure_ascii=False), now_iso(), project_id, board_asset_id))
    asset = get_asset(db_path, project_id, board_asset_id)
    return {"asset": asset, "source_frame_ids": evidence["source_frame_ids"], "warnings": warnings, "pixels": [W, H]}
