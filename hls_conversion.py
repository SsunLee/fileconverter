import os
import subprocess
import tempfile
from pathlib import Path


HLS_INPUT_OPTIONS = (
    "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
    "-allowed_extensions", "ALL", "-allowed_segment_extensions", "ALL",
    "-extension_picky", "0", "-analyzeduration", "30000000", "-probesize", "32000000",
)
PROCESS_OPTIONS = {
    "stdin": subprocess.DEVNULL,
    "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
}


def temporary_mp4(output):
    fd, name = tempfile.mkstemp(suffix=".mp4", dir=Path(output).parent)
    os.close(fd)
    return name


def publish_video(temporary, output):
    frames = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "V:0", "-show_entries",
         "stream=nb_frames", "-of", "csv=p=0", temporary], **PROCESS_OPTIONS
    ).strip()
    if not frames.isdigit() or int(frames) < 1:
        raise ValueError("출력 파일에 영상 프레임이 없습니다.")
    os.replace(temporary, output)
