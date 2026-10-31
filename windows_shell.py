"""Windows taskbar identity and native pin/relaunch metadata."""
import subprocess
import sys
from pathlib import Path
from win32com.propsys import propsys, pscon

APP_ID='Studio13.GuitarHacks'


def configure_taskbar(window):
    """Set on the native window before showing it; never pin without the user."""
    executable=Path(sys.executable).resolve()
    arguments=[str(executable),*sys.argv[1:]]
    if not getattr(sys,'frozen',False):
        arguments.insert(1,str(Path(__file__).resolve().parent/'app.py'))
    properties=propsys.SHGetPropertyStoreForWindow(int(window.winId()),propsys.IID_IPropertyStore)
    for key,value in (
        (pscon.PKEY_AppUserModel_RelaunchCommand,subprocess.list2cmdline(arguments)),
        (pscon.PKEY_AppUserModel_RelaunchDisplayNameResource,'GuitarHacks'),
        (pscon.PKEY_AppUserModel_RelaunchIconResource,
         str(executable)+',0' if getattr(sys,'frozen',False) else str(Path(__file__).resolve().parent/'assets/guitarhacks.ico')),
        (pscon.PKEY_AppUserModel_ID,APP_ID),
    ):
        properties.SetValue(key,propsys.PROPVARIANTType(value))
    properties.Commit()
