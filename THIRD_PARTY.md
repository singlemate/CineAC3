# Third-party software

The MIT license in this repository covers CineAC3's own code only.

## FFmpeg

CineAC3 invokes FFmpeg and ffprobe as separate command-line processes.
This repository does **not** distribute their binaries. On first launch,
if the tools are unavailable, CineAC3 downloads the unmodified Windows x64
FFmpeg 9.0.2 essentials archive directly from its upstream Windows build provider:

- Build: https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip
- SHA-256: `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`
- Provider and build/source information: https://www.gyan.dev/ffmpeg/builds/
- FFmpeg source: https://ffmpeg.org/download.html
- License information: https://ffmpeg.org/legal.html

That build enables GPL and version 3 and is covered by GPLv3. Its original
LICENSE is installed alongside the downloaded binaries. Its external
components remain subject to their respective licenses.

The upstream download is separate from CineAC3's source distribution.
If you redistribute FFmpeg binaries yourself (including in an application
archive), you must separately satisfy their licensing requirements, including
providing the complete corresponding source as required by the applicable GPL.
This repository's MIT license does not replace those requirements.

## Python and Tcl/Tk

Source execution uses the user's installed Python and Tcl/Tk.
When distributing a frozen executable, retain the Python/Tcl/Tk and packaging
tool license notices in that distribution. This source repository does not
bundle a Python runtime.
