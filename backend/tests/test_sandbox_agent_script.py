import ast
from pathlib import Path


def _extract_agent_script(source_path: Path) -> str:
    module = ast.parse(source_path.read_text())
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "AGENT_SCRIPT":
                    return ast.literal_eval(node.value)
    raise AssertionError("AGENT_SCRIPT not found in sandbox runner")


def test_embedded_agent_script_compiles():
    script_path = Path(__file__).resolve().parents[1] / "agent_runner" / "sandbox.py"
    agent_script = _extract_agent_script(script_path)
    compile(agent_script, "agent_script.py", "exec")

