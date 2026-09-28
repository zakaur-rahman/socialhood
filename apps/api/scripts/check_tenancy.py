"""TR-TEN-04: fail when tenant-safety rules are broken in src/socialhood.

1. SQLAlchemy's ``update``/``delete`` constructs are used only in repositories/ (the scoped
   helpers add the workspace filter; anything else could touch another tenant's rows).
2. ``tenant_bypass_scope`` is used only in webhooks/, jobs/ and auth/ (and defined in
   db/tenancy.py).

Usage: python scripts/check_tenancy.py [root]   (exit code 1 on violations)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

WRITE_CONSTRUCTS = {"update", "delete"}
WRITES_ALLOWED_IN = ("repositories/",)
BYPASS_ALLOWED_IN = ("webhooks/", "jobs/", "auth/", "db/tenancy.py")


def _allowed(rel: str, prefixes: tuple[str, ...]) -> bool:
    return any(rel == p or rel.startswith(p) for p in prefixes)


def check_source(rel: str, source: str) -> list[str]:
    """Return violations for one file. ``rel`` is the path relative to src/socialhood."""
    rel = rel.replace("\\", "/")
    tree = ast.parse(source, filename=rel)
    problems: list[str] = []
    sqlalchemy_modules: set[str] = set()  # local names bound to sqlalchemy modules

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy."):
                    sqlalchemy_modules.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "sqlalchemy" or node.module.startswith("sqlalchemy."):
                for alias in node.names:
                    if alias.name in WRITE_CONSTRUCTS and not _allowed(rel, WRITES_ALLOWED_IN):
                        problems.append(
                            f"{rel}:{node.lineno}: SQLAlchemy {alias.name}() imported outside "
                            "repositories/; use scoped_update/scoped_delete (TR-TEN-04)"
                        )
            for alias in node.names:
                if alias.name == "tenant_bypass_scope" and not _allowed(rel, BYPASS_ALLOWED_IN):
                    problems.append(
                        f"{rel}:{node.lineno}: tenant_bypass_scope used outside webhooks/, "
                        "jobs/ and auth/ (TR-TEN-04)"
                    )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in WRITE_CONSTRUCTS
            and isinstance(node.value, ast.Name)
            and node.value.id in sqlalchemy_modules
            and not _allowed(rel, WRITES_ALLOWED_IN)
        ):
            problems.append(
                f"{rel}:{node.lineno}: {node.value.id}.{node.attr}() used outside repositories/ "
                "(TR-TEN-04)"
            )
        if (
            isinstance(node, ast.Name | ast.Attribute)
            and (node.id if isinstance(node, ast.Name) else node.attr) == "tenant_bypass_scope"
            and not _allowed(rel, BYPASS_ALLOWED_IN)
        ):
            problems.append(
                f"{rel}:{node.lineno}: tenant_bypass_scope used outside webhooks/, jobs/ and "
                "auth/ (TR-TEN-04)"
            )
    return sorted(set(problems))


def check_tree(root: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        problems.extend(check_source(rel, path.read_text(encoding="utf-8")))
    return problems


def main() -> int:
    default = Path(__file__).resolve().parents[1] / "src" / "socialhood"
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    problems = check_tree(root)
    for line in problems:
        print(line)
    if problems:
        print(f"{len(problems)} tenancy rule violation(s)")
        return 1
    print("Tenancy rules: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
