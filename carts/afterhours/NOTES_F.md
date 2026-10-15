# Agent F's notes: sound and music

What `dr_audio.akr` offers, the calls it needs from A (the runtime) and E (the front end), the
channels and what it all costs. The sounds are made by `tools/gen_afterhours_audio.py` (it writes
`audio/` and `au_data.akr`); `dr_audio.akr` is the only file that reads them. Kept current.

## The calls (for A and E)

`import "dr_audio.akr"` and call these; none of them changes the game's state, so tapes and
replays are unaffected. Every call is safe at any time, in any order, any number of times.

| Call | When | Who |
|---|---|---|
| `au_tick()` | **Once a frame, always**, whatever screen (play, freeze, menus, transition), after the frame's other calls | A: at the end of every `update()`, in every mode (so E does not call it) |
| `au_music(on)` | `true` where the stage track should be heard (it starts it, or does nothing when it is already playing); `false` fades it out over half a second | E (title, stage select), A (the run) |
| `au_pause(on)` | The pause menu opens (`true`) and closes (`false`): the music and the ambience duck | A or E |
| `au_room(amb)` | **Entering a room** (the run's first and each next one; *not* on a restart): its ambience `AMB_*` (below), crossfaded from the last room's; the same ambience carries on untouched. Also sets the room's reverb and plays the door shutting behind him | A (`enter_room()`) |
| `au_ambience(amb)` | The ambience alone, crossfaded (no door, no reverb change): `AMB_NONE` on the title and the select | E |
| `au_restart()` | **Every attempt's start** (`restart_attempt()`, caught or START): stops the attempt's sounds (steps, the trains, doors, hiding, noises); not the caught sting, the music or the ambience | A |
| `au_retry()` | START restarts the room: a short rewind chirp (the catch has its own sting) | A |
| `au_caught()` | The catch (the freeze's first frame): the sting, and the music dips for a moment | A (`caught()`) |
| `au_thief(moved, running, dx)` | **Every tick**: the distance he moved this tick (m), whether R is held, his x less the camera's (`thief.x - cam_x`). Footsteps come from it: a soft step every 0.8 m walking, a heel strike every 1.3 m running; none while hidden or still | A (`tick()`) |
| `au_hide(on)` | Going into a hiding place (`true`), coming out (`false`) | A |
| `au_train(t, phase, head, dx, to_close)` | **Every tick, for every train** t of the room: `trains[t].phase as s32`, `trains[t].head`, the x of the middle of its part on the path less `cam_x`, and while it is stopped the ticks until its doors close (-1 otherwise). The arrival, the brakes, the doors, the door chime and the departure all come from it | A (`tick()`, after `trains_update`) |
| `au_exit()` | The thief goes through the exit (the staff door opens) | A |
| `au_transition()` | The pull-back between rooms starts (a slow air, 1.6 s) | E |
| `au_transition_skip()` | The pull-back is skipped (A): the air fades out at once | E |
| `au_menu_move()`, `au_menu_ok()`, `au_menu_back()`, `au_menu_deny()` | A menu's cursor moves; a choice is taken; back; a locked stage is chosen | E |
| `au_clear()` | A stage (a run) is cleared: the end line, or a stage unlocked | A or E |
| `au_alert(dx)` | A guard hears a noise and sets off toward it | A |
| `au_knock(dx)` | A fragile thing is knocked over | A |
| `au_bell(dx)` | The pocket bell beeps | A |
| `au_card(dx)` | (Stage 2) a keycard picked up | A |
| `au_unlock(dx)` | A staff door unlocked by its card (dx: the door's) | A |

The ambiences, for `au_room`: `AMB_NONE`, `AMB_PLATFORM` (Gate 1's platform and level 1's
first room), `AMB_GATES`, `AMB_PASSAGE`, `AMB_LOBBY`, `AMB_AQUARIUM` (0-5), and stage 2's
`AMB_CINEMA`, `AMB_BOOTH` (the projection booth), `AMB_CORRIDOR` (the staff corridor),
`AMB_SHOPFLOOR`, `AMB_FOODHALL` (6-10). *Proposal to A and B:* the
room type gets a field `sound: none | platform | gates | passage | lobby | aquarium = none` in
`afterhours.game.mochi`, set by each room's world recipe, and A passes it; until then A can map
level 1's rooms by their order (platform, gates, passage, lobby, aquarium) and Gate 1's platform
to `AMB_PLATFORM`.

`dx` is metres from the middle of the screen (the view is 13.2 m wide): a sound pans with it,
fully at the screen's edge, and a train beyond the edge grows quieter.

**Tests**: `weak fn au_heard(id: s32, ch: s32)` is called for every sound started (`SFX_*` from
`au_data.akr`); a harness can replace it to log what plays.

## How it behaves

- **The music never restarts on a catch or a restart.** It runs on across attempts and rooms; a
  catch dips it about 4 dB for half a second under the sting. The loop is long (about 84 s,
  longer than a room) and has no ending or build to land on a restart.
- **Restarts do not stack sounds**: `au_restart()` stops everything the attempt started; the
  steps, the alert and the knock each have one channel at most at a time (a new one restarts it);
  the sting restarts itself.
- **The trains are loops held each tick**: the running sound's pitch and level follow the train's
  speed, so it fits any timetable; a stopped train idles (its air conditioning). A loop nobody
  held this frame fades out over four frames, so in the caught freeze (no ticks) and the pause
  the trains go quiet by themselves. One-shots come from the changes between ticks: the horn as
  it comes out of the tunnel, the brakes as it stops, the doors opening, **the door chime 90
  ticks (1.5 s) before its doors close** (a warning the player can use), the doors closing. A
  room whose clock 0 finds a train already moving starts its loop without a one-shot.

## Channels

| Channels | What |
|---|---|
| 0, 1, 2 | The stage track: the rhythm (mono, dry) and the air (left, right; to the reverb) |
| 3, 4 | The ambience (mono; two so one room's can fade while the next one's starts) |
| 5, 6 | Two trains' loops (a third or fourth train shares the one-shots' channels) |
| 7-15 | One-shots, through `voice.akr`'s allocator: priorities sting 9, transition and menus 8, doors and trains 6, alert 6, knock 5, hiding 4, running steps 3, walking steps 2 |

The console's reverb: preset hall, its decay set per room by `au_room` (the passage longest, the
aquarium shortest). The music's air and most room sounds go to it.

## Wired (2026-10-15)

A imports `dr_audio.akr` in `afterhours.akr` and `tests/harness.akr` and calls every hook as in
the table: `au_tick()` at the end of every `update()` in every mode (the freeze's frames
included, so E does not call it), `au_music(true)` in `run_start()`, `au_room(amb)` in
`enter_room()` (level 1 mapped by room order, the platform level 1), `au_restart()` in every
`restart_attempt()`, `au_retry()` on START, the trains every tick, `au_clear()` before E's
`run_end()`. Not called yet: `au_pause` (no pause menu), `au_transition`, `au_transition_skip`
and the menus' four (E's).

