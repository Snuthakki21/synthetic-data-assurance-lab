import argparse
import json
from pathlib import Path
from .registry import execute, projects


def main():
    parser = argparse.ArgumentParser(description="Run inspectable enterprise AI reference applications")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List available projects")
    run = sub.add_parser("run", help="Execute one project")
    run.add_argument("project_id")
    run.add_argument("--input", type=Path, help="JSON input; defaults to original synthetic fixture")
    run.add_argument("--output", type=Path)
    run.add_argument("--mode", choices=["local", "live"], default="local")
    build = sub.add_parser("build", help="Build browser app and execute sample reports")
    build.add_argument("--output", type=Path)
    server = sub.add_parser("serve", help="Build and serve a loopback web app")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--mode", choices=["local", "live"], default="local")
    sub.add_parser("mcp", help="Run read-only MCP tools over stdio")
    args = parser.parse_args()
    try:
        if args.command == "list":
            for pid, module in projects().items():
                print(f"{pid}: {module.META['title']}")
        elif args.command == "run":
            payload = json.loads(args.input.read_text()) if args.input else None
            result = execute(args.project_id, payload, args.mode)
            text = json.dumps(result, indent=2, allow_nan=False) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(text)
            else:
                print(text, end="")
        elif args.command in {"build", "serve"}:
            from .build import build
            data = build(args.output if args.command == "build" else None)
            if args.command == "build":
                print(f"Built {len(data['projects'])} runnable project(s)")
            else:
                from .server import serve
                serve(args.port, args.mode)
        elif args.command == "mcp":
            from .mcp import main as mcp_main
            mcp_main()
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")

if __name__ == "__main__":
    main()
