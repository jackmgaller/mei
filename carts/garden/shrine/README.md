# The shrine slice

A vertical slice of the platformer: one Mario 64-sized level taken all the way (terrain,
textures, dense props, life and sound, things to do), to learn how much *stuff* a fulfilling
space needs and what it costs. The owner's vision, from a shrine they visited in Kyoto: a shrine
encircled by a giant forest you can go through. Designed with the owner on 2026-10-04; nothing is
built yet.

![From the road](from_road.png)

`layout.py` draws these sketches (`from_road.png`, `from_mountain.png`, `top.png`) from a rough
height model and an object list. The numbers below are the plan in metres; the world recipe will
own the exact ones.

## Size and shape

192 × 288 m (x east, north up): the road at the south, the shrine in the middle, the forest all
round it and running 96 m further north up a back mountain of about 60 m.

## Zones, south to north

- **The street:** a konbini and a building south of the road, the big torii at the road.
- **The outer courtyard** (street level, raked gravel): a stone approach between two long red
  side halls.
- **The inner precinct** on a 5 m stone terrace inside a white wall, entered through a two-storey
  red gate (about 17 m): two corridor halls, stone lanterns, the main temple on an 8.6 m platform
  at the back, and a five-storey pagoda (about 30 m) in the north-east corner.
- **The forest:** red maples, yellow ginkgo and tall cedars, rising to a wooded ridge (about
  20 m) behind the temple, then a deep northern forest climbing the back mountain, with a cliff
  band near the top.
- **The pond** east of the shrine, fed by a stream from the waterfall.

## The forest loop

One trail, entered at the south-west and ending at the shrine:

1. Fallen log, mossy boulders, stepping stones (west forest, ground level).
2. The **treetop walkway**: wooden platforms on giant cedars from about 10 to 24 m, joined by
   rope bridges.
3. The **clearings**: the **fox shrine grove** (a little tunnel of torii, a vermilion shrine, fox
   statues), the **sacred tree** (a huge cedar with a shimenawa rope), the **waterfall clearing**
   (falls of over 30 m off the back mountain).
4. The summit: a **hall on a Kiyomizu-style stage** on stilts, reached over a rope bridge, with
   long glide lines down towards the waterfall and the sacred tree.
5. Down the stream (a hollow log, a stream crossing) to the **pond crossing**: stepping stones,
   bobbing logs, a stretch of zig-zag red bridge, lily pads.

**The pond is mandatory:** the shrine's wall has no north or east gate and a bamboo fence closes
its east side, so the only way out of the forest and back to the shrine is across the pond.
**Water is wading:** falling in slows the player down; there is no swimming.

## Collectibles

- **8 red coins** along the forest loop.
- **Coins on the rooftops:** the main temple, the four halls, the two-storey gate, the torii, the
  konbini and the building; the pagoda's top and the highest treetop platform.

## Decided

- The slice is this shrine (the owner's sketch), grown to a full level rather than a corner.
- Verticality: the terraced precinct, the pagoda, the gate, the treetop walkway, the mountain
  stage.
- Pond crossing mandatory; water is wading.

## Open

- A shortcut back into the forest after the loop (a gate that opens, Mario 64-style).
- Goals beyond coins: the bell, the night festival, omikuji slips, the fox shrine, a cat; and how
  many for a level this size.
- Day and night (the festival at night).
- Whether the slice is a second world in the garden cart (reusing its controller, camera and
  tests) or a cart of its own. My recommendation: a second world in the garden cart.

## What it needs before production

- **World Kit terrain** (heightfields, swept paths): in progress.
- **Textures in worlds** (the World Kit packing textures per region, animated textures, the 8-bit
  night tint): next, after terrain. Textures in the Asset Kit are built.
- Then production in the usual shape: a world lead for the level, asset workers by family
  (shrine buildings, forest and foliage with cutouts, the pond crossing, street and signage),
  and agents for goals and for sound.
