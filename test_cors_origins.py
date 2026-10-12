"""Checks that the CORS allowlist never admits a credentialed plaintext origin.

Parses main.py instead of importing it, so it runs without the app's dependencies.
"""
import ast
import io

src = io.open("main.py", encoding="utf-8").read()
fn = next(
    n for n in ast.parse(src).body
    if isinstance(n, ast.FunctionDef) and n.name == "_is_credentialed_safe"
)
ns = {}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "main.py", "exec"), ns)
is_safe = ns["_is_credentialed_safe"]

assert is_safe("https://socialraven.online")
assert is_safe("https://www.socialraven.online")
assert is_safe("http://localhost:3000")
assert is_safe("http://127.0.0.1:5173")
assert not is_safe("http://socialraven.online")
assert not is_safe("http://evil.example")
assert not is_safe("*")

print("CORS origin filter OK")
