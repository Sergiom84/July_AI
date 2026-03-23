"""Deep code analyzer for July architect copilot.

Goes beyond surface-level inspection (READMEs, manifests) to analyze
actual source code: directory structure, imports, dependency graphs,
architectural patterns, and code smells.
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Ignore patterns ──────────────────────────────────────────────
IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".next", ".nuxt", "dist", "build", "out", ".output",
    "target", "vendor", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "coverage", ".coverage", "htmlcov",
    ".idea", ".vscode", ".vs", "egg-info",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll",
    ".lock", ".map", ".min.js", ".min.css",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2",
    ".db", ".sqlite", ".sqlite3",
}

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".rb", ".php",
    ".java", ".kt", ".cs", ".cpp", ".c", ".h",
    ".vue", ".svelte",
}

# ── Architecture pattern detection ───────────────────────────────
LAYER_PATTERNS = {
    "controllers": "controller",
    "routes": "controller",
    "handlers": "controller",
    "api": "controller",
    "services": "service",
    "usecases": "service",
    "use_cases": "service",
    "application": "service",
    "models": "model",
    "entities": "model",
    "domain": "model",
    "schemas": "model",
    "repositories": "repository",
    "repos": "repository",
    "adapters": "repository",
    "infrastructure": "repository",
    "views": "view",
    "templates": "view",
    "components": "view",
    "pages": "view",
    "middleware": "middleware",
    "utils": "utility",
    "helpers": "utility",
    "lib": "utility",
    "config": "config",
    "tests": "test",
    "test": "test",
    "__tests__": "test",
    "specs": "test",
}

# ── SOLID / smell thresholds ─────────────────────────────────────
MAX_FILE_LINES = 300
MAX_FUNCTION_LINES = 50
MAX_IMPORTS_PER_FILE = 15
MAX_PARAMS_PER_FUNCTION = 5


@dataclass(slots=True)
class FileInfo:
    path: str
    extension: str
    lines: int
    size_bytes: int


@dataclass(slots=True)
class ImportInfo:
    source_file: str
    module: str
    names: list[str]


@dataclass(slots=True)
class CodeSmell:
    file: str
    kind: str
    detail: str
    severity: str  # "info", "warning", "critical"


@dataclass(slots=True)
class ArchitectureInsight:
    pattern: str
    confidence: float
    detail: str
    suggestion: str


@dataclass(slots=True)
class AnalysisResult:
    repo_root: str
    total_files: int
    source_files: int
    languages: dict[str, int]
    directory_tree: list[str]
    layers_detected: dict[str, list[str]]
    architecture_pattern: str
    architecture_insights: list[ArchitectureInsight]
    imports: list[ImportInfo]
    dependency_hotspots: list[dict[str, Any]]
    code_smells: list[CodeSmell]
    proactive_questions: list[str]
    suggestions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "total_files": self.total_files,
            "source_files": self.source_files,
            "languages": self.languages,
            "directory_tree": self.directory_tree,
            "layers_detected": self.layers_detected,
            "architecture_pattern": self.architecture_pattern,
            "architecture_insights": [
                {"pattern": i.pattern, "confidence": i.confidence,
                 "detail": i.detail, "suggestion": i.suggestion}
                for i in self.architecture_insights
            ],
            "dependency_hotspots": self.dependency_hotspots,
            "code_smells": [
                {"file": s.file, "kind": s.kind, "detail": s.detail, "severity": s.severity}
                for s in self.code_smells
            ],
            "proactive_questions": self.proactive_questions,
            "suggestions": self.suggestions,
        }


# ── Main entry point ─────────────────────────────────────────────

def analyze_codebase(repo_root: Path, *, max_files: int = 500) -> AnalysisResult:
    """Run a deep analysis of the codebase at repo_root."""
    files = collect_source_files(repo_root, max_files=max_files)
    languages = count_languages(files)
    tree = build_directory_tree(repo_root, depth=3)
    layers = detect_layers(repo_root, files)
    arch_pattern, arch_insights = infer_architecture(layers, files, repo_root)
    imports = extract_imports(repo_root, files)
    hotspots = find_dependency_hotspots(imports)
    smells = detect_code_smells(repo_root, files, imports)
    questions = generate_proactive_questions(arch_pattern, layers, smells, languages, files)
    suggestions = generate_suggestions(arch_pattern, layers, smells, hotspots, languages)

    return AnalysisResult(
        repo_root=str(repo_root),
        total_files=len(list(iter_all_files(repo_root, max_files=max_files * 2))),
        source_files=len(files),
        languages=languages,
        directory_tree=tree,
        layers_detected=layers,
        architecture_pattern=arch_pattern,
        architecture_insights=arch_insights,
        imports=imports,
        dependency_hotspots=hotspots,
        code_smells=smells,
        proactive_questions=questions,
        suggestions=suggestions,
    )


# ── File collection ──────────────────────────────────────────────

def iter_all_files(repo_root: Path, *, max_files: int = 1000) -> list[FileInfo]:
    result: list[FileInfo] = []
    count = 0
    for path in _walk_files(repo_root):
        if count >= max_files:
            break
        try:
            stat = path.stat()
            result.append(FileInfo(
                path=str(path.relative_to(repo_root)),
                extension=path.suffix.lower(),
                lines=0,
                size_bytes=stat.st_size,
            ))
            count += 1
        except OSError:
            continue
    return result


def collect_source_files(repo_root: Path, *, max_files: int = 500) -> list[FileInfo]:
    result: list[FileInfo] = []
    for path in _walk_files(repo_root):
        if len(result) >= max_files:
            break
        ext = path.suffix.lower()
        if ext not in SOURCE_EXTENSIONS:
            continue
        if ext in IGNORE_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            result.append(FileInfo(
                path=str(path.relative_to(repo_root)),
                extension=ext,
                lines=lines,
                size_bytes=len(content.encode("utf-8")),
            ))
        except OSError:
            continue
    return result


def _walk_files(repo_root: Path):
    try:
        for entry in sorted(repo_root.iterdir()):
            if entry.name.startswith(".") and entry.name != ".":
                if entry.name not in (".github", ".gitlab"):
                    continue
            if entry.is_dir():
                if entry.name.lower() in IGNORE_DIRS:
                    continue
                yield from _walk_files(entry)
            elif entry.is_file():
                if entry.suffix.lower() not in IGNORE_EXTENSIONS:
                    yield entry
    except PermissionError:
        pass


# ── Language detection ───────────────────────────────────────────

LANG_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React JSX", ".tsx": "React TSX",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".java": "Java", ".kt": "Kotlin", ".cs": "C#",
    ".cpp": "C++", ".c": "C", ".h": "C/C++ Header",
    ".vue": "Vue", ".svelte": "Svelte",
}


def count_languages(files: list[FileInfo]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for f in files:
        lang = LANG_MAP.get(f.extension)
        if lang:
            counter[lang] += 1
    return dict(counter.most_common())


# ── Directory tree ───────────────────────────────────────────────

def build_directory_tree(repo_root: Path, *, depth: int = 3) -> list[str]:
    lines: list[str] = []
    _tree_recurse(repo_root, repo_root, lines, depth=depth, prefix="")
    return lines


def _tree_recurse(path: Path, root: Path, lines: list[str], *, depth: int, prefix: str) -> None:
    if depth <= 0:
        return
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return

    visible = [
        e for e in entries
        if not (e.name.startswith(".") and e.name not in (".github", ".gitlab"))
        and e.name.lower() not in IGNORE_DIRS
    ]

    for i, entry in enumerate(visible[:30]):
        connector = "└── " if i == len(visible[:30]) - 1 else "├── "
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{prefix}{connector}{entry.name}{suffix}")
        if entry.is_dir():
            ext = "    " if i == len(visible[:30]) - 1 else "│   "
            _tree_recurse(entry, root, lines, depth=depth - 1, prefix=prefix + ext)


# ── Layer detection ──────────────────────────────────────────────

def detect_layers(repo_root: Path, files: list[FileInfo]) -> dict[str, list[str]]:
    layers: dict[str, list[str]] = defaultdict(list)

    # Check top-level and src/ directories
    for path in repo_root.iterdir():
        if path.is_dir():
            name = path.name.lower()
            if name in LAYER_PATTERNS:
                layers[LAYER_PATTERNS[name]].append(path.name)

    src = repo_root / "src"
    if src.is_dir():
        for path in src.iterdir():
            if path.is_dir():
                name = path.name.lower()
                if name in LAYER_PATTERNS:
                    layers[LAYER_PATTERNS[name]].append(f"src/{path.name}")

    # Also check file paths for patterns
    for f in files:
        parts = Path(f.path).parts
        for part in parts[:-1]:
            lower = part.lower()
            if lower in LAYER_PATTERNS:
                layer = LAYER_PATTERNS[lower]
                dir_path = str(Path(*parts[:parts.index(part) + 1]))
                if dir_path not in layers[layer]:
                    layers[layer].append(dir_path)

    return dict(layers)


# ── Architecture inference ───────────────────────────────────────

def infer_architecture(
    layers: dict[str, list[str]],
    files: list[FileInfo],
    repo_root: Path,
) -> tuple[str, list[ArchitectureInsight]]:
    insights: list[ArchitectureInsight] = []
    layer_types = set(layers.keys())

    # Clean Architecture / Hexagonal
    if {"service", "repository", "model"} <= layer_types:
        if "controller" in layer_types:
            pattern = "layered_mvc"
            insights.append(ArchitectureInsight(
                pattern="Layered / MVC",
                confidence=0.85,
                detail=f"Capas detectadas: {', '.join(sorted(layer_types))}",
                suggestion="Verifica que los controllers no accedan directamente a repositories sin pasar por services.",
            ))
        else:
            pattern = "clean_architecture"
            insights.append(ArchitectureInsight(
                pattern="Clean Architecture",
                confidence=0.75,
                detail=f"Capas core detectadas: {', '.join(sorted(layer_types))}",
                suggestion="Asegurate de que el domain/models no importe de infrastructure/adapters.",
            ))
    elif {"controller", "model"} <= layer_types:
        pattern = "mvc"
        insights.append(ArchitectureInsight(
            pattern="MVC",
            confidence=0.7,
            detail="Controllers y models detectados sin capa de services explicita.",
            suggestion="Considera extraer logica de negocio de los controllers a una capa de services.",
        ))
    elif {"view", "model"} <= layer_types or {"view", "controller"} <= layer_types:
        pattern = "frontend_component"
        insights.append(ArchitectureInsight(
            pattern="Frontend componentizado",
            confidence=0.7,
            detail="Estructura basada en componentes/vistas.",
            suggestion="Verifica que la logica de estado no este acoplada a los componentes de presentacion.",
        ))
    elif len(files) <= 10:
        pattern = "script"
        insights.append(ArchitectureInsight(
            pattern="Script / utilidad",
            confidence=0.8,
            detail=f"Proyecto pequeno con {len(files)} archivos fuente.",
            suggestion="Para proyectos pequenos, mantener la simplicidad es una virtud. No sobrearquitectures.",
        ))
    else:
        pattern = "flat"
        insights.append(ArchitectureInsight(
            pattern="Estructura plana",
            confidence=0.6,
            detail="No se detectan capas arquitectonicas claras.",
            suggestion="Si el proyecto crece, considera separar en capas (domain, services, infrastructure).",
        ))

    # Check for monorepo
    workspace_indicators = [
        repo_root / "packages",
        repo_root / "apps",
        repo_root / "libs",
    ]
    if any(p.is_dir() for p in workspace_indicators):
        insights.append(ArchitectureInsight(
            pattern="Monorepo",
            confidence=0.8,
            detail="Detectados directorios packages/, apps/ o libs/.",
            suggestion="Verifica que las dependencias entre paquetes esten bien definidas y no haya imports circulares.",
        ))

    # Check for Docker
    if (repo_root / "Dockerfile").exists() or (repo_root / "docker-compose.yml").exists():
        insights.append(ArchitectureInsight(
            pattern="Containerizado",
            confidence=0.9,
            detail="Dockerfile o docker-compose detectado.",
            suggestion="Revisa que los multi-stage builds esten optimizados y no copien archivos innecesarios.",
        ))

    return pattern, insights


# ── Import extraction ────────────────────────────────────────────

def extract_imports(repo_root: Path, files: list[FileInfo]) -> list[ImportInfo]:
    """Extract import statements from Python and JS/TS files."""
    imports: list[ImportInfo] = []

    for f in files:
        if f.extension == ".py":
            imports.extend(_extract_python_imports(repo_root, f.path))
        elif f.extension in (".js", ".ts", ".jsx", ".tsx"):
            imports.extend(_extract_js_imports(f.path, repo_root))

    return imports


def _extract_python_imports(repo_root: Path, rel_path: str) -> list[ImportInfo]:
    result: list[ImportInfo] = []
    full_path = repo_root / rel_path
    try:
        source = full_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=rel_path)
    except (SyntaxError, OSError):
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append(ImportInfo(
                    source_file=rel_path,
                    module=alias.name,
                    names=[alias.asname or alias.name],
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            result.append(ImportInfo(
                source_file=rel_path,
                module=module,
                names=names,
            ))
    return result


_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+\w+|\w+))*\s+from\s+)?['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)


def _extract_js_imports(rel_path: str, repo_root: Path) -> list[ImportInfo]:
    result: list[ImportInfo] = []
    full_path = repo_root / rel_path
    try:
        content = full_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return result

    for match in _JS_IMPORT_RE.finditer(content):
        module = match.group(1) or match.group(2)
        if module:
            result.append(ImportInfo(
                source_file=rel_path,
                module=module,
                names=[],
            ))
    return result


# ── Dependency hotspots ──────────────────────────────────────────

def find_dependency_hotspots(imports: list[ImportInfo]) -> list[dict[str, Any]]:
    """Find files that are imported the most (high fan-in) and files that import the most (high fan-out)."""
    imported_by: Counter[str] = Counter()
    imports_from: Counter[str] = Counter()

    for imp in imports:
        imports_from[imp.source_file] += 1
        if not imp.module.startswith(".") and "." in imp.module:
            # Internal module reference
            imported_by[imp.module] += 1
        elif imp.module.startswith("."):
            imported_by[f"{imp.source_file}->{imp.module}"] += 1

    hotspots: list[dict[str, Any]] = []

    # High fan-out (files importing too many things)
    for path, count in imports_from.most_common(5):
        if count > MAX_IMPORTS_PER_FILE:
            hotspots.append({
                "file": path,
                "kind": "high_fan_out",
                "count": count,
                "detail": f"Importa {count} modulos. Puede indicar responsabilidades mezcladas.",
            })

    # High fan-in (modules imported by many files)
    for module, count in imported_by.most_common(5):
        if count >= 5:
            hotspots.append({
                "module": module,
                "kind": "high_fan_in",
                "count": count,
                "detail": f"Importado por {count} archivos. Cambios aqui tienen alto impacto.",
            })

    return hotspots


# ── Code smell detection ─────────────────────────────────────────

def detect_code_smells(
    repo_root: Path,
    files: list[FileInfo],
    imports: list[ImportInfo],
) -> list[CodeSmell]:
    smells: list[CodeSmell] = []

    for f in files:
        # Large files
        if f.lines > MAX_FILE_LINES:
            severity = "critical" if f.lines > MAX_FILE_LINES * 3 else "warning"
            smells.append(CodeSmell(
                file=f.path,
                kind="large_file",
                detail=f"{f.lines} lineas. Considera dividirlo en modulos mas pequenos.",
                severity=severity,
            ))

        # Python-specific smells
        if f.extension == ".py":
            smells.extend(_detect_python_smells(repo_root, f))

    # No tests detected
    test_files = [f for f in files if "test" in f.path.lower()]
    if not test_files and len(files) > 5:
        smells.append(CodeSmell(
            file="(proyecto)",
            kind="no_tests",
            detail="No se detectan archivos de test. Los tests son esenciales para mantener calidad.",
            severity="warning",
        ))

    return smells[:20]  # Cap at 20 smells


def _detect_python_smells(repo_root: Path, f: FileInfo) -> list[CodeSmell]:
    smells: list[CodeSmell] = []
    full_path = repo_root / f.path
    try:
        source = full_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=f.path)
    except (SyntaxError, OSError):
        return smells

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Long functions
            if hasattr(node, "end_lineno") and node.end_lineno:
                func_lines = node.end_lineno - node.lineno
                if func_lines > MAX_FUNCTION_LINES:
                    smells.append(CodeSmell(
                        file=f.path,
                        kind="long_function",
                        detail=f"Funcion '{node.name}' tiene {func_lines} lineas (max recomendado: {MAX_FUNCTION_LINES}).",
                        severity="warning",
                    ))

            # Too many parameters
            params = node.args
            param_count = len(params.args) + len(params.kwonlyargs)
            if params.vararg:
                param_count += 1
            if params.kwarg:
                param_count += 1
            # Discount 'self' and 'cls'
            if params.args and params.args[0].arg in ("self", "cls"):
                param_count -= 1

            if param_count > MAX_PARAMS_PER_FUNCTION:
                smells.append(CodeSmell(
                    file=f.path,
                    kind="too_many_params",
                    detail=f"Funcion '{node.name}' tiene {param_count} parametros. Considera usar un dataclass o dict.",
                    severity="info",
                ))

        # God class detection (classes with too many methods)
        if isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if len(methods) > 15:
                smells.append(CodeSmell(
                    file=f.path,
                    kind="god_class",
                    detail=f"Clase '{node.name}' tiene {len(methods)} metodos. Considera dividir responsabilidades.",
                    severity="warning",
                ))

    return smells


# ── Proactive questions ──────────────────────────────────────────

def generate_proactive_questions(
    arch_pattern: str,
    layers: dict[str, list[str]],
    smells: list[CodeSmell],
    languages: dict[str, int],
    files: list[FileInfo],
) -> list[str]:
    questions: list[str] = []

    if arch_pattern == "flat" and len(files) > 15:
        questions.append(
            "El proyecto tiene bastantes archivos pero sin estructura clara de capas. "
            "Estas pensando en reorganizarlo o prefieres mantenerlo plano?"
        )

    if "service" not in layers and "controller" in layers:
        questions.append(
            "Veo controllers pero no una capa de services. "
            "La logica de negocio esta directamente en los controllers?"
        )

    if "test" not in layers and len(files) > 5:
        questions.append(
            "No detecto tests en el proyecto. Quieres que te sugiera una estrategia de testing?"
        )

    critical_smells = [s for s in smells if s.severity == "critical"]
    if critical_smells:
        questions.append(
            f"He detectado {len(critical_smells)} problemas criticos de estructura. "
            "Quieres que los revisemos antes de seguir trabajando?"
        )

    if len(languages) > 3:
        questions.append(
            f"El proyecto usa {len(languages)} lenguajes diferentes. "
            "Es intencionado o hay archivos que deberian limpiarse?"
        )

    return questions[:3]


# ── Suggestions ──────────────────────────────────────────────────

def generate_suggestions(
    arch_pattern: str,
    layers: dict[str, list[str]],
    smells: list[CodeSmell],
    hotspots: list[dict[str, Any]],
    languages: dict[str, int],
) -> list[str]:
    suggestions: list[str] = []

    # Architecture suggestions
    if arch_pattern == "flat" and sum(languages.values()) > 15:
        suggestions.append(
            "Considera organizar en capas: domain/ para modelos y logica pura, "
            "services/ para casos de uso, infrastructure/ para adaptadores externos."
        )

    if arch_pattern == "mvc" and "service" not in layers:
        suggestions.append(
            "Patron MVC detectado sin capa de servicios. "
            "Extraer logica de controllers a services mejora testabilidad y reutilizacion."
        )

    # Smell-based suggestions
    large_files = [s for s in smells if s.kind == "large_file"]
    if large_files:
        suggestions.append(
            f"Hay {len(large_files)} archivos que superan {MAX_FILE_LINES} lineas. "
            "Archivos mas pequenos son mas faciles de entender, testear y mantener."
        )

    god_classes = [s for s in smells if s.kind == "god_class"]
    if god_classes:
        suggestions.append(
            "Se detectan clases con muchos metodos (God Class). "
            "Aplica el Principio de Responsabilidad Unica: cada clase deberia tener una sola razon para cambiar."
        )

    # Hotspot suggestions
    high_fan_out = [h for h in hotspots if h["kind"] == "high_fan_out"]
    if high_fan_out:
        suggestions.append(
            "Algunos archivos importan demasiados modulos. "
            "Esto puede indicar que mezclan responsabilidades o que falta una capa de abstraccion."
        )

    no_tests = [s for s in smells if s.kind == "no_tests"]
    if no_tests:
        suggestions.append(
            "No hay tests detectados. Empieza por testear la logica de negocio critica "
            "y los edge cases que mas te han fallado."
        )

    return suggestions[:5]
