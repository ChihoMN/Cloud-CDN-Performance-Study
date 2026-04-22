from __future__ import annotations

import importlib
import sys


COMMAND_MODULES = {
    "generate-files": "scripts.generate_files",
    "upload-files": "scripts.upload_files",
    "benchmark": "scripts.benchmark",
    "analyze": "scripts.analyze",
}


def print_usage() -> None:
    commands = "\n".join(f"  {name}" for name in COMMAND_MODULES)
    print("Usage: python main.py <command> [options]\n")
    print("Commands:")
    print(commands)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print_usage()
        return 0

    command = sys.argv[1]
    module_name = COMMAND_MODULES.get(command)
    if module_name is None:
        print(f"Unknown command: {command}\n")
        print_usage()
        return 2

    module = importlib.import_module(module_name)
    return module.main(sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
