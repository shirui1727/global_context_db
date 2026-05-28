from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx", ".doc", ".rtf", ".html", ".htm"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".rtf"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | DOCUMENT_EXTENSIONS
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "dist", "release", "data", ".venv", "venv"}


def infer_asset_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    return "generic_asset"


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_scan_item(path: Path, uri_prefix: str, root: Path | None = None) -> dict[str, Any]:
    path = path.resolve()
    root = (root or path.parent).resolve()
    relative = path.relative_to(root).as_posix()
    asset_kind = infer_asset_kind(path)
    media_type = guess_type(path.name)[0]
    stat = path.stat()
    return {
        "uri": f"{uri_prefix.rstrip('/')}/{relative}",
        "asset_key": f"{asset_kind}:{path.stem.lower()}",
        "checksum": checksum_file(path),
        "size_bytes": stat.st_size,
        "modified_at": _mtime_iso(stat.st_mtime),
        "media_type": media_type,
        "asset_kind": asset_kind,
        "title": path.stem,
        "summary": "",
        "tags": [asset_kind],
        "trust_level": "unverified",
        "metadata": {"source_path": str(path), "relative_path": relative},
    }


def build_scan_run(
    root: Path,
    scope_prefix: str,
    uri_prefix: str | None = None,
    mark_missing: bool = True,
    created_by: str = "media_manifest_worker",
) -> dict[str, Any]:
    root = root.resolve()
    observed = [
        build_scan_item(path, uri_prefix=uri_prefix or scope_prefix, root=root)
        for path in iter_supported_files(root)
    ]
    return {
        "scope_prefix": scope_prefix.rstrip("/"),
        "mark_missing": mark_missing,
        "observed": observed,
        "created_by": created_by,
        "metadata": {
            "source_root": str(root),
            "generated_by": created_by,
            "observed_count": len(observed),
        },
    }


def iter_supported_files(root: Path) -> list[Path]:
    root = root.resolve()
    paths = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix().lower())


def build_analysis_manifest(
    path: Path,
    asset_id: str,
    artifact_uri_prefix: str,
    artifact_root: Path,
    generated_by: str = "media_manifest_worker",
    ffprobe: Callable[[Path], dict[str, Any] | None] | None = None,
    ocr_adapter: Callable[[Path], str | None] | None = None,
    asr_adapter: Callable[[Path], str | None] | None = None,
) -> dict[str, Any]:
    path = path.resolve()
    artifact_root = artifact_root.resolve()
    asset_dir = artifact_root / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset_kind = infer_asset_kind(path)
    artifacts = []
    summary = ""
    if asset_kind == "document" and path.suffix.lower() in TEXT_EXTENSIONS:
        text = _read_text(path)
        artifact_path = asset_dir / f"{path.stem}.txt"
        artifact_path.write_text(text, encoding="utf-8")
        summary = _preview(text)
        artifacts.append(
            _artifact(
                "embedding_text",
                f"{artifact_uri_prefix.rstrip('/')}/{asset_id}/{artifact_path.name}",
                "text/plain",
                text=text,
                metadata={"source_path": str(path)},
            )
        )
    elif asset_kind == "image":
        probe = _safe_probe(path, ffprobe)
        probe_uri = f"{artifact_uri_prefix.rstrip('/')}/{asset_id}/{path.stem}.probe.json"
        _write_json_artifact(asset_dir / f"{path.stem}.probe.json", probe)
        artifacts.append(
            _artifact(
                "probe_metadata",
                probe_uri,
                "application/json",
                text=json.dumps(probe, ensure_ascii=False),
                metadata={"source_path": str(path), "probe_status": "ready" if probe else "placeholder", "probe": probe},
            )
        )
        ocr_text = _safe_text_adapter(path, ocr_adapter)
        if ocr_text:
            summary = _preview(ocr_text)
            artifacts.append(
                _artifact(
                    "ocr_text",
                    f"{artifact_uri_prefix.rstrip('/')}/{asset_id}/{path.stem}.ocr.txt",
                    "text/plain",
                    text=ocr_text,
                    metadata={"source_path": str(path), "adapter": "ocr"},
                )
            )
    elif asset_kind == "video":
        probe = _safe_probe(path, ffprobe)
        probe_uri = f"{artifact_uri_prefix.rstrip('/')}/{asset_id}/{path.stem}.probe.json"
        _write_json_artifact(asset_dir / f"{path.stem}.probe.json", probe)
        artifacts.append(
            _artifact(
                "probe_metadata",
                probe_uri,
                "application/json",
                text=json.dumps(probe, ensure_ascii=False),
                metadata={"source_path": str(path), "probe_status": "ready" if probe else "placeholder", "probe": probe},
            )
        )
        asr_text = _safe_text_adapter(path, asr_adapter)
        if asr_text:
            summary = _preview(asr_text)
            artifacts.append(
                _artifact(
                    "asr_text",
                    f"{artifact_uri_prefix.rstrip('/')}/{asset_id}/{path.stem}.asr.txt",
                    "text/plain",
                    text=asr_text,
                    metadata={"source_path": str(path), "adapter": "asr"},
                )
            )
    else:
        artifacts.append(
            _artifact(
                "probe_metadata",
                f"{artifact_uri_prefix.rstrip('/')}/{asset_id}/{path.stem}.probe.json",
                "application/json",
                metadata={"source_path": str(path), "note": "generic probe placeholder"},
            )
        )
    return {
        "asset_id": asset_id,
        "payload": {
            "analysis_status": "indexed",
            "summary": summary or None,
            "tags": [asset_kind],
            "generated_by": generated_by,
            "artifacts": artifacts,
            "metadata": {"source_path": str(path), "asset_kind": asset_kind},
        },
    }


