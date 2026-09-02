from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import time
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


APP_NAME = "Tidy"
APP_VERSION = "1.2.1"
CONTENT_LIMIT = 96 * 1024
INSPECTION_FILE_LIMIT = 200

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".svg", ".avif"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
DOCUMENT_EXT = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".pages", ".xls", ".xlsx", ".csv", ".numbers", ".ppt", ".pptx", ".key", ".json", ".log"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
APP_EXT = {".exe", ".msi", ".dmg", ".pkg", ".deb", ".appimage", ".apk"}
SYSTEM_EXT = {".sys", ".dll", ".drv", ".efi", ".mui", ".cpl", ".ocx"}
TEXT_EXT = {".txt", ".md", ".csv", ".json", ".log", ".rtf"}
OOXML_EXT = {".docx", ".pptx", ".xlsx", ".odt"}

DEFAULT_RULES = {
    "work": "work, client, project, meeting, report, invoice, campaign, launch, office, brief, design, proposal, contract, quarter, deadline, stakeholder, roadmap, budget, revenue, deliverable, q1, q2, q3, q4",
    "personal": "personal, family, recipe, holiday, vacation, passport, medical, health, tax, resume, cv, wedding, birthday, school, travel, home, rent, insurance",
    "video_edits": "edit, edited, cut, draft, final, render, export, premiere, resolve, timeline, reel",
    "presentations": "presentation, present, slide, slides, deck, keynote, webinar, pitch, demo",
    "screenshots": "screenshot, screen shot, screen-shot, snipping, capture",
    "group_documents": True,
}

FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF


@dataclass
class PlannedMove:
    source: str
    destination_folder: str
    destination: str
    category: str
    name: str
    reason: str


@dataclass
class ScanResult:
    folder: str
    moves: list[PlannedMove]
    skipped_protected: int
    inspected: int


def local_app_data() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME


def history_file() -> Path:
    return local_app_data() / "history.json"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_as_admin() -> bool:
    import sys

    executable = sys.executable
    parameters = " ".join(f'"{item}"' for item in sys.argv[1:])
    if not getattr(sys, "frozen", False):
        parameters = f'"{Path(__file__).with_name("app.py")}" {parameters}'.strip()
    try:
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, None, 1)
        return result > 32
    except Exception:
        return False


def attributes(path: Path) -> int:
    try:
        return int(ctypes.windll.kernel32.GetFileAttributesW(str(path)))
    except Exception:
        return 0


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def critical_roots() -> list[Path]:
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")),
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    ]
    return [item.resolve() for item in candidates if item.exists()]


def validate_folder(folder: Path) -> Path:
    resolved = folder.resolve()
    if resolved.parent == resolved:
        raise ValueError("Choose a specific folder, not an entire drive.")
    if resolved == Path.home().resolve():
        raise ValueError("Choose a folder inside your profile, not your entire user profile.")
    if any(is_relative_to(resolved, root) for root in critical_roots()):
        raise ValueError("Windows and Program Files stay shielded because moving their contents can prevent Windows from starting.")
    return resolved


def document_group_key(name: str) -> str | None:
    tokens = [token for token in re.split(r"[\s_\-()[\]]+", Path(name).stem) if token and not re.fullmatch(r"v?\d+(\.\d+)*", token, re.I)]
    return " ".join(tokens[:2]).lower() if len(tokens) >= 2 else None


def _strip_xml(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value))[:CONTENT_LIMIT]


def inspect_content(path: Path) -> str:
    """Read only a small local excerpt. Nothing is uploaded or persisted."""
    if path.stat().st_size > 64 * 1024 * 1024:
        return ""
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            return path.read_bytes()[:CONTENT_LIMIT].decode("utf-8", errors="ignore")
        if ext in OOXML_EXT:
            with zipfile.ZipFile(path) as archive:
                parts: list[str] = []
                for member in archive.namelist():
                    if not member.endswith(".xml") or not any(prefix in member for prefix in ("word/", "ppt/slides/", "xl/sharedStrings", "content.xml")):
                        continue
                    parts.append(_strip_xml(archive.read(member)[:CONTENT_LIMIT].decode("utf-8", errors="ignore")))
                    if sum(map(len, parts)) >= CONTENT_LIMIT:
                        break
                return " ".join(parts)[:CONTENT_LIMIT]
        if ext == ".pdf":
            raw = path.read_bytes()[:CONTENT_LIMIT]
            return " ".join(chunk.decode("latin-1", errors="ignore") for chunk in re.findall(rb"[A-Za-z][A-Za-z0-9 ,.'()/_-]{5,}", raw))[:CONTENT_LIMIT]
    except (OSError, zipfile.BadZipFile):
        return ""
    return ""


