"""Running Mei's real compiler and headless runner, and the images they produce: PPM in, PNG
and contact sheets out. No image library is needed."""
import csv
import os
from pathlib import Path
import re
import struct
import subprocess
import zlib

from .errors import KitError

WIDTH, HEIGHT = 320, 240
ROOT = Path(__file__).resolve().parents[2]

# The native tools the kits run: {key: (environment variable, file in a build directory)}. The
# key is the command-line option's name (--compiler, --runner, --probe); the variables are the
# ones the test suites read.
TOOLS = {'compiler': ('MEIC', 'meic'), 'runner': ('RUN', 'mei-headless'),
         'probe': ('PROBE', 'mei-asset-probe'), 'scene_probe': ('SCENE_PROBE', 'mei-scene-probe')}


def build_dir(given=None, environ=None):
    """The build directory (the one make B=DIR builds into) and how it was chosen, (Path, how):
    --build-dir DIR (given), else $B (relative to the repository, as make's B), else build/.
    Every kit command that runs native tools or keeps a cache in the build directory takes the
    directory from here."""
    environ = os.environ if environ is None else environ
    if given is not None:
        return Path(given).resolve(), f'--build-dir {given}'
    if environ.get('B'):
        return (ROOT/environ['B']).resolve(), f'B={environ["B"]}'
    return ROOT/'build', 'the default, build/'


def tool_paths(keys, options=None, given_dir=None, environ=None):
    """{key: (path, how it was chosen)} for the native tools named by keys (of TOOLS), each from
    the first of: its own option (options[key]: --compiler, --runner, --probe), --build-dir DIR
    (given_dir), its environment variable (MEIC, RUN, PROBE, SCENE_PROBE), then build_dir():
    $B, build/."""
    environ = os.environ if environ is None else environ
    options = options or {}
    out = {}
    for key in keys:
        variable, executable = TOOLS[key]
        given = options.get(key)
        if given is not None:
            path, how = Path(given), f'--{key.replace("_", "-")} {given}'
        elif given_dir is not None:
            path, how = Path(given_dir)/executable, f'--build-dir {given_dir}'
        elif environ.get(variable):
            path, how = Path(environ[variable]), f'{variable}={environ[variable]}'
        else:
            directory, how = build_dir(None, environ)
            path = directory/executable
        out[key] = (path.resolve(), how)
    return out


def require_tools(tools, keys, error=KitError):
    """An error naming each missing tool (of tool_paths()), the directory looked in, how it was
    chosen, the make command that builds it and how to point the kit elsewhere."""
    missing = [(key, *tools[key]) for key in dict.fromkeys(keys) if not tools[key][0].is_file()]
    if not missing:
        return
    lines = []
    for key, path, how in missing:
        directory = path.parent
        try:
            shown = directory.relative_to(ROOT)
        except ValueError:
            shown = directory
        lines.append(f'Missing {path.name} in {directory} (the {key.replace("_", " ")}, from {how}): build it with '
                     f'make B={shown} {shown}/{path.name}')
    raise error('/arguments/tools', '. '.join(lines) + '. To use another build directory, pass --build-dir DIR '
                '(the directory make B=DIR builds into) or set B=DIR, or MEIC, RUN, PROBE and SCENE_PROBE for single '
                'tools, or the tool\'s own option (--compiler, --runner, --probe).')


def require(path, executables, hint='Run make to build Mei, or pass --compiler/--runner.', error=KitError):
    for executable in executables:
        if not Path(executable).is_file():
            raise error(path,f'Missing {executable}. {hint}')


def run(args, path, timeout=45, env=None, error=KitError):
    """Runs a tool; a failure raises error(path) with the end of its output."""
    try:
        result = subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=timeout,env=env)
    except (OSError,subprocess.TimeoutExpired) as failure:
        raise error(path,str(failure)) from failure
    if result.returncode:
        raise error(path,(result.stderr+'\n'+result.stdout).strip()[-4000:])
    return result


def compile_cart(compiler, source, cart, path, env=None, error=KitError):
    return run([compiler,source,'-o',cart],path,env=env,error=error)


def run_cart(runner, cart, path, frames=4, dump=None, gpu_stats=None, extra=(), timeout=45, error=KitError):
    args = [runner,cart,'--frames',str(frames)]
    if dump: args += ['--dump',dump]
    if gpu_stats: args += ['--gpu-stats',gpu_stats]
    return run(args+list(extra),path,timeout=timeout,error=error)


def read_ppm(path, error_path, error=KitError):
    """The pixels (RGB bytes) of a 320 x 240 binary PPM the headless runner dumped."""
    header,width_height,maxval,pixels = Path(path).read_bytes().split(b'\n',3)
    if (header,width_height,maxval,len(pixels)) != (b'P6',f'{WIDTH} {HEIGHT}'.encode(),b'255',WIDTH*HEIGHT*3):
        raise error(error_path,'Headless runner produced an unexpected image format.')
    return pixels


def last_frame_stats(path):
    """The last presented frame's row of a --gpu-stats CSV, as integers, or None."""
    with Path(path).open() as stream:
        frames = list(csv.DictReader(stream))
    return {k:int(v) for k,v in frames[-1].items()} if frames else None


def frame_budgets():
    """{'cpu': cycles, 'gpu': cycles} a frame may spend: MEI_CYCLES_PER_FRAME and
    MEI_GPU_CYCLES_PER_FRAME from src/core/mei.h."""
    text = (Path(__file__).resolve().parents[2]/'src'/'core'/'mei.h').read_text()
    found = dict(re.findall(r'#define\s+(MEI_(?:GPU_)?CYCLES_PER_FRAME)\s+(\d+)',text))
    return {'cpu':int(found['MEI_CYCLES_PER_FRAME']),'gpu':int(found['MEI_GPU_CYCLES_PER_FRAME'])}


def upscaled(pixels, factor, width=WIDTH, height=HEIGHT):
    """RGB bytes of width x height scaled up by a whole factor, each pixel a factor x factor block."""
    if factor == 1:
        return pixels
    rows = []
    for y in range(height):
        row = b''.join(pixels[x*3:x*3+3]*factor for x in range(y*width,(y+1)*width))
        rows.append(row*factor)
    return b''.join(rows)


def tile_sheet(images, width, height, columns):
    """Images (RGB bytes, width x height each) tiled into one PNG, left to right, top to bottom."""
    rows = (len(images)+columns-1)//columns
    full = width*columns
    pixels = bytearray(full*height*rows*3)
    for i,img in enumerate(images):
        x,y = (i%columns)*width,(i//columns)*height
        for row in range(height):
            start = ((y+row)*full+x)*3
            pixels[start:start+width*3] = img[row*width*3:(row+1)*width*3]
    return png_bytes(full,height*rows,bytes(pixels))


def png_bytes(width, height, pixels):
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    rows = b''.join(b'\0'+pixels[y*width*3:(y+1)*width*3] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',width,height,8,2,0,0,0))+
            chunk(b'IDAT',zlib.compress(rows,9))+chunk(b'IEND',b''))


def contact_sheet(images, columns=3):
    """Screens (RGB bytes, 320 x 240 each) tiled into one PNG, left to right, top to bottom."""
    return tile_sheet(images,WIDTH,HEIGHT,columns)
