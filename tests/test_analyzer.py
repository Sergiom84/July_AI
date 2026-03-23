"""Tests for july.analyzer module."""
from __future__ import annotations

import tempfile
from pathlib import Path

from july.analyzer import (
    AnalysisResult,
    analyze_codebase,
    build_directory_tree,
    collect_source_files,
    count_languages,
    detect_code_smells,
    detect_layers,
    extract_imports,
    find_dependency_hotspots,
    generate_proactive_questions,
    generate_suggestions,
    infer_architecture,
)


def _make_project(tmp: Path, files: dict[str, str]) -> Path:
    for rel_path, content in files.items():
        full = tmp / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    return tmp


def test_collect_source_files_finds_python():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            "main.py": "print('hello')\n",
            "lib/utils.py": "def helper(): pass\n",
            "README.md": "# Project\n",
        })
        files = collect_source_files(root)
        py_files = [f for f in files if f.extension == ".py"]
        assert len(py_files) == 2
        assert all(f.lines > 0 for f in py_files)


def test_collect_source_files_ignores_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            "app.py": "x = 1\n",
            "node_modules/pkg/index.js": "module.exports = {}\n",
        })
        files = collect_source_files(root)
        assert all("node_modules" not in f.path for f in files)


def test_count_languages():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            "a.py": "x=1\n",
            "b.py": "y=2\n",
            "c.js": "const z = 3;\n",
        })
        files = collect_source_files(root)
        langs = count_languages(files)
        assert langs["Python"] == 2
        assert langs["JavaScript"] == 1


def test_build_directory_tree():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            "src/main.py": "pass\n",
            "src/utils.py": "pass\n",
            "README.md": "# Hi\n",
        })
        tree = build_directory_tree(root, depth=2)
        assert any("src/" in line for line in tree)


def test_detect_layers():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            "controllers/user.py": "pass\n",
            "services/auth.py": "pass\n",
            "models/user.py": "pass\n",
        })
        files = collect_source_files(root)
        layers = detect_layers(root, files)
        assert "controller" in layers
        assert "service" in layers
        assert "model" in layers


def test_infer_architecture_mvc():
    layers = {"controller": ["controllers"], "model": ["models"]}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pattern, insights = infer_architecture(layers, [], root)
        assert pattern == "mvc"
        assert len(insights) >= 1


def test_infer_architecture_clean():
    layers = {"service": ["services"], "repository": ["repos"], "model": ["models"]}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pattern, insights = infer_architecture(layers, [], root)
        assert pattern == "clean_architecture"


def test_extract_python_imports():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            "app.py": "import os\nfrom pathlib import Path\nfrom . import utils\n",
        })
        files = collect_source_files(root)
        imports = extract_imports(root, files)
        modules = [i.module for i in imports]
        assert "os" in modules
        assert "pathlib" in modules


def test_find_dependency_hotspots_high_fan_out():
    from july.analyzer import ImportInfo, MAX_IMPORTS_PER_FILE
    imports = [
        ImportInfo(source_file="big.py", module=f"mod{i}", names=[])
        for i in range(MAX_IMPORTS_PER_FILE + 5)
    ]
    hotspots = find_dependency_hotspots(imports)
    fan_out = [h for h in hotspots if h["kind"] == "high_fan_out"]
    assert len(fan_out) >= 1
    assert fan_out[0]["file"] == "big.py"


def test_detect_code_smells_large_file():
    with tempfile.TemporaryDirectory() as tmp:
        large_content = "\n".join(f"x_{i} = {i}" for i in range(400))
        root = _make_project(Path(tmp), {"big.py": large_content})
        files = collect_source_files(root)
        smells = detect_code_smells(root, files, [])
        large = [s for s in smells if s.kind == "large_file"]
        assert len(large) >= 1


def test_detect_code_smells_long_function():
    with tempfile.TemporaryDirectory() as tmp:
        lines = ["def long_func():"]
        for i in range(60):
            lines.append(f"    x_{i} = {i}")
        root = _make_project(Path(tmp), {"funcs.py": "\n".join(lines) + "\n"})
        files = collect_source_files(root)
        smells = detect_code_smells(root, files, [])
        long_fn = [s for s in smells if s.kind == "long_function"]
        assert len(long_fn) >= 1


def test_detect_no_tests_smell():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            f"mod{i}.py": f"x = {i}\n" for i in range(6)
        })
        files = collect_source_files(root)
        smells = detect_code_smells(root, files, [])
        no_tests = [s for s in smells if s.kind == "no_tests"]
        assert len(no_tests) == 1


def test_generate_proactive_questions_flat_project():
    questions = generate_proactive_questions(
        arch_pattern="flat",
        layers={},
        smells=[],
        languages={"Python": 20},
        files=[object()] * 20,  # type: ignore
    )
    assert any("capas" in q.lower() or "estructura" in q.lower() for q in questions)


def test_generate_suggestions_no_tests():
    from july.analyzer import CodeSmell
    smells = [CodeSmell(file="(proyecto)", kind="no_tests", detail="", severity="warning")]
    suggestions = generate_suggestions("flat", {}, smells, [], {"Python": 5})
    assert any("test" in s.lower() for s in suggestions)


def test_analyze_codebase_returns_result():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_project(Path(tmp), {
            "main.py": "print('hi')\n",
            "utils.py": "def helper(): return 42\n",
        })
        result = analyze_codebase(root)
        assert isinstance(result, AnalysisResult)
        assert result.source_files == 2
        assert "Python" in result.languages
        d = result.to_dict()
        assert "architecture_pattern" in d
        assert "proactive_questions" in d


def test_analyze_codebase_on_real_project():
    """Smoke test: run analyzer on the actual July repo."""
    repo_root = Path(__file__).resolve().parent.parent
    result = analyze_codebase(repo_root)
    assert result.source_files > 0
    assert "Python" in result.languages
    assert result.architecture_pattern in (
        "flat", "layered_mvc", "clean_architecture", "mvc",
        "frontend_component", "script",
    )
