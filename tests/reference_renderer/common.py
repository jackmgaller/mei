"""Paths and native builds shared by the Reference Renderer's checks (README.md).

Everything a check makes goes under BUILD/reference_renderer/: its generated carts and their
assets (carts/NAME/), the compiled probes and its images and reports. BUILD is the build
directory, `build` unless MEI_BUILD names another (`make B=DIR rendercheck` passes it on).
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))     # meshlib, the native mesh writer
BUILD = ROOT / os.environ.get('MEI_BUILD', 'build')
OUT = BUILD / 'reference_renderer'
HEADLESS = BUILD / 'mei-headless'


def native(*targets):
    """Builds these files of the build directory (e.g. 'meic') with make, honouring MEI_BUILD.
    Under `make rendercheck` they are built already; the parent's job server is not passed on."""
    env = {k: v for k, v in os.environ.items() if k not in ('MAKEFLAGS', 'MFLAGS', 'MAKELEVEL')}
    subprocess.run(['make', '-s', f'B={os.path.relpath(BUILD, ROOT)}',
                    *(os.path.relpath(BUILD / t, ROOT) for t in targets)], cwd=ROOT, env=env,
                   check=True)


def probe(name):
    """Compiles HERE/NAME.c against the emulator core into OUT/NAME; returns its path."""
    native('libmeicore.a')
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    subprocess.run(['cc', '-O2', '-std=c11', '-Wall', '-Wextra', '-I', str(ROOT / 'src/core'),
                    str(HERE / f'{name}.c'), str(BUILD / 'libmeicore.a'), '-o', str(path)], check=True)
    return path


def cart_dir(name):
    """The folder a check writes cart NAME's source and assets to."""
    path = OUT / 'carts' / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def compile_cart(name):
    """Compiles cart_dir(NAME)/NAME.akr with the build directory's meic and this checkout's
    stdlib (or the one MEI_STDLIB names); returns the ROM's path."""
    native('meic', 'mei-headless')
    rom = OUT / f'{name}.mei'
    env = dict(os.environ, MEI_STDLIB=os.environ.get('MEI_STDLIB') or str(ROOT / 'stdlib'))
    subprocess.run([str(BUILD / 'meic'), str(cart_dir(name) / f'{name}.akr'), '-o', str(rom)],
                   env=env, check=True)
    return rom
