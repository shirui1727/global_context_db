import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.core.schemas import IngestRequest, MemoryCreate
from app.storage.bootstrap import bootstrap
from app.ingest.pipeline import ingest_text
from app.memory.service import add_memory, list_memories
from app.retrieval.service import search_context
from app.storage.repo import documents_repo


def main() -> None:
    bootstrap(settings)
    parser = argparse.ArgumentParser(prog="gcd")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("path")

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)

    memory = sub.add_parser("memory")
    memory_sub = memory.add_subparsers(dest="memory_cmd", required=True)
    mem_add = memory_sub.add_parser("add")
    mem_add.add_argument("content")
    mem_add.add_argument("--tag", action="append", default=[])
    memory_sub.add_parser("list")

    docs = sub.add_parser("documents")
    docs_sub = docs.add_subparsers(dest="documents_cmd", required=True)
    docs_sub.add_parser("list")

    args = parser.parse_args()
    if args.cmd == "ingest":
        text = Path(args.path).read_text(encoding="utf-8")
        print(json.dumps(ingest_text(IngestRequest(source=args.path, text=text)), ensure_ascii=False, indent=2))
    elif args.cmd == "search":
        print(json.dumps(search_context(args.query, args.top_k), ensure_ascii=False, indent=2))
    elif args.cmd == "memory" and args.memory_cmd == "add":
        print(json.dumps(add_memory(MemoryCreate(content=args.content, tags=args.tag)), ensure_ascii=False, indent=2))
    elif args.cmd == "memory" and args.memory_cmd == "list":
        print(json.dumps(list_memories(), ensure_ascii=False, indent=2))
    elif args.cmd == "documents" and args.documents_cmd == "list":
        rows = documents_repo().list_all()
        print(json.dumps(rows, ensure_ascii=False, indent=2))
