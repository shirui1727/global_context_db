from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from tools.media_manifest_worker import build_analysis_manifest, build_scan_item, build_scan_run, infer_asset_kind, post_json


def test_infer_asset_kind_for_common_media():
    assert infer_asset_kind(Path("photo.jpg")) == "image"
    assert infer_asset_kind(Path("clip.mp4")) == "video"
    assert infer_asset_kind(Path("paper.pdf")) == "document"
    assert infer_asset_kind(Path("notes.md")) == "document"


def test_build_scan_item_uses_stable_asset_key_and_checksum(tmp_path: Path):
    source = tmp_path / "demo.txt"
    source.write_text("hello worker", encoding="utf-8")

    item = build_scan_item(source, uri_prefix="smb://NAS/docs", root=tmp_path)

    assert item["uri"] == "smb://NAS/docs/demo.txt"
    assert item["asset_key"] == "document:demo"
    assert item["checksum"]
    assert item["size_bytes"] == len("hello worker")
    assert item["asset_kind"] == "document"


def test_build_analysis_manifest_for_document_text(tmp_path: Path):
    source = tmp_path / "brief.md"
    source.write_text("# Brief\n\nNAS memory workflow notes.", encoding="utf-8")
    artifact_root = tmp_path / "artifacts"

    manifest = build_analysis_manifest(
        source,
        asset_id="asset-123",
        artifact_uri_prefix="/data/artifacts",
        artifact_root=artifact_root,
        generated_by="pytest-worker",
    )

    assert manifest["asset_id"] == "asset-123"
    assert manifest["payload"]["analysis_status"] == "indexed"
    assert manifest["payload"]["generated_by"] == "pytest-worker"
    assert manifest["payload"]["artifacts"][0]["artifact_kind"] == "embedding_text"
    assert manifest["payload"]["artifacts"][0]["text"].startswith("# Brief")
    assert (artifact_root / "asset-123" / "brief.txt").exists()


def test_build_scan_run_recurses_supported_files_and_skips_noise(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "photos").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "docs" / "brief.md").write_text("brief", encoding="utf-8")
    (tmp_path / "photos" / "cover.jpg").write_bytes(b"fake image")
    (tmp_path / "__pycache__" / "ignore.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "scratch.tmp").write_text("ignore", encoding="utf-8")

    payload = build_scan_run(
        tmp_path,
        scope_prefix="smb://NAS/library",
        uri_prefix="smb://NAS/library",
        created_by="pytest-worker",
    )

    assert payload["scope_prefix"] == "smb://NAS/library"
    assert payload["created_by"] == "pytest-worker"
    assert payload["mark_missing"] is True
    assert [item["uri"] for item in payload["observed"]] == [
        "smb://NAS/library/docs/brief.md",
        "smb://NAS/library/photos/cover.jpg",
    ]
    assert {item["asset_kind"] for item in payload["observed"]} == {"document", "image"}


def test_post_json_sends_api_key_and_payload():
    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["content-length"])
            captured["path"] = self.path
            captured["api_key"] = self.headers.get("x-api-key")
            captured["body"] = self.rfile.read(length).decode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = post_json(
            f"http://127.0.0.1:{server.server_port}/assets/scan-runs",
            {"scope_prefix": "smb://NAS/test", "observed": []},
            api_key="secret",
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert response == {"ok": True}
    assert captured["path"] == "/assets/scan-runs"
    assert captured["api_key"] == "secret"
    assert '"scope_prefix": "smb://NAS/test"' in captured["body"]


def test_cli_post_url_can_submit_analysis_manifest(tmp_path: Path, capsys):
    source = tmp_path / "brief.md"
    source.write_text("short text", encoding="utf-8")
    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["content-length"])
            captured["path"] = self.path
            captured["api_key"] = self.headers.get("x-api-key")
            captured["body"] = self.rfile.read(length).decode("utf-8")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"accepted": true}')

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from tools import media_manifest_worker

        argv = [
            str(source),
            "--mode",
            "analysis-manifest",
            "--asset-id",
            "asset-1",
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--post-url",
            f"http://127.0.0.1:{server.server_port}/assets/asset-1/analysis-manifest",
            "--api-key",
            "secret",
        ]
        old_argv = __import__("sys").argv
        __import__("sys").argv = ["media_manifest_worker.py", *argv]
        try:
            media_manifest_worker.main()
        finally:
            __import__("sys").argv = old_argv
    finally:
        server.shutdown()
        thread.join(timeout=2)

    out = capsys.readouterr().out
    assert captured["path"] == "/assets/asset-1/analysis-manifest"
    assert captured["api_key"] == "secret"
    assert '"accepted": true' in out
