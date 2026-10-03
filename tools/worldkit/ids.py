"""The ID lock file, NAME.ids.json beside the world recipe: every saved entity's persistent bit.

Append-only: a new saved entity gets the next bit; a removed one's bit is retired, never given to
another ID; an entity that says "was": OLD takes OLD's bit (a rename). Re-adding a retired ID gives
it back its own bit, since it names the same goal. Nothing ever moves a bit to a different ID
except an explicit rename, so a player's save stays valid across edits of the level.
"""
from pathlib import Path

from kitcore import jsonio
from .schema import WorldError

FORMAT = 'mei-world-ids'


def empty(world):
    return {'format':FORMAT,'version':1,'world':world,'next_bit':0,'bits':{},'retired':{},'renamed':{}}


def load(path, world):
    """The lock at path, checked, or an empty one if there is none."""
    path = Path(path)
    if not path.exists(): return empty(world)
    lock = jsonio.load(str(path),WorldError)
    file = str(path)
    def bad(message, where=''): raise WorldError(where,message+' Restore the lock file from version control; never edit bits by hand.',file)
    if not isinstance(lock,dict) or lock.get('format') != FORMAT or lock.get('version') != 1:
        bad('Not a World Kit ID lock file (format mei-world-ids, version 1).')
    if set(lock) != {'format','version','world','next_bit','bits','retired','renamed'}:
        bad('The lock file has missing or unknown properties.')
    if lock['world'] != world:
        bad(f'The lock file is for world {lock["world"]!r}, not {world!r}.','/world')
    bits = {**lock['bits'],**lock['retired']}
    if len(bits) != len(lock['bits'])+len(lock['retired']):
        bad('An ID is both live and retired.')
    values = list(bits.values())
    if any(type(b) is not int or not 0 <= b < lock['next_bit'] for b in values) or len(set(values)) != len(values):
        bad('Bits must be distinct integers below next_bit.','/bits')
    return lock


def update(lock, saved, renames):
    """The lock after this recipe, and what changed. saved: ordered IDs of saved entities;
    renames: {new ID: (old ID, JSON Pointer of its 'was')}."""
    old = lock
    lock = {**old,'bits':dict(old['bits']),'retired':dict(old['retired']),'renamed':dict(old['renamed'])}
    changes = {'added':[],'retired':[],'renamed':[],'revived':[]}
    wanted = set(saved)
    for new,(was,path) in sorted(renames.items()):
        if new not in wanted: continue
        if was in wanted:
            raise WorldError(path,f'Entity {new!r} says it was {was!r}, but {was!r} still exists. Remove one, or drop "was".')
        if new in lock['bits']:
            continue                     # already renamed by an earlier build; `was` is history
        if was in lock['bits']:
            lock['bits'][new] = lock['bits'].pop(was)
        elif was in lock['retired']:
            lock['bits'][new] = lock['retired'].pop(was)
        else:
            raise WorldError(path,f'No saved entity {was!r} in the lock file to rename. Remove "was" for a new entity.')
        lock['renamed'][was] = new
        changes['renamed'].append([was,new])
    for name in sorted(set(lock['bits'])-wanted):
        lock['retired'][name] = lock['bits'].pop(name)
        changes['retired'].append(name)
    for name in saved:
        if name in lock['bits']: continue
        if name in lock['retired']:
            lock['bits'][name] = lock['retired'].pop(name)
            changes['revived'].append(name)
        else:
            lock['bits'][name] = lock['next_bit']
            lock['next_bit'] += 1
            changes['added'].append(name)
    lock['bits'] = dict(sorted(lock['bits'].items(),key=lambda kv: kv[1]))
    lock['retired'] = dict(sorted(lock['retired'].items(),key=lambda kv: kv[1]))
    lock['renamed'] = dict(sorted(lock['renamed'].items()))
    return lock, {k:v for k,v in changes.items() if v}