**For E:** the cart starts the first stage's run in `init()`, so the track, the first room's
ambience and its door are already playing when your title opens. E calls
`au_ambience(AMB_NONE)` on the title and the select (the crossfade alone: no door, no reverb
change); the next `enter_room()` brings the room's ambience back. `au_transition()` is 1.6 s, to match the 1.5 s
pull-back; the next room's door (`au_room` from `enter_room()`) lands at its end.

## The sounds (for the owner's ears; the WAVs are `--preview`'s)

- **track**: "Shutters Down", 91.9 bpm in D minor: brushes, a sidestick and soft swung hats, an
  upright bass, a suitcase electric piano panning slowly between the speakers; then a nylon
  guitar's bossa comp, a shaker and the vibraphone's tune; a breakdown of strings and slow
  vibraphone arpeggios; the groove again with the vibraphone answering. Original chords and
  tune, no fill or ending at the loop.
- **step_walk**: a soft rubber sole on tile, barely there (walking is silent to the guards).
- **step_run**: a heel strike on tile with the toe's scuff, in the room's reverb.
- **caught**: a mallet cluster struck hard (D, G sharp, C sharp over a low D) with a short
  drop; under a second, so it never trails into the next attempt.
- **hide_in** / **hide_out**: clothes rustling and a soft settle; the rustle the other way.
- **train_horn**: a dark two-tone electric horn down the tunnel, with the air it pushes.
- **train_brake**: the brakes' squeal wavering as it slows to a stop.
- **doors_open**: the air's hiss, the doors sliding, their stop.
- **door_chime**: the warning before the doors close: a soft two-tone chime, twice, 1.5 s before.
- **doors_close**: the doors sliding and meeting with a rubber thud, a little air.
- **train_run** (loop): wheels, motors' whine and body rumble, a bogie pair over a rail joint;
  pitched by the speed. **train_idle** (loop): a stopped train's fans and converter.
