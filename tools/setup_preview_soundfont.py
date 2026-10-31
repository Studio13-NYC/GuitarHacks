"""Install the pinned local General MIDI preview sound set and its license."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / 'StemSlicer' / 'playback'
BASE = 'https://raw.githubusercontent.com/musescore/MuseScore/45924076871483cb96b859cc374c5fbdbf76ba53/share/sound/'
FILES = {
    'FluidR3Mono_GM.sf3': 'cfcd66d89e8386823400eca64934b14fbea7bf48ba1f00d21189af1262794ec2',
    'FluidR3Mono_License.md': '09926f9451f751408abd65162c99343f840234d2a708584808fd46427633063f',
}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, digest in FILES.items():
        target = ROOT / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            continue
        with urllib.request.urlopen(BASE + name, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f'Sound set verification failed: {name}')
        temporary = target.with_suffix('.partial')
        temporary.write_bytes(data)
        temporary.replace(target)
        print(f'Installed {target} ({len(data):,} bytes)')


if __name__ == '__main__':
    main()