def _matches(text: str, key: str, rules: dict | None) -> bool:
    active = rules or DEFAULT_RULES
    words = [item.strip() for item in str(active.get(key, DEFAULT_RULES[key])).split(",") if item.strip()]
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.I) for word in words)


def _document_destination(name: str, content: str, groups: Counter[str], rules: dict | None = None) -> tuple[Path, str]:
    ext = Path(name).suffix.lower()
    combined = f"{name} {content[:CONTENT_LIMIT]}"
    key = document_group_key(name)
    if bool((rules or DEFAULT_RULES).get("group_documents", True)) and key and groups[key] > 1:
        child = Path("Grouped") / key.title()
        reason = f"Matches the {key.title()} document set"
    elif ext in {".ppt", ".pptx", ".key"}:
        child, reason = Path("Presentations"), "Presentation file type"
    elif ext in {".xls", ".xlsx", ".csv", ".numbers"}:
        child, reason = Path("Spreadsheets"), "Spreadsheet file type"
    elif ext == ".pdf":
        child, reason = Path("PDFs"), "PDF file type"
    else:
        child, reason = Path("Text & Word"), "Document file type"

    if content and _matches(combined, "work", rules):
        return Path("Work") / child, f"Local content suggests work • {reason.lower()}"
    if content and _matches(combined, "personal", rules):
        return Path("Personal") / child, f"Local content suggests personal • {reason.lower()}"
    return child, reason


def classify(path: Path, root: Path, groups: Counter[str], content: str = "", rules: dict | None = None) -> tuple[Path, str, str]:
    ext = path.suffix.lower()
    name = path.name
    root_name = root.name.lower()
    if ext in IMAGE_EXT:
        screenshot = _matches(name, "screenshots", rules) or "screenshot" in root_name
        if screenshot:
            child = "Work" if _matches(name, "work", rules) else "Personal"
            destination = Path(child) if "screenshot" in root_name else Path("Screenshots") / child
            return destination, "Pictures", f"Screenshot filename suggests {child.lower()}"
        return Path("Pictures"), "Pictures", "Image file type"
    if ext in VIDEO_EXT:
        child = "Presentations" if _matches(name, "presentations", rules) else "Edits" if _matches(name, "video_edits", rules) else "Media"
        destination = Path(child) if "video" in root_name else Path("Videos") / child
        return destination, "Videos", f"Video filename suggests {child.lower()}"
    if ext in DOCUMENT_EXT:
        child, reason = _document_destination(name, content, groups, rules)
        return (child if "document" in root_name else Path("Documents") / child), "Documents", reason
    if ext in AUDIO_EXT:
        return Path("Audio"), "Audio", "Audio file type"
    if ext in ARCHIVE_EXT:
        return Path("Archives"), "Archives", "Archive file type"
    if ext in APP_EXT:
        return Path("Apps & Installers"), "Apps", "Installer or application file type"
    return Path("Other"), "Other", "No matching type rule"