def post_json(url: str, payload: dict[str, Any], api_key: str | None = None, timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"content-type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed with HTTP {error.code}: {detail}") from error
    if not response_body:
        return {}
    return json.loads(response_body)


def _artifact(
    artifact_kind: str,
    artifact_uri: str,
    media_type: str,
    text: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "artifact_kind": artifact_kind,
        "artifact_uri": artifact_uri,
        "media_type": media_type,
        "status": "ready",
        "text": text,
        "metadata": metadata or {},
    }


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def run_ffprobe(path: Path, ffprobe_bin: str = "ffprobe") -> dict[str, Any]:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout or "{}")


def _safe_probe(path: Path, ffprobe: Callable[[Path], dict[str, Any] | None] | None) -> dict[str, Any] | None:
    if not ffprobe:
        return None
    return ffprobe(path)


def _safe_text_adapter(path: Path, adapter: Callable[[Path], str | None] | None) -> str:
    if not adapter:
        return ""
    return adapter(path) or ""


def _write_json_artifact(path: Path, payload: dict[str, Any] | None) -> None:
    path.write_text(json.dumps(payload or {}, ensure_ascii=False, indent=2), encoding="utf-8")


def _preview(text: str, limit: int = 500) -> str:
    return " ".join(text.split())[:limit]


def _mtime_iso(value: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(value, UTC).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GCD asset scan or analysis manifest payloads.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--mode", choices=["scan-item", "scan-run", "analysis-manifest"], default="analysis-manifest")
    parser.add_argument("--asset-id")
    parser.add_argument("--uri-prefix", default="smb://NAS/assets")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--artifact-root", type=Path, default=Path("data/artifacts"))
    parser.add_argument("--artifact-uri-prefix", default="/data/artifacts")
    parser.add_argument("--generated-by", default="media_manifest_worker")
    parser.add_argument("--scope-prefix", default=None)
    parser.add_argument("--no-mark-missing", action="store_true")
    parser.add_argument("--post-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--ffprobe", action="store_true", help="Run ffprobe for image/video probe_metadata when available.")
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--ocr-text-file", type=Path, default=None, help="Optional OCR adapter text file to attach for image assets.")
    parser.add_argument("--asr-text-file", type=Path, default=None, help="Optional ASR adapter text file to attach for video assets.")
    args = parser.parse_args()
    if args.mode == "scan-item":
        payload = build_scan_item(args.path, uri_prefix=args.uri_prefix, root=args.root)
    elif args.mode == "scan-run":
        payload = build_scan_run(
            args.path,
            scope_prefix=args.scope_prefix or args.uri_prefix,
            uri_prefix=args.uri_prefix,
            mark_missing=not args.no_mark_missing,
            created_by=args.generated_by,
        )
    else:
        if not args.asset_id:
            raise SystemExit("--asset-id is required for analysis-manifest")
        payload = build_analysis_manifest(
            args.path,
            asset_id=args.asset_id,
            artifact_uri_prefix=args.artifact_uri_prefix,
            artifact_root=args.artifact_root,
            generated_by=args.generated_by,
            ffprobe=(lambda item: run_ffprobe(item, args.ffprobe_bin)) if args.ffprobe else None,
            ocr_adapter=(lambda _item: args.ocr_text_file.read_text(encoding="utf-8", errors="replace")) if args.ocr_text_file else None,
            asr_adapter=(lambda _item: args.asr_text_file.read_text(encoding="utf-8", errors="replace")) if args.asr_text_file else None,
        )
    if args.post_url:
        response = post_json(args.post_url, payload["payload"] if args.mode == "analysis-manifest" else payload, api_key=args.api_key, timeout=args.timeout)
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
