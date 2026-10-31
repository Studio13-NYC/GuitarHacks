"""Find song folders and remember destinations chosen outside the default library."""
import json
from pathlib import Path
import uuid

from .recipe_spec import song_slug


def locations(root):
    try:
        entries = json.loads((root / 'song-folders.json').read_text(encoding='utf-8'))
        return [item for item in entries if isinstance(item, dict)
                and all(isinstance(item.get(key), str) for key in ('source', 'title', 'folder'))
                and item['title'].strip() and item['source'].strip()
                and Path(item['folder']).is_absolute()] if isinstance(entries, list) else []
    except (OSError, ValueError):
        return []


def remember_folder(root, source, title, folder):
    entries = [item for item in locations(root)
               if not (Path(item['source']) == source and song_slug(item['title']) == song_slug(title))]
    entries.insert(0, {'source': str(source), 'title': title, 'folder': str(folder)})
    target = root / 'song-folders.json'
    temporary = root / f'.song-folders-{uuid.uuid4().hex}.tmp'
    try:
        temporary.write_text(json.dumps(entries, indent=2), encoding='utf-8')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def reports(root):
    folders = set((root / 'separated').glob('*'))
    folders.update((root / 'separated/instruments').glob('*'))
    folders.update(Path(item['folder']) for item in locations(root))
    found = set()
    for folder in folders:
        if folder.is_dir():
            for pattern in ('stem-manifest-*.json', 'midi-manifest-*.json', 'verification.json'):
                found.update(folder.glob(pattern))
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def find_song_folder(root, source, title):
    """Prefer the user's chosen location, then existing matching song folders."""
    for item in locations(root):
        folder = Path(item['folder'])
        if (source and Path(item['source']) == source
                and song_slug(item['title']) == song_slug(title) and folder.is_dir()):
            return folder
    direct = root / 'separated' / title
    if direct.is_dir():
        return direct
    for report in reports(root):
        try:
            data = json.loads(report.read_text(encoding='utf-8'))
            if (source and data.get('source') and Path(data['source']) == source
                    and song_slug(data.get('title') or report.parent.name) == song_slug(title)):
                return report.parent
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    for folder in sorted((root / 'separated').glob('*')):
        if folder.is_dir() and song_slug(folder.name) == song_slug(title):
            return folder
    return None
