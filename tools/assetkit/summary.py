"""The one-screen plain-text summaries preview and verify print by default (--json prints the full
report instead): the verdict, the failures (with the parts and where they are), the counts, the
bounds, the allowed findings as counts per kind and part pair, and where the full report is."""
from pathlib import Path

FAILURES = 8        # failure lines shown; the rest are counted
PAIRS = 4           # part pairs shown per kind of allowed finding
WARNINGS = 3        # close-face lines shown


def shown(path):
    """A path relative to the current directory when it is inside it."""
    try: return str(Path(path).resolve().relative_to(Path.cwd()))
    except ValueError: return str(path)


def more(shown, total, where):
    return [f'  ... and {total-shown} more ({where})'] if total > shown else []


def settings_lines(report):
    """'settings: carts/x/mei-kit.json; depth on (carts/x/mei-kit.json), ...': the settings files a
    command read and the runtime it drew with, when a settings file applied (else nothing)."""
    settings = report.get('settings') or {}
    if not settings.get('files'): return []
    line = 'settings: '+', '.join(settings['files'])
    runtime = settings.get('runtime') or {}
    if runtime:
        line += '; '+', '.join(f'{k} {"on" if v["value"] else "off"} ({v["from"]})' for k,v in runtime.items())
    return [line]


def counts_line(report):
    """'triangles 82 of 100, vertices 81 of 128, textures 0, VRAM 0 bytes, palette entries 1':
    textures and VRAM always, even when zero."""
    budget = report.get('budget',{})
    of = lambda key: f'{report[key]}'+(f' of {budget[key]}' if key in budget else '')
    textures = report.get('textures') or {}
    line = (f'triangles {of("triangles")}, vertices {of("vertices")}, textures {len(textures.get("list",[]))}, '
            f'VRAM {textures.get("vram_bytes",0)} bytes')
    palette = report.get('palette')
    if palette: line += f', palette entries {palette.get("entries",0)}'
    levels = report.get('lod',{}).get('levels') if isinstance(report.get('lod'),dict) else None
    if levels: line += ', levels of detail '+' / '.join(str(level.get('triangles','?')) for level in levels)
    collision = report.get('collision')
    if isinstance(collision,dict):
        line += (f', collision {collision.get("triangles","?")} triangles ('
                 +('its own nodes' if collision.get('source') == 'nodes' else f'level {collision.get("level")}')+')')
    return line


def bounds_lines(report):
    lo,hi = report['bounds']['min'],report['bounds']['max']
    size = ' x '.join(f'{b-a:.2f}' for a,b in zip(lo,hi))
    lines = ['bounds: '+'  '.join(f'{axis} {a:.2f} .. {b:.2f}' for axis,a,b in zip('xyz',lo,hi))+f'  (size {size})']
    if lo[1] < 0:
        below = sorted((p['bounds']['min'][1],p['id']) for p in report.get('parts',[]) if p['bounds']['min'][1] < 0)
        names = ', '.join(dict.fromkeys(name for _,name in below))
        lines.append(f'below y = 0: down to {lo[1]:.2f}' + (f' ({names})' if names else ''))
    return lines


def allowed_lines(geometry):
    """One line per kind of allowed finding: its count and the part pairs with the most."""
    kinds = {}
    for row in (geometry or {}).get('allowed',[]):
        kinds.setdefault(row['code'],[]).append(row)
    lines = []
    for code,rows in kinds.items():
        rows.sort(key=lambda r:-r['count'])
        pair = lambda r: r['parts'][0] if r['parts'][0] == r['parts'][1] else '/'.join(r['parts'])
        shown = ', '.join(f'{pair(r)} {r["count"]}' for r in rows[:PAIRS])
        rest = f', and {len(rows)-PAIRS} more pairs' if len(rows) > PAIRS else ''
        lines.append(f'allowed {code}: {sum(r["count"] for r in rows)} ({shown}{rest})')
    return lines


def warning_lines(report):
    """The compile warnings, counted by code, with the parts they name."""
    codes = {}
    for w in report.get('warnings',[]):
        if isinstance(w,dict):
            codes.setdefault(w.get('code','warning'),[]).append(w.get('part') or w.get('key') or '')
        else:
            codes.setdefault('warning',[]).append('')
    lines = []
    for code,parts in codes.items():
        named = [p for p in dict.fromkeys(parts) if p]
        listed = f' ({", ".join(named[:6])}{", ..." if len(named) > 6 else ""})' if named else ''
        lines.append(f'warning {code}: {len(parts)}{listed}')
    return lines


