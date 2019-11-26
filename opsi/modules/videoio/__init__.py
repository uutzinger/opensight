from dataclasses import dataclass
import sys
import glob

from opsi.manager.manager_schema import Function
from opsi.manager.types import Mat
from opsi.util.unduplicator import Unduplicator

from .input import Camera
from .cameraserver import CameraSource, CamHook

# from .input import controls, create_capture, get_modes, parse_camstring

__package__ = "opsi.videoio"
__version__ = "0.123"

UndupeInstance = Unduplicator()
HookInstance = CamHook()


def safe_int(inp):
    try:
        return int(inp)
    except ValueError:
        return inp


def get_cameras():
    # get camera list, convert to int if possible (allow implmentations to appropriately deal with non-ints)
    cam_list = (
        safe_int(cam.replace("/dev/video", "")) for cam in glob.glob("/dev/video*")
    )
    cls_list = [type(f"Camera{i}", (Camera, Function), {"ID": i}) for i in cam_list]
    return cls_list


for i in get_cameras():
    setattr(sys.modules[__name__], i.__name__, i)
# unset i so it is not accidentally as a member
i = None


class CameraServer(Function):
    has_sideeffect = True

    @classmethod
    def validate_settings(cls, settings):
        settings.name = settings.name.strip()

        return settings

    def on_start(self):
        self.src = CameraSource()
        HookInstance.register(self)

    @dataclass
    class Settings:
        name: str = "camera"

    @dataclass
    class Inputs:
        img: Mat

    def run(self, inputs):
        self.src.img = inputs.img
        return self.Outputs()

    def dispose(self):
        self.src.shutdown()
        HookInstance.unregister(self)

    # Returns a unique string for each CameraServer instance
    @property
    def id(self):
        return self.settings.name