def unique_path(destination: Path, *, restored: bool = False) -> Path:
    if not destination.exists():
        return destination
    suffix = destination.suffix
    stem = destination.stem
    marker = " restored" if restored else ""
    index = 2
    while True:
        candidate = destination.with_name(f"{stem}{marker} ({index}){suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def scan_folder(folder: Path, include_hidden: bool = False, deep_inspect: bool = False, progress: Callable[[int, int, str], None] | None = None, rules: dict | None = None) -> ScanResult:
    root = validate_folder(folder)
    try:
        entries = list(root.iterdir())
    except PermissionError as error:
        raise PermissionError("Windows denied access. Restart Tidy as administrator and try again.") from error

    eligible: list[Path] = []
    skipped = 0
    for path in entries:
        try:
            attrs = attributes(path)
            if not path.is_file() or path.is_symlink() or attrs == INVALID_FILE_ATTRIBUTES or attrs & (FILE_ATTRIBUTE_SYSTEM | FILE_ATTRIBUTE_REPARSE_POINT) or path.suffix.lower() in SYSTEM_EXT:
                if path.is_file():
                    skipped += 1
                continue
            if not include_hidden and (attrs & FILE_ATTRIBUTE_HIDDEN or path.name.startswith(".")):
                continue
            eligible.append(path)
        except OSError:
            skipped += 1

    groups = Counter(filter(None, (document_group_key(path.name) for path in eligible if path.suffix.lower() in DOCUMENT_EXT)))
    moves: list[PlannedMove] = []
    inspected = 0
    total = len(eligible)
    for index, source in enumerate(eligible, start=1):
        content = ""
        if deep_inspect and inspected < INSPECTION_FILE_LIMIT and source.suffix.lower() in DOCUMENT_EXT:
            content = inspect_content(source)
            inspected += bool(content)
        relative, category, reason = classify(source, root, groups, content, rules)
        destination = unique_path(root / relative / source.name)
        moves.append(PlannedMove(str(source), str(relative), str(destination), category, source.name, reason))
        if progress:
            progress(index, total, source.name)
    return ScanResult(str(root), moves, skipped, inspected)


def _save_history(folder: Path, moves: list[PlannedMove]) -> None:
    history_file().parent.mkdir(parents=True, exist_ok=True)
    history_file().write_text(json.dumps({"folder": str(folder), "created_at": datetime.now().isoformat(), "moves": [asdict(move) for move in moves]}, indent=2), encoding="utf-8")


def load_history() -> tuple[Path | None, list[PlannedMove]]:
    try:
        payload = json.loads(history_file().read_text(encoding="utf-8"))
        return Path(payload["folder"]), [PlannedMove(**item) for item in payload["moves"]]
    except Exception:
        return None, []


def refresh_folder_dates(root: Path, completed: list[PlannedMove]) -> None:
    """Give used destination folders one finish time, without changing file dates."""
    folders: set[Path] = set()
    for move in completed:
        current = Path(move.destination).resolve().parent
        while current != root and is_relative_to(current, root):
            folders.add(current)
            current = current.parent
    finished_ns = time.time_ns()
    for folder in sorted(folders, key=lambda path: (-len(path.parts), str(path))):
        if not is_relative_to(folder, root):
            raise ValueError(f"Unsafe folder timestamp target rejected: {folder}")
        try:
            os.utime(folder, ns=(folder.stat().st_atime_ns, finished_ns))
        except OSError as error:
            raise OSError(f"Files were moved, but Windows could not update the date of “{folder.name}”. Undo is still available.") from error


def execute_plan(folder: Path, plan: list[PlannedMove], progress: Callable[[int, int, str], None] | None = None) -> list[PlannedMove]:
    root = validate_folder(folder)
    completed: list[PlannedMove] = []
    total = len(plan)
    for index, move in enumerate(plan, start=1):
        source = Path(move.source).resolve()
        if source.parent != root or not is_relative_to(source, root):
            raise ValueError(f"Unsafe source rejected: {move.name}")
        destination_folder = (root / move.destination_folder).resolve()
        if not is_relative_to(destination_folder, root):
            raise ValueError(f"Unsafe destination rejected: {move.name}")
        destination_folder.mkdir(parents=True, exist_ok=True)
        destination = unique_path(destination_folder / move.name)
        try:
            shutil.move(str(source), str(destination))
        except PermissionError as error:
            raise PermissionError(f"Windows denied access to “{move.name}”. Restart Tidy as administrator and try again.") from error
        completed_move = PlannedMove(move.source, move.destination_folder, str(destination), move.category, move.name, move.reason)
        completed.append(completed_move)
        _save_history(root, completed)
        if progress:
            progress(index, total, move.name)
    refresh_folder_dates(root, completed)
    return completed


def undo_last(progress: Callable[[int, int, str], None] | None = None) -> tuple[int, Path | None]:
    folder, moves = load_history()
    restored = 0
    total = len(moves)
    for index, move in enumerate(reversed(moves), start=1):
        current = Path(move.destination)
        if current.exists():
            original = unique_path(Path(move.source), restored=True)
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(current), str(original))
            restored += 1
        if progress:
            progress(index, total, move.name)
    history_file().unlink(missing_ok=True)
    return restored, folder
