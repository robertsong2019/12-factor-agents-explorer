#!/usr/bin/env python3
"""Find top-level functions in memory_graph.py never referenced by any test file."""
import ast, glob, re

src = open("memory_graph.py", encoding="utf-8").read()
tree = ast.parse(src)
funcs = []
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        funcs.append(node.name)
funcs = sorted({n for n in funcs if not n.startswith("_")})

test_blob = ""
for f in glob.glob("test_*.py"):
    test_blob += open(f, encoding="utf-8").read()

untested = [n for n in funcs if not re.search(r"\b" + re.escape(n) + r"\b", test_blob)]
print(f"top-level funcs: {len(funcs)}, unreferenced in tests: {len(untested)}")
# prefer short ones (pure helpers) — print name + line + length
for n in untested[:40]:
    m = re.search(r"^def " + re.escape(n) + r"\(", src, re.M)
    line = src[: m.start()].count("\n") + 1 if m else -1
    print(f"{n}\tline {line}")
