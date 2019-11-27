from dataclasses import dataclass
from opsi.manager.types import Mat
from opsi.manager.manager_schema import Function
import glob
import logging
import re
import subprocess

import cv2

LOGGER = logging.getLogger(__name__)

__package__ = "opsi.input"

CODECS = {
    "video/x-h264": "X264",
    "video/x-raw": ("YUYV", "I420", "YUY2"),
    "image/jpeg": "MJPG",
}


def get_fourcc(filetype, fmt):
    codec = CODECS[filetype]
    if type(codec) is tuple:
        if fmt in codec:
            codec = fmt
        else:
            return None
    return cv2.VideoWriter_fourcc(*codec)


class Camera:
    def on_start(self):
        assert type(self.ID) is int
        self.get_modes()
        self.cap = cv2.VideoCapture(self.ID)

    @dataclass
    class Inputs:
        pass

    @dataclass
    class Outputs:
        img: Mat

    @dataclass
    class Settings:
        pass

    def __get_info__(self):
        try:
            gst = subprocess.Popen(
                f"timeout 0.2 gst-launch-1.0 --gst-debug=v4l2src:5 v4l2src device=/dev/video{self.ID} ! fakesink".split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            out = subprocess.check_output(
                ["sed", "-une", r"/caps of src/ s/[:;] /\n/gp"],
                stdin=gst.stdout,
                universal_newlines=True,
            )
            print(out)
            return str(out)
        except subprocess.CalledProcessError as e:
            pass
        return None

    def get_modes(self):
        # today i will have two problems
        regex = r"(\w+\/[\da-z-]+), (?:stream-)?(?:format=\(string\)([\w-]+), )?(?:.+)?(?:width=\(int\)(\[[\d ,]+\]|\d+)), (?:height=\(int\)(\[[\d ,]+\]|\d+)), (?:framerate=\(fraction\)([\{\}\[\]\d \/,]+))"
        info = self.__get_info__()
        if not info:
            return None
        modes = []
        for match in re.finditer(regex, info):
            mode = {}
            mode["fourcc"] = get_fourcc(match.group(1), match.group(2))
            if not mode["fourcc"]:
                continue
            mode["format"] = match.group(2)

            width = list(
                map(int, match.group(3).strip("\{\}[]").replace(",", "").split())
            )
            height = list(
                map(int, match.group(4).strip("\{\}[]").replace(",", "").split())
            )
            if len(width) == 1 and len(height) == 1:
                mode["resolutions"] = (width[0], height[0])

            mode["fps"] = match.group(5).strip("\{\}[]").replace(",", "").split()
            modes.append(mode)
        print(modes)

    def run(self, inputs):
        frame = None
        if self.cap:
            ret, frame = self.cap.read()
            frame = frame.view(Mat)
        return self.Outputs(img=frame)


# def get_w(string):
#     camstring = parse_camstring(string)
#     if len(camstring) >= 3:
#         camtuple = parse_camstring(string)
#         return camtuple[1] + camtuple[2]
#     return 0


# def get_codec(v4l2_out):
#     # for each codec, add the codec name and the description from v4l2-ctl (regex allowed), and FOURCC name
#     # order by priority
#     codecs = [
#         ("H264", "H.264, compressed", "X264"),
#         ("MJPG", "Motion-JPEG, compressed", "MJPG"),
#         ("YUYV", r"YUYV \d:\d:\d", "YUYV"),
#         ("YU12", r"Planar YUV \d:\d:\d", "YU12"),
#     ]
#     for i in codecs:
#         # [digit] '<CODEC NAME>' (<CODEC DESCRIPTION>)
#         # ex. [1]: 'MJPG' (Motion-JPEG, compressed)
#         pattern1 = fr"\[\d+\]: '{i[0]}' \({i[1]}\) (.+)(\[\d+\].+)"
#         lines1 = re.search(pattern1, v4l2_out)
#         if lines1 is not None:
#             return (cv2.VideoWriter_fourcc(*i[2]), lines1.group(1))
#         pattern2 = fr"\[\d+\]: '{i[0]}' \({i[1]}\) (.+)($)"
#         lines2 = re.search(pattern2, v4l2_out)
#         if lines2 is not None:
#             return (cv2.VideoWriter_fourcc(*i[2]), lines2.group(1))
#     return None


# def get_cam_info(cam):
#     try:
#         sp_out = subprocess.run(
#             f"v4l2-ctl -d {str(cam)} --list-formats-ext".split(),
#             capture_output=True,
#             check=True,
#         )
#         return str(sp_out.stdout).replace("\\n", " ").replace("\\t", "")
#     except subprocess.CalledProcessError:
#         pass
#     return None


# def get_modes():
#     # TODO: don't use globals, move all of this to a class and make a instance for module
#     global ENABLE_FPS
#     global ENABLE_RES

#     all_modes = set()
#     cam_list = (cam.replace("/dev/video", "") for cam in glob.glob("/dev/video*"))

#     for cam in sorted(cam_list, key=int):

#         caminfo = get_cam_info(cam)

#         # remove cameras of these types
#         # PiCam has extraneous cameras with type "Video Capture Multiplanar"

#         skip = False
#         cam_blacklist = ("Video Capture Multiplanar",)
#         for i in cam_blacklist:
#             if re.search(i, caminfo):
#                 skip = True
#         if skip:
#             continue

#         codec = get_codec(caminfo)
#         if codec is None:
#             continue

#         # group 1: resolution
#         # group 2: everything up until next instance of Size
#         any_set = False
#         for match in re.finditer(r"Size: Discrete (\d+x\d+) ", codec[1]):
#             resolution = match.group(1)
#             # get everything from the curent resolution to the next resolution
#             line = re.search(
#                 fr"{match.group(0)}(.+?)Size|{match.group(0)}(.+)", codec[1]
#             )
#             line = line.group(1) or line.group(2)
#             fpses = set()
#             for interval in re.finditer(r"nterval: \w+ \d+\.\d+s \((.+?) fps\)", line):
#                 fpses.add(float(interval.group(1)))
#             # convert to float to use %g formatting, removing extraneous decimals
#             if resolution:
#                 if fpses:
#                     all_modes.add(
#                         "Cam {0}: {1} @ {2:g} fps".format(
#                             cam, resolution, float(max(fpses))
#                         )
#                     )
#                     any_set = True
#                 else:
#                     all_modes.add("Cam {0}: {1}".format(cam, resolution))
#                     any_set = True
#                     ENABLE_FPS = True
#         if not any_set:
#             all_modes.add("Cam {0}".format(cam))
#             ENABLE_RES = True

#     return tuple(sorted(all_modes, key=get_w, reverse=True))


# def parse_camstring(string):
#     camstring = []
#     # group 3: any digit+ OR any digit+, decimal, any digit+
#     m = re.search(r"(?:Cam (\d+))?(?::( \d+)x(\d+))?(?: @ (\d+|\d+.\d+) fps)?", string)
#     cam = m.group(1)
#     w = m.group(2)
#     h = m.group(3)
#     fps = m.group(4)
#     if cam:
#         camstring.append(int(cam))
#     if w and h:
#         camstring.append(int(w))
#         camstring.append(int(h))
#     if fps:
#         camstring.append(float(fps))
#     return tuple(camstring)


# def controls(fps=False):
#     if ENABLE_RES:
#         return int
#     if fps and ENABLE_FPS:
#         return int
#     return None


# def set_property(cap, prop, value):
#     try:
#         cap.set(prop, value)
#     except AttributeError:
#         LOGGER.debug("Camera does not support property %s", property)


# def create_capture(settings):
#     mode = parse_camstring(settings.mode)
#     if len(mode) < 1:
#         return None
#     cap = cv2.VideoCapture(mode[0])
#     codec = get_codec(get_cam_info(mode[0]))
#     set_property(cap, cv2.CAP_PROP_FOURCC, codec[0])
#     if len(mode) >= 3:
#         w = mode[1]
#         h = mode[2]
#     else:
#         w = settings.width
#         h = settings.height
#     set_property(cap, cv2.CAP_PROP_FRAME_WIDTH, w)
#     set_property(cap, cv2.CAP_PROP_FRAME_HEIGHT, h)
#     if len(mode) >= 4:
#         fps = mode[3]
#     else:
#         fps = settings.fps
#     set_property(cap, cv2.CAP_PROP_FPS, fps)
#     set_property(cap, cv2.CAP_PROP_BRIGHTNESS, settings.brightness)
#     set_property(cap, cv2.CAP_PROP_CONTRAST, settings.contrast)
#     set_property(cap, cv2.CAP_PROP_SATURATION, settings.saturation)
#     set_property(cap, cv2.CAP_PROP_EXPOSURE, settings.exposure)
#     return cap

# class CameraInput(Function):
#     def on_start(self):
#         camNum = parse_camstring(self.settings.mode)[0]
#         if not UndupeInstance.add(camNum):
#             raise ValueError(f"Camera {camNum} already in use")

#         self.cap = create_capture(self.settings)
#         self.cap.read()  # test for errors

#     @dataclass
#     class Settings:
#         mode: get_modes()
#         brightness: int = 50
#         contrast: int = 50
#         saturation: int = 50
#         exposure: int = 50
#         width: controls() = None
#         height: controls() = None
#         fps: controls(True) = None

#     @dataclass
#     class Outputs:
#         img: Mat

#     def run(self, inputs):
#         frame = None
#         if self.cap:
#             ret, frame = self.cap.read()
#             frame = frame.view(Mat)
#         return self.Outputs(img=frame)

#     def dispose(self):
#         camNum = parse_camstring(self.settings.mode)[0]
#         UndupeInstance.remove(camNum)