def checked_lines(checked):
    """The Asset Checker's result: the verdict, the failures, the views, the allowed findings and
    the close faces."""
    lines = [f'verdict: {checked["verdict"]}']
    failures = checked.get('failures',[])
    lines += [f'  FAIL {line}' for line in failures[:FAILURES]]+more(FAILURES,len(failures),'failures')
    totals = checked.get('totals',{})
    if totals:
        unseen = checked.get('unobserved_faces',0)
        lines.append(f'views judged: {totals.get("views",0)}; faces seen {checked.get("observed_faces",0)} of '
                     f'{checked.get("faces",0)}'+(f' ({unseen} never seen: inside, or hidden from every view)' if unseen else ''))
    lines += allowed_lines(checked.get('geometry'))
    close = checked.get('warnings',[])
    if close:
        lines.append(f'close faces: {len(close)} part pairs (they z-fight from a distance)')
        lines += ['  '+line for line in close[:WARNINGS]]+more(WARNINGS,len(close),'warnings')
    return lines


def preview_text(report, output=None):
    """preview's summary of build()'s report."""
    name = report['name']
    lines = [f'{name}: preview written to {shown(report.get("output",output))}']
    if 'verification' in report:
        lines += checked_lines(report['verification'])
    else:
        lines.append('verdict: not checked (no required policy in the recipe; add --verify, or run verify)')
    lines.append(counts_line(report))
    lines += bounds_lines(report)
    flush = report.get('flush_contacts')
    if flush and flush.get('count'):
        lines.append(f'flush contacts: {flush["count"]} (allowed by geometry warn)')
        lines += ['  '+line for line in flush.get('fixes',[])[:WARNINGS]]+more(WARNINGS,len(flush.get('fixes',[])),'flush_contacts')
    lines += warning_lines(report)
    lines += settings_lines(report)
    preview = report.get('preview',{})
    look = preview.get('look')
    if look:
        sky = ' to '.join(look['background'])
        lines.append(f'look: background {sky}, ground {look["ground"] or "none"}'+(f' (from {look["from"]})' if look.get('from') else ''))
    if preview:
        lines.append(f'images: {shown(preview["contact"])} (6 fitted views)')
        cameras = preview.get('cameras')
        if cameras:
            costs = ', '.join(f'{v["view"]} {v["cost"]["asset_gpu_frame_percent"]} %' for v in cameras['views'])
            lines.append(f'        {shown(cameras["contact"])} (the asset\'s share of a frame\'s GPU: {costs})')
    out = report.get('output',output)
    lines.append(f'full report: {shown(Path(out)/"report.json")} (or run with --json)' if out else 'full report: run with --json')
    return '\n'.join(lines)


def verify_text(result, compiled=None, output=None):
    """verify's summary of the Asset Checker's result; compiled (the compile report) adds the
    counts and bounds."""
    lines = [f'{result["name"]}: {result["verdict"]}']
    lines += checked_lines(result)[1:]
    for level in result.get('lod',[]):
        lines.append(f'level of detail {level["level"]}: {"ok" if level["ok"] else "FAIL"}, {level["faces"]} faces')
    if compiled:
        lines.append(counts_line(compiled))
        lines += bounds_lines(compiled)
    lines += settings_lines(result)
    lines.append(f'full report: {shown(Path(output)/"verification.json")} (or run with --json)' if output else
                 'full report: run with --json (or -o DIR to save it with difference images)')
    return '\n'.join(lines)


def failure_text(report, error):
    """A failed verification under build or preview: its summary and where the renders and the
    report are."""
    lines = [f'{report.get("name","asset")}: export blocked by verification']
    lines += checked_lines(report)
    preview = report.get('preview') or {}
    if 'contact' in preview:
        lines.append(f'failing renders (not exported): {shown(preview["contact"])}'
                     +(f' and {shown(preview["cameras"]["contact"])}' if 'cameras' in preview else ''))
    elif 'error' in preview:
        lines.append(f'failing renders: none ({preview["error"]})')
    lines.append(f'full report: {shown(getattr(error,"report_path","verification.failed.json"))} (or run with --json)')
    return '\n'.join(lines)
