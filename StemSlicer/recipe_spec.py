"""Shared instrument names, stem definitions, and Windows-safe output names."""
import re

PARTS = (
    ('vocals', 'Vocals', 'V'), ('drums', 'Drums', 'D'), ('bass', 'Bass', 'B'),
    ('piano', 'Piano', 'P'), ('other', 'Other instruments', 'O'),
    ('lead-guitar', 'Lead guitar', 'L'), ('rhythm-guitar', 'Rhythm guitar', 'R'),
)
FORMATS = {'mp3': ('.mp3',), 'wav': ('.wav',), 'both': ('.mp3', '.wav')}


def song_title(text):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', text).strip(' .')[:80].rstrip(' .')
    if not value or value in ('.', '..'):
        raise ValueError('Enter a song title.')
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', value, re.I):
        value = 'Song-' + value
    return value


def suggested_title(filename_stem):
    return song_title(re.sub(r'^\d{1,3}[\s._-]+', '', filename_stem))


def validate_stems(stems):
    if not isinstance(stems, list) or not stems:
        raise ValueError('Add at least one stem.')
    names = [part[0] for part in PARTS]
    result = []
    for index, stem in enumerate(stems, 1):
        if not isinstance(stem, list) or not stem:
            raise ValueError(f'Choose at least one instrument for stem {index}.')
        if any(name not in names for name in stem):
            raise ValueError(f'Unknown instrument in stem {index}.')
        result.append([name for name in names if name in stem])
    return result


def song_slug(title):
    return re.sub(r'[^\w]+', '-', song_title(title).lower(), flags=re.UNICODE).strip('-_') or 'song'


def filename_base(text):
    """Accept a filename or basename, rejecting paths and Windows device names."""
    value = text.strip()
    if value.lower().endswith(('.mp3', '.wav')):
        value = value[:-4]
    if (not value or len(value) > 160 or value.endswith((' ', '.'))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
            or value in ('.', '..')
            or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', value, re.I)):
        raise ValueError('Use a filename without folders or special characters.')
    return value


def output_bases(title, stems, existing=(), names=None):
    """Choose names across formats; equal recipes and reruns get suffixes."""
    prefix = song_slug(title)
    used = {name.casefold() for name in existing}
    result = []
    stems = validate_stems(stems)
    if names is not None and (not isinstance(names, list) or len(names) != len(stems)):
        raise ValueError('Provide one output name per stem.')
    for index, stem in enumerate(stems):
        custom = names[index] if names else None
        base = filename_base(custom) if custom else prefix + '-' + '-'.join(code for name, _, code in PARTS if name in stem)
        candidate, suffix = base, 2
        while candidate.casefold() in used:
            candidate = f'{base}-{suffix}'
            suffix += 1
        result.append(candidate)
        used.add(candidate.casefold())
    return result
