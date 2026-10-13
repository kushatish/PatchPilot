"""
Step 3 & 4: Repository search + reading relevant code.

Pure stdlib text search (no embeddings/vector DB needed for V1). We
extract candidate keywords from the issue text, then rank every source
file in the repo by how many of those keywords it mentions -- similar
in spirit to a very simple BM25/grep hybrid.
"""
import ast
import os
import re
from dataclasses import dataclass, field

import config

# Small stopword list tuned for issue text (not a general NLP stopword list).
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "then", "so", "of", "in", "on", "at", "to",
    "for", "with", "when", "while", "this", "that", "it", "its", "as",
    "does", "do", "did", "not", "no", "has", "have", "had", "should",
    "would", "could", "will", "we", "i", "you", "your", "our", "row",
    "expected", "steps", "reproduce", "observe", "fails", "fail", "issue",
}


@dataclass
class FileMatch:
    path: str
    score: int
    matched_keywords: set = field(default_factory=set)


def extract_keywords(issue_title: str, issue_body: str) -> list:
    """Very lightweight keyword extraction: pulls out identifier-like
    tokens (snake_case, camelCase, filenames, quoted strings, words > 3
    chars) from the issue text."""
    text = f"{issue_title}\n{issue_body}"

    keywords = set()

    # Anything that looks like a filename or code identifier.
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}(?:\.py)?", text):
        low = tok.lower().replace(".py", "")
        if low not in _STOPWORDS and len(low) > 2:
            keywords.add(low)

    # Quoted strings/error messages often contain the most specific clues.
    for quoted in re.findall(r"[`'\"]([^`'\"]{3,60})[`'\"]", text):
        for word in re.findall(r"[A-Za-z_]{3,}", quoted):
            if word.lower() not in _STOPWORDS:
                keywords.add(word.lower())

    return sorted(keywords)


def _iter_source_files(repo_path: str):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in config.IGNORED_DIRS]
        for fname in files:
            if os.path.splitext(fname)[1] in config.SOURCE_EXTENSIONS:
                path = os.path.join(root, fname)
                if not os.path.islink(path):
                    yield path


def search_repository(repo_path: str, keywords: list) -> list:
    """Scores every source file by keyword occurrence. Returns a list of
    FileMatch sorted by descending score."""
    matches = []
    for filepath in _iter_source_files(repo_path):
        try:
            with open(filepath, "r", errors="ignore") as f:
                content = f.read().lower()
        except (IOError, OSError):
            continue

        score = sum(8 for kw in keywords if kw in os.path.basename(filepath).lower())
        try:
            tree = ast.parse(content)
            symbols = [n.name for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            score += sum(12 for symbol in symbols if symbol in keywords)
        except SyntaxError:
            pass
        matched = set()
        for kw in keywords:
            count = content.count(kw)
            if count:
                score += count
                matched.add(kw)

        if score > 0:
            rel_path = os.path.relpath(filepath, repo_path)
            matches.append(FileMatch(path=rel_path, score=score, matched_keywords=matched))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def read_relevant_files(repo_path: str, file_matches: list, limit: int = None) -> dict:
    """Reads the top-N matched files' full content (truncated if huge)."""
    limit = limit or config.MAX_FILES_TO_INSPECT
    contents = {}
    for match in file_matches[:limit]:
        full_path = os.path.join(repo_path, match.path)
        try:
            with open(full_path, "r", errors="ignore") as f:
                text = f.read()
        except (IOError, OSError):
            continue
        if len(text) > config.MAX_FILE_CHARS:
            # Prefer a complete relevant top-level definition to an unrelated file prefix.
            try:
                tree = ast.parse(text)
                definitions = [node for node in tree.body
                               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                               and node.name.lower() in match.matched_keywords]
                imports = [ast.get_source_segment(text, node) for node in tree.body
                           if isinstance(node, (ast.Import, ast.ImportFrom))]
                chunks = ["# Selected source excerpts; omitted definitions are not shown."] + imports
                for node in definitions:
                    segment = ast.get_source_segment(text, node)
                    if segment and len("\n\n".join(chunks + [segment])) <= config.MAX_FILE_CHARS:
                        chunks.append(segment)
                text = "\n\n".join(chunks) if len(chunks) > len(imports) + 1 else text[:config.MAX_FILE_CHARS] + "\n# ... truncated ...\n"
            except SyntaxError:
                text = text[:config.MAX_FILE_CHARS] + "\n# ... truncated ...\n"
        contents[match.path] = text
    return contents


def find_related_test_files(repo_path: str, source_file_paths: list) -> list:
    """Given a list of relative source paths, guesses likely test files by
    common pytest naming conventions (test_<name>.py, <name>_test.py, or
    files under a tests/ dir mentioning the module name)."""
    candidates = set()
    all_test_files = [
        os.path.relpath(p, repo_path) for p in _iter_source_files(repo_path)
        if os.path.basename(p).startswith("test_") or os.path.basename(p).endswith("_test.py")
    ]

    module_names = {os.path.splitext(os.path.basename(p))[0] for p in source_file_paths}

    for test_file in all_test_files:
        base = os.path.splitext(os.path.basename(test_file))[0]
        stripped = base.removeprefix("test_").removesuffix("_test")
        if stripped in module_names:
            candidates.add(test_file)

    # Fall back to including all discovered test files if none matched directly
    # (better to run a slightly broader test suite than to run nothing).
    if not candidates:
        candidates.update(all_test_files)

    return sorted(candidates)


def expand_import_context(repo_path: str, contents: dict) -> dict:
    """Follow local imports one hop while keeping the total context bounded."""
    from pathlib import Path
    expanded = dict(contents)
    root = Path(repo_path).resolve()
    for path, source in list(contents.items()):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                bases = [root] if not getattr(node, 'level', 0) else [root / Path(path).parent]
                for base in bases:
                    target = base.joinpath(*module.split('.')).with_suffix('.py')
                    if target.is_file() and not target.is_symlink() and root in target.resolve().parents:
                        rel = str(target.relative_to(root))
                        if rel not in expanded and len(expanded) < config.MAX_FILES_TO_INSPECT * 2:
                            expanded[rel] = target.read_text(errors='replace')[:config.MAX_FILE_CHARS]
    return expanded