- **door_open**: the staff door's push bar, a clunk, a short creak (the exit).
- **door_shut**: a heavy door closing behind him (each room's entry).
- **transition**: a slow air rising and settling, a low breath, a faint high vibraphone note.
- **menu_move**: a soft wooden tick. **menu_ok**: the vibraphone up a fifth. **menu_back**: the
  vibraphone down. **menu_deny**: a dull double buzz.
- **clear**: the vibraphone up a D major ninth over an electric piano chord.
- **alert**: two marimba notes rising, the second bent up like a question.
- **knock**: cans and boxes clattering down.
- **bell**: the pocket bell: a pager's beeps, three and three.
- **retry**: a short tape rewind (START).
- **card**: a keycard picked up: the plastic's snap and a small two-note pip.
- **unlock**: a card reader's beep, the magnetic lock letting go with a clunk, the door easing.
- **amb_platform**: ventilation, the tunnels' low wind, the tubes' hum. **amb_gates**: quieter
  room tone, the machines' standby tones. **amb_passage**: the tubes' 100 Hz buzz, one tube
  ticking now and then, long tunnel air. **amb_lobby**: the air handling and the city's rumble.
  **amb_aquarium**: the pumps' hum, the filters' bubbles, trickling water.
- Stage 2: **amb_cinema**: dead soft air, the projector clattering behind the wall.
  **amb_booth**: the projector itself at 24 frames a second, its motor, the lamp's fan.
  **amb_corridor**: the tubes, a duct's rush, a vending machine's compressor. **amb_shopfloor**:
  a large quiet, the air handling far off. **amb_foodhall**: the cold cases' two compressors
  beating, their fans.

## Costs

- **ROM**: 4.66 MB of the cart's 5.88 MB: the track 3.26 MB (three stems of 86 s at ADPCM's
  12.6 KB a second), the sounds and loops 1.41 MB (ten 9 s ambiences 1.13 MB). The levers: a
  16-bar track would save 1.6 MB; 6 s ambiences 0.38 MB.
- **Channels**: at most 16 (3 track, 2 ambience while crossing, 2 trains, 9 one-shots); in play
  usually 6-8. The console's mixing cost is fixed per channel playing (DECISIONS.md: 16 ADPCM
  channels with the reverb are about 0.1 ms of host time a frame).
- **CPU**: `au_tick()` and the calls cost at most about 4,100 cycles a frame in a debug build
  (0.4 %); level 1's worst frame is 2,266 cycles more with them than without (480,110 against
  477,844, scenario 46 with `TRAP=0`).
- **Levels** (the console's mix, no reverb): the track peaks at -8.3 dBFS (RMS -26.3); level
  1's run with everything peaks at -5.6 dBFS, nothing clipped. Every sound's level is a number
  in the generator's `ONE_SHOTS` and `LOOPS` tables, the track's `MASTER_PEAK`.

## Regenerate, listen

```sh
python3 tools/gen_afterhours_audio.py --preview build-ah-F/audio-preview   # about a minute
```

The previews: `track.wav` (the intro, the loop twice: its seam is at 1:26.8), its stems, a WAV
of every sound (loops three times), `play.wav` (the track's first 25 s with the platform's hum,
steps, a train arriving and leaving, a catch, hiding, the exit, the transition and the next
door). Not written by the generator, but in the same folder from the console itself:
`level1_run.wav` (scenario 46, level 1 played through with the cart's own calls, reverb
included: `tests/run.sh 46 5200 OUT --wav FILE`).
