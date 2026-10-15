# After Hours

**Status: design sketch, not implementation.** Nothing here is built. It records the owner's
decisions of 2026-10-14 and 2026-10-15 and proposes the rest; proposals are marked as such, and
the [open questions](#open-questions) are listed at the end. When the MVP starts, the contract
(owners, interfaces, gates) goes in this folder's `README.md`, as Fall Line's and Mech Expo's did.

## The game

A three-quarter-view stealth game set in a Tokyo complex at night, in the late 90s. A run goes
through one continuous chain of places. A rooftop shrine leads into an aquarium; the aquarium's
service corridor comes out behind a cinema screen; the cinema lets out into a department store,
the department store's basement into an underground mall, and the mall onto a subway platform.
Each place is one room: a small, finished world that is also a clockwork puzzle. Guards and
cameras move on fixed routes with their sight cones drawn on the floor, and being seen sends you
back to the room's door at once.

**The rooms are the game.** Each one should be worth stopping in: a platform where trains run to
a timetable, an aquarium lit blue through its tanks, a cinema with the projector still running.
The surprise of Tokyo is how these places open into one another in real space. A door at the
back of one turns out to be the way into the next, and the run is the route that strings them
together.

It draws on Metal Gear Solid: VR Missions (short rooms, instant retries), Bonanza Bros. (the
heist, the humour) and Monaco (the floor-plan readability). Because Mei is deterministic, a room
plays out identically on every attempt. That makes it a puzzle rather than a dice roll. Runs are
replayable from their inputs, so ghosts and speedruns come free.

## Decided

| Date | Question | Answer |
|---|---|---|
| 2026-10-14 | Camera | A fixed three-quarter view of a 3D diorama, to try. Gate 1 checks that it reads |
| 2026-10-14 | Being seen | Instant restart: a tough game with a quick feedback loop |
| 2026-10-14 | Who you play | One thief and their tools. The wind-up decoy toys may stay as one tool |
| 2026-10-14 | Planning between runs | Wanted, after the MVP |
| 2026-10-15 | What the game is about | The rooms: beautiful little worlds (a subway station with running trains, an aquarium with fish tanks and blue light) |
| 2026-10-15 | The conceit | How Tokyo's places connect in real space: a cinema becomes a mall becomes a station becomes a meditation room. The asset bubble is no longer the conceit |
| 2026-10-15 | The thief | Not convinced by the directions offered so far. Parked: the rooms come first |
| 2026-10-15 | Title | After Hours (the folder is renamed after Gate 1) |
| 2026-10-15 | A mascot suit tool | Yes, as a [tool](#tools), like Super Mario Bros. 3's tanuki statue; not the premise |
| 2026-10-15 | Camera angle | 60°, after the aquarium sketch's captures at 45°, 60° and 75° ([Gate 0](#gate-0-the-aquarium-sketch)) |
| 2026-10-15 | Gate 1 | Fun, but too hard. Fine as a greybox, though not handcrafted like the aquarium. Not sure about the toys, perhaps because of the difficulty |
| 2026-10-15 | Seeing into a train | Only through an open door: cones reach into a car through its open doors' gaps; its closed doors, sides and windows still block |
| 2026-10-15 | The first level | A gentler introduction of several handcrafted rooms, from the platform up to the aquarium ([Level 1](#level-1)) |
| 2026-10-15 | Tools in level 1 | None; tools arrive in later levels, one at a time |
| 2026-10-15 | Gentler | Caught only when a cone covers the thief's centre; one new idea per room; slower guards, shorter cones and fewer watchers in early rooms |

## Setting: one complex, end to end

Late-90s Tokyo. Terminal stations grew department stores on top and shopping streets underneath.
Office towers carry an aquarium or a planetarium on the roof. A department store keeps a shrine on
its roof, and a cinema sits on the eighth floor of a mall. From inside, these read as one
building with no edges, and that is what a run shows.

Every complex in the game is fictional, but built from places of the kind that existed. The
bubble stays in the background: much of this was built at its height, and some of it is
half-empty by 1998.

**A run** starts in one place and ends in another, crossing a complex in one direction:

| Room | What makes it beautiful | What makes it a puzzle |
|---|---|---|
| Rooftop shrine | Night sky, the city's lights below, a small torii, paper lanterns | An open roof with few walls; a posted guard by the stairwell; noise travels |
| Aquarium | Blue light through the tanks, fish moving behind glass, a tunnel tank | Tanks you can see through but not walk through: cones pass the glass, the thief does not |
| Cinema | Rows of seats, the projector's beam, the film flickering on the screen | The beam is a cone that never moves; an usher patrols the aisles; you cross behind the screen |
| Department store floor | Glass counters, mannequins, escalators stopped for the night | Mannequins as cover and as false alarms; an escalator is a one-way route |
| Food hall (depachika) | Lit cases of cakes and fruit, the melon counter, wrapped boxes | Stacked boxes are fragile things; a cleaner's cart on a fixed loop |
| Underground mall | A long tiled passage, shutters down, vending machines glowing | Long sight lines; pillars as cover; a shutter rises on a timer |
| Ticket gates | Rows of gates, the fare map, a station office window | The office has a camera; the gates are a gap to time |
| Subway platform | Trains arrive and leave on a timetable, their windows lit | A passing train blocks every cone across the tracks; its open doors are a way through |

Other candidates: a planetarium, a meditation room, a pachinko parlour, a capsule hotel, a sentō,
a karaoke floor, a game centre, a bookshop with a narrow staircase, a station hotel's lobby, a
rooftop beer garden, a batting cage on a roof.

**Why the thief is there** is open, along with the thief. The run's shape works for any reason
to cross a complex at night: something to take from the top, something to deliver to the bottom,
or the last train to catch. *Proposal:* the run ends on the platform, so **the last train** can
be the building's timer and the rank screen's best moment: you make it or you watch it leave.

## How it plays

### Rooms are clockwork

Each room has its own clock, which starts at 0 when you come through its door. Every guard,
camera, train and timer in the room is a function of that clock and of what you do, so the room
plays out identically on every attempt. Doors close behind you, and nothing carries from one
room's watchers to the next.

**The drawn cone is the test.** A watcher's sight is a fan on the floor, cut short by walls (and
not by glass). The polygon that is drawn is the same one the game tests the thief against, in the
same fixed-point numbers. If the thief's centre (the point he stands on) is inside the drawn fan,
you are seen; if not, you are not, however much of his body the fan covers. There is no hidden
check and no suspicion meter. (Gate 1 tested his whole 0.3 m footprint; the owner found that too
hard.)

### Caught means restart

When you are seen, the game freezes for about a third of a second. It shows a "!" and highlights
the cone that saw you. Then you are back at the room's door, with the room's clock at 0. Fewer
than 60 frames pass from the mistake to the next try. Start opens a pause menu with "restart
room" and "restart run".

Noise does not restart you. A guard who hears something walks to the sound, looks around for a
fixed time and walks back to his route. All of it is deterministic, so noise is a tool you can
plan with.

### Controls

| Input | Does |
|---|---|
| Stick or d-pad | Walk (silent). The thief moves freely, not on a grid |
| R (hold) | Run: about twice as fast, and loud (a noise ring is drawn on the floor) |
| A | Use what is in front of you: a door, a lock (hold), a hiding place, a lift button |
| B | Use the selected tool (throw, place, wind up) |
| L | Switch tool |
| Start | Pause |

X and Y are free for later tools or a peek.

### Tools

There are a few of each per room. The room decides which tools you have, so its puzzle is fixed.

- **Wind-up toy** (MVP): set down facing a direction. It walks in a straight line, clicking, and
  turns at walls. A guard who hears it follows it until it runs down.
- **Pocket bell** (MVP): a pager placed on the floor that beeps after 3 s. It's a fixed lure
  on a timer.
- **Mascot suit** (wanted by the owner, after Gate 1; Super Mario Bros. 3's tanuki statue is the
  reference): a store mascot's costume, found in the rooms that have one. In it the thief walks
  at half speed and cannot run; holding still, he poses, and a posing mascot is ignored by every
  cone, for as long as he holds. A guard walking past a posed mascot may pat its head. Moving
  inside a cone in the suit is caught as usual.
- *Later:* hairspray to fog a camera, a security guard's jacket, a cardboard box that only works
  on a guard who never looks down, a glass cutter for a second route.

### Watchers and moving things

- **Patrol guard** (MVP): walks a loop of waypoints, waits at some, looks a set direction at each.
- **Posted guard** (MVP): stands still and turns his head on a cycle.
- **Security camera** (MVP): a sweep between two angles. It cannot leave its post or hear.
- **Timetabled machinery** (MVP: the trains): things that move on the room's clock and change
  what can be seen or crossed. A train's sides block sight across the tracks, but an open door
lets a cone into the car, so a stopped train is not a safe place to stand; later, escalators, lifts,
  shutters and a projector's beam.
- *Later:* a dog that follows your recent path, a guard who checks hiding places, a night
  cleaner on a loop, lights you can switch off (shorter cones in the dark).

### Fragile things

Stacked melon boxes, a pyramid of cans, a sign on an easel. Brushing one makes a loud noise and
changes nothing else.

### The run and its rank

A run is 5–8 rooms. At the end, the rank screen shows each room's time, restarts and tools used,
and the run's total time. The total counts every attempt, so retrying a room costs time. A room
cleared with no restarts is marked clean.

The successful attempt's input tape is kept for each room. The best tape is drawn as a ghost on
the next visit, and the best tapes are saved to the memory card.

## The look

- **Each room is a finished diorama.** It is lit for its place: blue through the aquarium's
  tanks, the cinema's grey flicker, the food hall's warm cases, the platform's fluorescent
  tubes. The Asset Kit bakes one directional light per recipe and has no point lights, so glows,
  pools of coloured light and soft shadows are painted into the floor's texture by the room's
  script, as the aquarium's are. That painted floor light is the cheapest and strongest tool the
  sketch found. Fog does little looking down from 28 m.
- **Light, not detail.** At about 24 px per metre, anything under about 0.3 m reads as texture,
  and text 0.36 m tall is 4–5 px. Signs are lit shapes and pictograms, not words.
- **The complex is a sectional model.** Rooms are dioramas cut from one building. The walls
  nearest the camera are cut at about 1 m, like an architect's section, and the camera's yaw
  never changes. So this is a building rule for every room's assets: no wall ever has to fade.
- **Between rooms, the camera pulls back** to show the current room in its place in the
  section: the room above you, the room you are heading into. The neighbours are drawn as
  low-detail stand-ins (the World Kit makes them). The connection is the moment the game is
  about, so it gets a second on screen, not a cut.
- **The rank screen** is the whole section, zoomed out, with your route traced through it from
  the roof to the platform.
- **The void** around the section is dark, on the Horizon Engine's planes at no CPU or GPU cost:
  a night sky above the roof, the city's lights, and the earth under the platform.
- **Sight cones** are semi-transparent flat fans just above the floor, depth-tested and drawn
  after the opaque scene. They're pale yellow and turn red when they catch you.
- **Camera.** Fixed yaw, on the room's −Z side looking toward +Z, 60° down from horizontal,
  with a 20° vertical field of view (near orthographic) from about 28 m away. That gives about
  24 px per metre in the middle of the room. A room about 11–12 m across fits one screen; a
  larger room (the platform, the passage) pans with the thief.
- **People** are about 23 px tall on screen. They read by colour and by what they carry, not by
  shape: the thief by one strong colour that no guard or prop uses, a guard by his torch and his
  cone.

## How it is built

- **Each complex is a World Kit world** on a game schema of the cart's own. The kit is meant
  to serve games built from discrete levels
  ([WORLDKIT.md](../../docs/WORLDKIT.md#what-this-is-for)). Every wall and prop is an Asset Kit
  recipe, and the rooms, watchers, routes, trains and tools are game entities with stable IDs.
  A sketch of the schema in Mochi (the names and fields are proposals; the World Kit parses it):

  ```
  game dorobo

  probe {
    radius            = 0.3
    height            = 1.7
    floor_max_degrees = 40
  }

  worlds complex

  type room {
    entry:  ref
    exit:   ref
    toys:   u8 = 0
    bells:  u8 = 0
  }

  type waypoint {
    next:   ref?
    wait:   u8 = 0
    look:   s16 = 0
  }

  type guard {
    kind:   patrol | posted | camera
    route:  ref?
    sight:  fixed = 6
    fov:    u8 = 60
  }

  type train {
    path:     name
    period:   s16
    offset:   s16 = 0
    dwell:    s16 = 0
  }

  type hide_spot
  type fragile
  type glass
  ```

- **Walls for the cones.** A room needs 2D wall segments to cut the fans against, and to tell
  them apart from glass. The options are rays against the world's collision walls, or a wall map
  exported per room. Gate 1 picks one.
- **The thief and guards** are rigged Asset Kit models posed by the Animation Kit, like Mech
  Expo's mechs: walk, sneak, run, pick a lock, hide, caught; and patrol, look, turn, alert.
- **Every room has a solution tape**, a scenario in `tests/` that plays a known solution and
  checks that it reaches the exit unseen. A change that breaks a room fails `make test-carts`.

## Budgets

**Measured** on the aquarium sketch at 60°, in depth mode, drawn by `mei-headless`
([its notes](rooms/aquarium/shots/NOTES.md); the frame budgets are 1,000,000 CPU and 2,000,000
GPU cycles):

| Frame | Triangles submitted / drawn | CPU cycles | GPU cycles |
|---|---|---|---|
| The room (1,493), a stand-in thief (116), one guard (168) and his cone (16) | 1,793 / 1,086 | 221,559 (22%) | 362,897 (18.1%) |
| The same with three guards and cones | about 2,150 / 1,226–1,278 | 255,402–260,059 (26%) | 369,139–419,444 (21% at most) |
| What the glass costs: the window, the column and the cube, three water surfaces (64 triangles) | | 24,943 | 55,086 (2.8%) |
| Everything semi-transparent: glass, jellyfish, light shafts, cones, shadows (a third of the picture) | | 54,539 | 83,723 (4.2%) |

Back faces are culled, so about 60% of what is submitted is drawn. The CPU costs about 120
cycles a submitted triangle. The room uses 61 KB of VRAM for its textures. The GPU is not the
limit at this framing, and the glass was not the worst case it was feared to be: the limits are
pixels per metre and how much floor tall things hide.

**Proposed budgets** from those numbers. The figures read by colour at 23 px, so they need far
less than first planned, and the room gets the difference:

| Item | Budget (submitted) |
|---|---|
| Room: walls, floor, furniture, glass, its machinery | 2,500 triangles |
| Thief | 250 triangles |
| Watchers, up to 4 | 200 triangles each |
| Sight cones, 16 rays each | 16 triangles each |
| Frame total | about 3,600 triangles, about 430,000 CPU cycles to draw (43%), leaving more than half the CPU for the game |

Sight on the CPU (16 ray casts per watcher against a few dozen wall segments) is not measured
yet; Gate 1 measures it.

## The MVP

| In | Out (later) |
|---|---|
| One complex, about 6 rooms, from the roof to the platform. *Proposal:* rooftop shrine, aquarium, cinema, food hall, underground mall, subway platform | Other complexes |
| Patrol guards, posted guards, cameras, trains on a timetable | Dogs, lights, cleaners, escalators, lifts |
| Two tools: the wind-up toy and the pocket bell | Other tools |
| Hiding places, locked doors, fragile things, glass | Safes, shutters |
| The pull-back between rooms; the section on the rank screen | |
| Instant restart, the rank screen, per-room ghosts saved to the memory card | Online ghosts, leaderboards |
| Title, play, rank | The planning phase |
| One stealth track, a cue for the last train, the core sound effects, each room's ambience (the tanks' hum, the projector, the trains) | More music |

## Level 1

**The first level** is a gentle introduction: about five handcrafted rooms, from the platform up
to the aquarium on the roof, each teaching one idea before the last combines them. No tools.
Gate 1's hard platform is kept for a later level (perhaps the same station on the way home).

| Room | Teaches | Watchers |
|---|---|---|
| 1. The platform, gentle: you arrive on the last train | What a cone is, and timing it | One posted guard turning his head on a slow cycle |
| 2. Ticket gates and the station office | Hiding | One patrol guard; a hiding place in the office |
| 3. The underground passage, tiled, shutters down | Pillars cast sight shadows | A camera sweeping the passage; pillars |
| 4. The lobby and a stopped escalator up into the building | Two routes crossing | Two patrol guards; the escalator as the only way up |
| 5. The aquarium on the roof | Glass: cones pass it, you don't | Several, combining the above; the tanks are the reward |

The rooms and watchers are a proposal for the level lead to change; what is decided is the
route, the gentleness and no tools. Early rooms get slower guards, shorter cones and fewer
watchers. Rooms join by doors: the next room loads when the thief goes through, and its clock
starts at 0. The pull-back between rooms comes later.

**Who builds it** (all Opus):

- **The level lead** (agent B, who built Gate 1's room) owns the route, how the rooms join in
  the World Kit (it keeps one world open at a time today), each room's floor plan, puzzle,
  watchers and solution tape, and the difficulty curve. The lead builds each room in greybox
  first, then hands its floor plan to a room builder.
- **The stealth core** (agent A) makes the rule changes: the centre test, sight through a
  train's open doors, moving from room to room, and the run's total.
- **The aquarium's builder** (the agent that sketched it) relights it with the Asset Kit's point
  lights and fixes the tank top that reads as a second window, to the lead's floor plan.
- **Room builders**, two rooms each, dress rooms 1–4 to the standard of the aquarium sketch, on
  the lead's floor plans. They start when the plans exist.

## Gates

0. **A room sketch** (done 2026-10-15). [Below](#gate-0-the-aquarium-sketch).
1. **A greybox room that plays.** The platform built from boxes, playable from the door to the
   exit, with the stealth rules in. Shown to the owner to judge the feel. The plan is
   [below](#gate-1-plan).
2. **Two rooms joined.** Two finished rooms and the pull-back between them, with the thief and a
   guard modelled and animated.
3. **The MVP.** Everything in the table, within budget, with every room's solution tape passing.

### Gate 0: the aquarium sketch

One Opus agent built the aquarium, dressed and lit, with a stand-in thief and a guard's cone,
and captured it through Mei at 45°, 60° and 75°. The files are in `rooms/aquarium/`:
`make_aquarium.py` writes the five recipes and draws the textures, and `capture.py --verify`
checks, packs and renders them into `build-dorobo-sketch/` in about 10 s. The shots, the full
figures and the agent's notes are in [`rooms/aquarium/shots/`](rooms/aquarium/shots/NOTES.md).

What it settled: the camera (60°, chosen by the owner), the [budgets](#budgets), and the art
rules under [The look](#the-look) (painted floor light, no readable text). What it left for
later: the ocean tank's open top shows above the back wall and reads as a second window; the
kit's camera preview draws one asset at a fixed 60° field of view, so rooms need `capture.py`'s
own carts to be seen as the game sees them.

### Gate 1 plan

**The question it answers:** is a room fun to play at 60°? Everything a player touches is in;
nothing is dressed.

**The room:** the subway platform in greybox, about 30 m long and 10 m deep, so the camera must
pan. One island platform between two tracks, pillars, benches, a stair at one end (the way in)
and a staff door at the other (the exit). Two patrol guards, one posted guard and one security
camera. A train on each track on its own timetable, with lit boxes for carriages; a stopped
train's doors open, and a train blocks every cone across its track. Two fragile things and two
hiding places. The thief has two wind-up toys and one pocket bell. The puzzle is B's: it should
take a new player a few minutes and a few dozen restarts, and have more than one solution.

**In:**

- The thief's movement as in [Controls](#controls): walk, run with its noise ring, use, tools.
- Sight: the fans cut by walls and pillars and not by glass, drawn and tested as one polygon.
- Hearing: guards walk to a noise, look around, walk back.
- The wind-up toy and the pocket bell.
- The room clock, the caught freeze and the instant restart.
- The input tape of each attempt, the best one drawn as a ghost on the next.
- A line of text after the exit: the time and the restarts. No menus.
- Stand-ins for everything: capsules for people, boxes for the room, flat colours, the cone's
  real colours. Placeholder beeps if they help the feel; no audio work.

**Out:** art, animation, music, the pull-back between rooms, menus, the memory card.

**Agents** (both Opus, from the [team](#team-proposal); a shared checkout, private build
directories `build-dr-A` and `build-dr-B`, no commits; the main session integrates):

| Agent | Writes |
|---|---|
| A, stealth core | `dorobo.akr` (the entry point) and the runtime: the room clock, the thief, sight, hearing, watchers, trains, tools, restart, tapes and ghosts, the camera's pan. The cart's tests: `tests/harness.akr`, `tests/run.sh`, `tests/check.sh` |
| B, the complex | `dorobo.game.mochi` (A asks for the fields the runtime needs), `worlds.txt`, the platform's world recipe and greybox assets in `rooms/platform/`, the timetables, the puzzle and its solution tape |

A writes stubs of its interfaces first, so B can build the room against them. B's greybox is
deliberately plain: Gate 2 dresses it.

**Decisions Gate 1 makes, and reports with its reasons:**

- Walls for the cones: rays against the world's collision walls, or a wall map per room.
- What a cone tests against: the thief's footprint as a circle or as a polygon.
- Whether the World Kit suits a room: the schema, entity placement, collision and the
  stand-ins it will make for the pull-back. If it fights the room, B says how, specifically.
- The tape's format, and how a ghost is drawn.
- How the camera pans in a long room without hiding the cones that matter.

**Checks** (`make test-carts` runs `tests/check.sh`):

- The solution tape reaches the exit unseen.
- A tape that walks into a cone is caught on the frame the drawn fan first covers the thief, and
  restarts at the door.
- The same tape played twice gives the same state on every frame.
- Each train's cone blocking lines up with where the train is drawn.

**Delivered to the owner:** the cart (`make B=build-dr-A build-dr-A/mei
build-dr-A/carts/dorobo.mei`, then `build-dr-A/mei build-dr-A/carts/dorobo.mei`), captures of
the room at a few moments (a train passing, a cone cut by a pillar, the caught freeze), and the
worst frame's CPU and GPU figures, with sight's CPU cost on its own. The owner plays it and
judges the speeds, the cone reading, the restart's timing and the trains' rhythm. (Done
2026-10-15: fun but too hard; see [Decided](#decided) and [Level 1](#level-1).)

## Team (proposal)

Following [Mech Expo's pattern](../mechexpo/README.md#folders-and-owners): a shared checkout,
a private build directory per agent, and the main session integrating and committing. The rooms
are the game, so they get their own builders.

| Agent | Owns | Model |
|---|---|---|
| A, stealth core | The room clock, thief movement, sight and noise, watchers, trains, tools, restart, tapes and ghosts | Opus |
| B, the complex | The game schema (with A), how the rooms connect, the section, the stand-ins, each room's puzzle and solution tape | Opus |
| R1, R2, R3, rooms | Two rooms each: their architecture, props, lighting and machinery, within B's floor plans | Opus |
| C, characters | The thief, guards and camera as models, and their animations | Opus |
| D, small props | Fragile things, signs, vending machines, the small stuff the room builders ask for | Sonnet |
| E, front end | The camera, the pull-back, the void, the HUD, the rank screen | Opus |
| F, audio | Music, sound effects and each room's ambience | Opus |

## Open questions

- **The thief:** who they are and why they cross the complex. Parked until a room exists.
- **What the run is for:** something to take, something to deliver, the last train, or several
  of these.
- **Which way a run goes:** down from the roof to the platform, or up from the platform to the
  roof.
- **The wind-up toys:** keep them as the signature tool, or make the tools all 90s gadgetry?
- **Co-op later?** Two thieves would change the camera and every room. Ruled out for the MVP.
- **Music:** late-90s Tokyo suggests Shibuya-kei and acid jazz, in style only.
