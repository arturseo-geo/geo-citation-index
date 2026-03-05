import ast
import re
import sys
from pathlib import Path


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def parse_routes(main_py: Path) -> set[str]:
    tree = ast.parse(main_py.read_text(encoding="utf-8"))
    routes = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not isinstance(func, ast.Attribute):
                continue
            if not isinstance(func.value, ast.Name) or func.value.id != "app":
                continue
            method = func.attr.lower()
            if method not in HTTP_METHODS:
                continue
            if not dec.args:
                continue
            first_arg = dec.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                path = first_arg.value.strip()
                routes.add(f"{method.upper()} {path}")
    return routes


def parse_models(db_py: Path) -> set[str]:
    tree = ast.parse(db_py.read_text(encoding="utf-8"))
    models = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        is_model = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "Base":
                is_model = True
            elif isinstance(base, ast.Attribute) and base.attr == "Base":
                is_model = True
        if is_model:
            models.add(node.name)
    return models


def parse_endpoint_index(md_path: Path) -> set[str]:
    pattern = re.compile(r"^\s*-\s*`?(GET|POST|PUT|PATCH|DELETE)\s+(/[^`\s]+)`?\s*$")
    found = set()
    for line in md_path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            found.add(f"{m.group(1)} {m.group(2)}")
    return found


def parse_model_index(md_path: Path) -> set[str]:
    pattern = re.compile(r"^\s*-\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*$")
    found = set()
    for line in md_path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            found.add(m.group(1))
    return found


def print_diff(title: str, missing: set[str], extra: set[str]) -> None:
    print(f"\n[{title}]")
    if missing:
        print("Missing in docs:")
        for item in sorted(missing):
            print(f"  - {item}")
    if extra:
        print("Stale in docs (not in code):")
        for item in sorted(extra):
            print(f"  - {item}")
    if not missing and not extra:
        print("OK")


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    main_py = repo / "app" / "backend" / "main.py"
    db_py = repo / "app" / "models" / "db.py"
    endpoint_index = repo / "docs" / "appendices" / "endpoint-index.md"
    model_index = repo / "docs" / "appendices" / "model-index.md"

    for path in [main_py, db_py, endpoint_index, model_index]:
        if not path.exists():
            print(f"Required file missing: {path}")
            return 2

    code_routes = parse_routes(main_py)
    docs_routes = parse_endpoint_index(endpoint_index)
    code_models = parse_models(db_py)
    docs_models = parse_model_index(model_index)

    missing_routes = code_routes - docs_routes
    extra_routes = docs_routes - code_routes
    missing_models = code_models - docs_models
    extra_models = docs_models - code_models

    print_diff("Endpoint coverage", missing_routes, extra_routes)
    print_diff("Model coverage", missing_models, extra_models)

    if missing_routes or extra_routes or missing_models or extra_models:
        return 1

    print("\nDocs integrity check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
