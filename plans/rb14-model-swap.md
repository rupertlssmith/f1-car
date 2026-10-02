# Plan: turn the redbull mod into a Red Bull RB14

Replace the visual model of `vehicles/redbull/` (a renamed Carbonworks F4) with
the RB14 model in `redbull/source/rb14.glb` + `redbull/textures/`, re-fit the
physics (jbeam) to the RB14's size, and then tune it to drive like a 2018 F1 car.

Work happens on `master`. Each milestone ends with a build
(`python3 tools/build_mod.py`) that is tested in BeamNG.drive.

## Starting point

| | Current mod (F4) | RB14 model |
|---|---|---|
| Size | jbeam spans ~1.5 m wide × 4.4 m long × 1.0 m tall | 2.05 m wide × 5.39 m long × 1.18 m tall (metres) |
| Mesh split | ~100 meshes, one per component, named to match jbeam flexbodies (`redbull_nose`, `redbull_wing_F`, …) in `F4.dae` + `common/redbull_wheels/F4_wheels.dae` | 30 meshes split **by material**, not component (one 55k-tri carbon mesh spans wings, floor and bodywork; all four tyres are one mesh) |
| Axes | Collada Z-up, nose towards −Y | glTF Y-up; forward direction to be confirmed |
| Triangles | — | ~150k (fine for BeamNG) |
| Textures | `.dds`, F4 UV layout, 10 liveries | 22 `.png` in the RB14 UV layout, one livery |
| Physics | 18 jbeam files, 236 nodes, 180 hp I4, F4 mass/aero | — |

How BeamNG ties them together: jbeam nodes/beams are the physics; each visible
part is a `flexbodies` entry naming a mesh in a `.dae` and the node group it
deforms with. A part only works if the mesh with that name exists **and**
sits on its nodes. Materials are resolved by name from `*.materials.json`.

## Tooling

All scripted and repeatable from the source `.glb` and the untouched F4 in
`vehicles/fr04`, so the model can be re-processed after any fix instead of
hand-edited. Pure Python (numpy; trimesh only for colour previews) except
the renders, which use headless Blender.

| Script | Does |
|---|---|
| `tools/jbeam.py` | Tolerant jbeam / relaxed-JSON reader (comments, trailing and missing commas) |
| `tools/rb14/glb.py` | Reads `rb14.glb` directly (geometry, UVs, embedded textures) into BeamNG axes |
| `tools/rb14/dae.py` | Collada reader/writer in the layout the F4's Blender export used. Ubuntu/Debian Blender builds ship **without** Collada, so the pipeline does not depend on Blender for `.dae` |
| `tools/rb14/fitmap.py` | The F4 → RB14 coordinate map: piecewise-linear along the car through stations (wing tip, wing trailing edge, front axle, steering wheel, roll hoop, rear axle, tail), with width and height breakpoints (tub, wheel faces, floor with the RB14's rake, hub, cockpit rim, halo, hoop). Monotonic, so no beam can invert |
| `tools/rb14/fit_jbeam.py` | Applies the map to every jbeam coordinate (nodes, wheel `nodeOffset`s, wing pivots, brakes, cameras, mirrors), always from the F4 originals, so re-running never compounds. Expression coordinates stay expressions, rescaled |
| `tools/rb14/build_model.py` | Splits the RB14 into the F4's part names by position rules, carries over the F4 internals that fit inside the RB14 (moved through the same map), writes `redbull.dae`, `redbull_wheels.dae`, materials and textures |
| `tools/rb14/materials.py` | RB14 → BeamNG material names and definitions; textures written as PNG with BeamNG's `_b.color` / `_n.normal` naming for the game to cook |
| `tools/rb14/sync_jbeam.py` | Comments out (`// rb14: no mesh`) jbeam flexbody/prop rows whose mesh no longer exists |
| `tools/rb14/envelope.py` | Which points are hidden inside the RB14 bodywork (used to decide which F4 internals to keep) |
| `tools/rb14/preview.py` | Assembles the *built* mod (the `.dae`s, materials and textures the game loads) into a textured `.glb`, wheels and wings placed like the jbeam does |
| `tools/rb14/render.py` | Blender (headless) preview renders, optional jbeam node/beam overlay and close-up camera |
| `tools/check_mod.py` | Consistency checks, run by every `build_mod.py` (errors refuse the build; `--no-check` skips): every reference (nodes, node groups / properties, `$variables`, named beams, deform groups, powertrain inputs, wheels, storages, rails, triggers, electrics read by hydros / thrusters / props) in the default car, every configuration and with each optional part fitted; the mod's Lua controllers run (luajit, `tools/rb14/check_controllers.lua`) on each car's nodes; meshes, materials, textures, config info / thumbnails, actions and key bindings. Known F4 leftovers are listed as accepted notes (`ACCEPTED`); `--fit` measures how far each flexbody's vertices are from its nodes |
| `tools/rb14/f1_setup.py` | Milestone 4: turns the re-fitted F4 physics into the 2018 F1 setup (mass, tyres, suspension, alignment, power unit, gearbox, diff, brakes, aero, ERS/DRS, ride-height floor, the four configs). Sets absolute values, calibrating against `setup_report.py`, so it is safe to re-run |
| `tools/rb14/setup_report.py` | Offline setup sheet read from the jbeam the way the game merges it: mass and balance, a linear spring-network model of each axle (wheel/heave/roll rates, ride frequency, static sag), flat-plate aero by part (and with DRS open), torque/power, gearing, a straight-line launch sim, tyre-limited lateral and braking g. `--config <name>` for a `.pc` |
| `tools/rb14/jbeam_edit.py` | Format-preserving (CRLF, comments) jbeam text edits used by `f1_setup.py` |
| `tools/rb14/replay_analysis.py` | Reads a BeamNG replay (`.rpl`: Ogg stream of MessagePack frames with JSON electrics / sensors / powertrain) and reports performance (acceleration, rear-wheel power, implied resistance, peak g) and steering (front / rear wheel angles from the steering check, rear toe, yaw rate after hard turns). `--csv` dumps the per-frame series. Needs `msgpack` |
| `tools/rb14/variants.py` | Front-fix test cars (`fix_*.pc`, "Front Fix N · ..." in the game), safest first, each run through the offline checks; test sheet `plans/front-fixes.md`. `build_mod.py --test` packs only Baseline + these; `--no-variants` leaves them out. (The earlier setup sweeps are recorded in `plans/sweeps-archive.md`.) |
| `tools/rb14/test_controllers.lua` | Runs the ERS, DRS and ground-effect Lua controllers against stubbed BeamNG globals (`luajit tools/rb14/test_controllers.lua`) |

Rebuild after changing any of these:

```bash
python3 tools/rb14/build_model.py   # meshes, materials, textures
python3 tools/rb14/sync_jbeam.py    # drop jbeam rows for meshes that went away
python3 tools/rb14/fit_jbeam.py     # re-fit coordinates (idempotent)
python3 tools/rb14/f1_setup.py      # F1 physics and configs on top (idempotent)
python3 tools/check_mod.py --fit    # must report 0 errors
python3 tools/rb14/setup_report.py --config baseline   # numbers vs the targets
luajit tools/rb14/test_controllers.lua                 # Lua controllers
python3 tools/rb14/variants.py      # front-fix test cars + plans/front-fixes.md
python3 tools/build_mod.py          # dist/redbull_<timestamp>.zip
```

Previews go to `plans/previews/` (committed) so progress can be reviewed
without the game.

## Status

- **Milestone 1 - done (awaiting in-game test).** The RB14 body, aero,
  cockpit, steering wheel (with the dashboard display on its LCD), wishbones,
  uprights, rims and 2018-size tyres are in; the F4 physics is re-fitted to
  the RB14's 3.555 m wheelbase and track, its rake and its wheel centres. The
  split went straight to Milestone 2's component level (nose, wings and
  endplates, sidepods, engine cover, floor... keep the F4's breakable
  parts), so the "one big body flexbody" step was skipped. `check_mod.py`:
  0 errors (21 warnings, all inherited from the original F4 jbeam).
  Previews: `plans/previews/m1_*.png`.
- **Milestone 3 - done.** Four configs (`lowdf`, `baseline`, `highdf`,
  `aggressive`) with thumbnails, F4 skins and liveries removed, metadata and
  mod manager info.
- **Milestone 4 - done offline (awaiting in-game test).** All of it is
  applied by `tools/rb14/f1_setup.py`; details and the in-game checklist are
  under "Milestone 4 result" below. Not done: flipping the rear pushrod to a
  pullrod in the physics (the RB14 pullrod mesh is shown; the corner spring
  acts hub-to-chassis, so the rod layout doesn't change the rates), tyre
  thermals/wear beyond BeamNG's own.
- **Fixed on the way:** front brake discs/calipers were placed at the rear
  axle since Milestone 1 (front and rear brakes share mesh names; the fit
  now keys them by node group too).

## Milestone 1 — Rough visual swap (drives in-game, looks like an RB14)

1. **Inspect the model.** Run `inspect.py`; confirm forward axis, scale,
   and list the loose pieces inside each material mesh. Render reference views.
2. **Orient and scale.** Rotate to Z-up, nose towards −Y; wheels on the ground
   plane at z = 0 like the F4. Keep real-world scale (5.39 m).
3. **Coarse split.** Separate into a handful of parts only: body (everything
   rigid), four wheels, four tyres, steering wheel. Wheels/tyres split by
   position (FL/FR/RL/RR), then one front and one rear wheel/tyre kept and
   centred on the origin, as the existing wheel jbeam expects.
4. **Measure** wheel centres → wheelbase, front/rear track, tyre radii/widths,
   ride height.
5. **Re-fit the jbeam frame** (`fit_jbeam.py`): piecewise-linear remap of node
   x/y/z so that F4 wheel hubs → RB14 wheel centres, F4 chassis extents →
   RB14 body extents. Suspension pick-ups, wings and body nodes move with it.
   Update wheel/tyre radius and width in `common/redbull_wheels/*.jbeam`.
6. **Hook up the body.** Temporarily attach the whole RB14 body as one flexbody
   over all chassis node groups; hide the F4 bodywork meshes (remove their
   flexbody entries). Keep the F4 mechanical meshes for now if they sit inside
   the body; drop any that poke through.
7. **Textures (first pass).** Convert all 22 PNGs to DDS, define one material
   per RB14 material name, reusing the source texture maps as they are.
8. **Check + render.** `check_mod.py` clean; render the mesh with nodes
   overlaid from front/side/top.
9. **Build and test in game.** You check: car spawns, sits on its wheels,
   drives, nothing explodes, looks like an RB14 (jbeam debug view on).

## Milestone 2 — Proper parts (breakable wings, correct deformation)

1. **Full split** via `parts.json` into the components the jbeam already
   models: nose, front wing, front endplates L/R, rear wing, rear wing
   mounts, halo, mirrors L/R, sidepods, engine cover, floor, monocoque/tub,
   headrest, rollhoop, suspension arms/pushrods (if the model has them),
   steering wheel, rain light.
2. **Name each part after the F4 part it replaces** so the existing flexbody
   entries pick it up — detachable wings and nose keep working.
3. **Per-part node fit.** Refine `fit_jbeam.py` so each part's node group
   wraps its mesh (wing nodes on the wing, nose nodes on the nose, …);
   `check_mod.py` reports vertices too far from their group's nodes.
4. **RB14-specific parts.** Adjustable rear wing angle / DRS flap mapped to the
   existing wing-angle variables where possible.
5. **Cockpit.** Move driver camera, steering wheel prop, and the dash screen
   (HTML display) onto the RB14 steering wheel's LCD.
6. **Build and test.** You check: crash a wing off, nose damage, wheels steer
   and spin correctly, cockpit view.

## Milestone 3 — Materials, liveries and cleanup

1. **Materials polish.** Proper normal/roughness/metallic maps where the source
   provides them; glass, lights and decals with correct transparency;
   brake glow on the discs.
2. **Livery.** One RB14 livery as default. The ten F4 liveries (UV'd for the
   F4) are removed; configs reduced from 40 to the four aero setups
   (`lowdf`, `baseline`, `highdf`, `aggressive`) with new thumbnails.
3. **Remove leftovers.** F4-only meshes, textures and skin files no longer
   referenced; `F4.dae` → `redbull.dae`, `F4_wheels.dae` → `redbull_wheels.dae`.
4. **Metadata.** `info.json`: country, years, class; mod manager description
   and tagline; new thumbnails/screenshots.
5. **Build and test.**

## Milestone 4 — Make it drive like an F1 car

Red Bull's real RB14 setup data (spring rates, damper curves, aero maps) is not
public, so the car is set up from public 2018 F1 figures and informed
estimates, then tuned against measurable targets (below) in game.

### What the F4 already gives us

`redbull_suspension_F/R.jbeam` is built like an F1 suspension: double
wishbones with pushrods driving rockers, spring/damper on a rail
(`shock_F*`), separate bump/rebound dampers with fast/slow rates, front and
rear anti-roll bars, and tuning variables for camber, caster, ride height,
springs and dampers. We reshape and retune this rather than build new
suspension. Aero already uses jbeam wing surfaces with lift/drag
coefficients, and the mod already ships Lua controllers (pit limiter, brake
bias) as a pattern for custom logic.

### Work items

1. **Suspension geometry.** Re-fit wishbone, pushrod and rocker nodes to the
   RB14 pick-up points (done coarsely in Milestone 1, refined here). RB14 is
   **pushrod front, pullrod rear**: flip the rear pushrod to a pullrod
   (lower-chassis rocker, rod to the upper upright). Very little travel
   (a few cm), very low ride height, and Red Bull's **high rake** (rear set
   noticeably higher than front) as the default.
2. **Heave (third) springs.** Add a central spring + damper per axle between
   the left and right rockers, so the car resists aero load (both sides
   compressed together) separately from roll (corner springs + anti-roll
   bars). New tuning variables: heave spring rate, heave damping, heave
   packer gap. This is what keeps the platform stable as downforce builds and
   is the key change from F4 behaviour.
3. **Spring / damper / ARB rates.** Re-derive corner spring, heave spring and
   ARB rates from target wheel rates and natural frequencies for a 733 kg car
   with aero load; stiff rebound, bump stops/packers to cap travel.
4. **Aerodynamics.** Rescale wing and floor lift/drag so downforce ≈ car
   weight at ~150–180 km/h and ≈ 3–3.5× weight at 300 km/h, L/D ≈ 3–4, with
   an aero balance around 40–45 % front. The four configs (`lowdf`,
   `baseline`, `highdf`, `aggressive`) map to low/medium/high wing levels.
   **DRS**: rear flap that drops rear-wing drag and downforce on a button,
   via the existing wing-angle variables or a small controller.
5. **Ride-height-sensitive floor.** Much of 2018 downforce comes from the floor
   and depends on ride height and rake. BeamNG doesn't model ground effect
   natively, so write a Lua controller (`lua/controller/redbullFloorAero.lua`)
   that reads front/rear ride height each physics step and scales floor
   downforce (drops off when too high, stalls when bottoming out). Hardest
   part of the milestone; expect experimentation.
6. **Mass and balance.** 733 kg minimum including driver; ~45–46 % front
   weight. Set node weights; add ballast nodes to hit the total and balance.
7. **Tyres.** 2018 13" slicks: front 305/670, rear 405/670. High peak grip
   with strong load sensitivity (grip per kg falls as load rises), stiff
   sidewalls. BeamNG's tyre thermals and wear are basic, so tune for grip
   and feel rather than stint simulation. Wet tyres kept from the F4 setup.
8. **Power unit.** 1.6 L V6 turbo, ~750 hp from the engine plus ~160 hp
   (120 kW) electric boost. Start with an engine torque curve (rev limit
   15,000, used to ~12,000 rpm) plus an ERS boost button; a full
   battery/motor hybrid in BeamNG is a later option.
9. **Gearbox and diff.** 8-speed sequential with near-instant shifts and
   2018-typical ratios; limited-slip rear differential with adjustable
   preload/locking.
10. **Brakes.** Carbon-carbon discs: high torque, grip that needs temperature
    (BeamNG brake thermals), rear brake-by-wire approximated by the existing
    on-the-fly brake-bias controller.
11. **Test and iterate** against the targets below, one system at a time
    (platform → aero → tyres → power → brakes).

### Targets (measured in game)

Use BeamNG's built-in G-meter / telemetry apps; you record, we tune.

| Test | Target |
|---|---|
| 0–100 km/h | ~2.6 s |
| 0–200 km/h | ~5 s |
| Top speed (low-downforce config) | ~330–350 km/h |
| Peak lateral g, fast corners | ~4–5 g |
| Peak lateral g, slow corners | < 2 g (little aero at low speed) |
| Braking from 300 km/h | ~5 g peak, falling to mechanical grip as speed drops |
| Platform | ride height and rake stay controlled as downforce builds; no bottoming out or porpoising on a straight |
| Weight | 733 kg, ~45–46 % front |

The goal is a car that feels like a 2018 F1 car and hits these numbers, not a
replica of the real RB14 setup sheet.

### Milestone 4 result

Estimated offline by `setup_report.py` (BeamNG's exact aero and tyre models
aren't public: aero drag is calibrated on the F4's known top speed, lift uses
the same flat-plate model; the game is the ground truth).

| | lowdf | baseline | highdf | aggressive |
|---|---|---|---|---|
| Wing angles F / R / beam (deg) | -5 / 4 / 3 | -3 / 8 / 3 | 0 / 15 / 3 | 0 / 12 / 3 |
| ClA / CdA (m^2), front | 4.56 / 1.12, 43 % | 5.00 / 1.30, 43 % | 5.67 / 1.75, 43 % | 5.51 / 1.54, 44 % |
| Downforce at 300 km/h | 2.6 x weight | 2.8 x | 3.2 x | 3.2 x |
| 0-100 / 0-200 km/h | 2.7 / 4.9 s | 2.7 / 4.9 s | 2.7 / 5.0 s | 2.6 / 4.8 s |
| Top speed (DRS open) | 339 (347) km/h | 324 (345) | 294 (328) | 306 (338) |
| Lateral g, 300 km/h | 4.5 | 4.7 | 5.0 | 5.2 |

Every config: 1.9 g at low speed, 5-6 g braking from 300 km/h.

- **Mass:** 733 kg with driver and no fuel (777 kg with the configs' 60 L),
  45.5 % front, CoG 0.34 m. Power unit 145 kg, gearbox 40 kg, light
  corners, ballast in the plank.
- **Solver stability:** BeamNG integrates at 2 kHz, and every vibration
  mode of the node/beam network must stay below omega*dt = 2 or the solver
  pumps energy into it. `setup_report.py` computes the modes over the whole
  car, including an approximation of the hub and tyre nodes the game
  generates from `pressureWheels`; `f1_setup.py` refuses a setup above
  **1.65**. Calibrated on game tests: the F4 (fine in game) peaks at 1.84 on
  this model (wheel axles); our first M4 build (2.4) exploded, the second
  (1.96 at the wheel axles, 1.77 on the front bulkhead) lost its wheels and
  visibly shook in front of the cockpit. Fixes: suspension and steering
  beams capped at 4.5 MN/m (still ~25x the wheel rate), front steering-arm
  torsionbar 200 -> 80 kNm/rad, wheel hub beams at 40 % of the F4's with
  0.35 kg hub nodes, wheel axle nodes 4 kg (wheel clusters now 1.55), and mass moved from the plank
  ballast onto chassis and gearbox nodes (gearbox 40 kg). Ballast is solved
  for 733 kg / 45.5 % front; the CoG rose ~12 mm to 0.34 m.
- **Torque paths:** drive and brake torque reach the chassis through the
  nodes each wheel names, with force = torque / lever. The F4 (third test:
  rear struts bent under acceleration) named a drive coupling node that
  doesn't exist (so the game generated no drive reaction at all) and a
  torque arm 2 cm from the axle line; its rear brake arm was 7 cm from the
  axle. Now: coupling at the differential (10 kg), arms on the engine block
  -- the lower 25 kg node 0.77 m away and the opposite upper 11 kg node --
  after 5 kg gearbox arms 0.4 m away made the rear wheels shake and break
  pulling away in first gear (4.8 kNm per wheel); rear brake arm on the
  upper upright (13 cm, 16.5 kN).
- **Strength for F1 loads:** the F4's beams yield at forces sized for a
  650 kg car at ~1.5 g. `setup_report.strength_report()` loads each corner
  with aero at 300 km/h, 5 g braking, 4.7 g cornering and full traction
  (each x1.5 for bumps) and compares every beam with its beamDeform;
  `f1_setup.py` refuses anything above 50 %. The F4 values put the coilover
  springs at 105 % in cornering (they yield and shorten: the "bending
  struts" of the fourth test). Now: arms and wishbones 4x (rear 5x),
  coilovers, bump stops and anti-roll / heave bars 4x, steering 3x, rims
  and tyre beams 3x the F4's. Worst beam: 40 % (rear lower wishbone in
  4.7 g cornering). Note the linear model says arm stiffness isn't the
  visible flex (12 kN sideways moves a wheel 2-3 mm); yielding beams were.
- **Rim rings:** the pressure wheel's rim ring spins with the wheel. At the
  RB14's real rim widths (0.30 / 0.35 m, wider than the 0.27 m between the
  axle nodes) the rear ring's inner edge ran through the rear upright's top
  node, so the rear wheels caught once a revolution pulling away (fifth
  test). Rings are now 0.26 m wide, between the axle nodes like the F4's
  (tyres stay 305 / 405 mm); `f1_setup.py` refuses any node within 25 mm of
  a spinning wheel's rim/sidewall/tread section (closest now 38 mm; F4 40).
- **Round 7 (sixth in-game test):**
  - *Rear wing flexing at speed:* removing the leading edge's vertical mounts
    for DRS had left the wing nearly free (the linear model: ~200 mm at the
    trailing edge under its 6 kN). Now a central pylon (swan neck) from the
    trailing edge -- which DRS doesn't move -- to the crash structure, the
    wing's beams 3x stiffer and better damped, a stiffer DRS actuator,
    ~10 kg of wing assembly: 7 mm at the leading edge, 2 mm at the trailing.
  - *Wheel judder in skids / burnouts:* rim beams 55 % of the F4's (was 40 %)
    on 0.45 kg rim nodes (was 0.35), damping on the capped wheel-carrier
    beams raised to 400.
  - *Steering vague and off-centre after sharp turns:* the steering
    actuators moved at 1.25 (slower than BeamNG's default of 2), lagging the
    input up to ~0.8 s lock to centre. Now 4, with ~32 % more road-wheel
    angle per input and 180 deg of steering wheel to full lock (was 230).
    The lock stops still never engage; the tyres clear the front wing by
    51 mm up to 40 deg of steer.
  - *Rear too loose:* aero balance 43 -> 41 % front, front roll stiffness
    58 -> 62 %, rear toe-in 0.25 -> 0.40 deg, rear tyres ~5 % more grip
    than the fronts, brake bias 58 %, diff power lock 0.25 -> 0.20.
  - *Underbody scraping:* baseline ride height +10 mm front and rear
    (Spring Height 0 is the new baseline).
  - Sweeps are now relative to Baseline (`build_sweeps()`), so they follow it.
- **Round 8 (seventh in-game test):**
  - *Rear wing top broke off on spawn:* its pylon went to the crumple-zone
    crash box, which moves differently from the gearbox the endplates hang
    from; the F4-strength (5 kN) endplate-to-wing beams snapped. The pylon
    now braces from the gearbox top, front and rear; the wing's deform /
    break forces are 4x the F4's. Under 6 kN + drag: 7 / 6 mm, every wing
    beam under 8 % of its limit. The stability model now includes hydros
    (DRS and steering actuators), which it had missed.
  - *Wheel judder:* suspension beams capped at 6 MN/m (was 4.5), rims 65 %
    of the F4's stiffness on 0.45 kg nodes, carrier damping 600, heavier
    uprights and wheel axle nodes (4-5 kg); strengths 5x / 6x (F / R), rims
    and tyres 4x. Weight distribution 46.5 % front to fit the heavier
    corners (and help the rear).
  - *Pulling to one side pulling away:* the drive-torque reaction used a
    different diagonal pair of engine nodes per wheel; both wheels now use
    the same symmetric pair. The engine's own torque reaction (644 Nm of
    chassis roll, loading one rear tyre more) is off: in a longitudinal
    engine + transaxle it cancels through the gearbox.
  - *Revs flaring in low gears (wheelspin):* new torque-map controller
    (`lua/controller/redbullTraction.lua`, key **K**) trims the throttle
    when the rears slip more than 12 % -- the job 2018 per-gear torque maps
    did. On by default.
  - *More grip:* +6.5 % front and rear.
- **Round 9 (F4 -> F1 review, all 15 items; `migrations()` in
  `tools/rb14/f1_setup.py`, each scaled from the F4 original):**
  1. *Shift points:* the engine part's shift table (which overrides the
     transaxle's) was the F4's 7,000 rpm four-cylinder one. Upshift at
     12,000 rpm; each downshift lands the lower gear at ~11,500 rpm
     (8,850 ... 10,050 rpm); launch 7,000 / 7,500 rpm as the transaxle.
  2. *Tyre carcass:* tread / periphery beams 2.5x, rim reinforcement 5x,
     sidewall in extension 2x, damping 1.5x. (Undone in round 9c: unstable.)
  3. *Front wing:* wing beams 3x stiffer, 4x stronger; nose beams 1.5x on
     1.5x heavier nose nodes; ~8 kg wing assembly. Tip deflection under
     6.3 kN (300 km/h) 92 -> 46 mm, centre 34 -> 27 mm. Stiffer still puts
     the nose / bulkhead nodes over the solver limit.
  4. *Floor:* beams 1.5x stiffer (3x broke the solver limit on the F4's 1 kg
     floor nodes), 3x stronger; floor nodes back to the F4's weights. The
     ballast moved to the front of the tub floor (fx2, mt1) and to the
     engine sump / gearbox front (e2, rx1). CoG 0.361 -> 0.369 m.
  5. *Monocoque:* torsion (seat back held, couple on the front bulkhead,
     `monocoque_torsion()`) 4.7 -> 5.1 kNm/deg: the tub's beams up to
     3.5 MN/m are 2x stiffer and stronger, cockpit-rim and bulkhead nodes
     a little heavier. Doubling the 4 MN/m beams too would reach
     7.2 kNm/deg but needs ~6 kg more on the nose bulkhead, more than the
     front ballast has. A real tub is far stiffer; the 2 kHz solver is the
     limit here.
  6. *Wheel axle beams:* 2x stiffer, 3x stronger, damping 25 -> 100; hub
     damping 10 -> 40.
  7. *Cooling:* radiator 0.6 m^2, effectiveness 14,000, 8 L coolant,
     10 kg (was 25).
  8. *Engine damage thresholds* 3x (head gasket, piston rings, rods).
  9. *Clutch:* left as it was. BeamNG sizes the friction clutch's capacity
     from the engine torque; clutchFreePlay / lockSpringCoef are pedal feel
     and lock-up stiffness (no public documentation to check against).
  10. *Bodywork* (sidepods, engine cover, suspension fairings): deform /
      break forces 2.5x.
  11. *Sound:* pitch as a six-cylinder (the samples stay: BeamNG ships no
      V6 turbo-hybrid set).
  12. *Chase camera:* 6.8 m (min 2.5) for the 5.7 m car.
  13. *Hard travel stops:* ~57 mm bump front / ~64 mm rear (F4 ~120 / 90);
      the packers still act first.
  14. *Brakes:* brakeSpring 300, rear parking torque 3,000 Nm. ABS targets
      unchanged (only used if the player turns ABS on).
  15. *scaledragCoef 1.6* stays: the aero factors were solved with it.

  All gates pass: highest mode ω·dt 1.65, worst corner beam 0.35 of its
  deform limit, wheel clearance OK, all 54 sweep cars too.
- **Round 9b (in-game: rear wing shook itself off, tyres burst on spawn):**
  - *Damping in the stability model.* BeamNG integrates beam damping
    explicitly too, so a mode stays stable only while
    (omega*dt)^2 + 2*gamma < 4 (gamma = modal damping * dt / mass).
    `setup_report.stability_report()` now reports this damped measure
    (beams, hydros, torsionbars, generated hubs; beams with dampCutoffHz
    count as undamped, the generated tyres' damping is left out because
    the approximation puts the F4's own tyres at the limit). The F4 peaks
    at 1.97. The rear wing's DRS leading edge was at **2.02**: the damping
    floor of 150 on the wing beams plus 200 on the DRS actuators and pylon,
    on 0.6 kg nodes. Now the F4's wing damping, 40 on actuators and pylon:
    1.74 (F4 1.69), still 7 / 6 mm under 6 kN. New gate: damped <= 1.85
    for every config and sweep car (worst now 1.82). Also back to the
    F4's: hub damping (40 -> 10) and front wing damping (1.5x -> 1x); crash
    box nodes 1.15 -> 1.4 kg.
  - *Tyres burst and dented:* round 9 made the carcass beams 2.5x stiffer
    but kept their deform / break forces, so they yielded and broke at 40 %
    of the stretch they used to take. Deform / break forces now scale with
    the stiffening (tread and periphery 2.5x, sidewall 2x); rim
    reinforcement 2.5x (was 5x).
- **Round 9c (in-game: the rear wing stays on; the tyres shook violently at
  spawn, the fronts turned inside out and tore off; without tyres nothing
  moved):** the round-9 carcass stiffening (item 2, 2.5x) is undone -- the
  tyres are exactly round 8's (F4 springs and damping). With round 9's old
  deform limits the stiffer tyres burst first; with 9b's scaled limits
  nothing gave way and the instability showed. Our tyre nodes are 0.30 /
  0.34 kg against the F4's 0.16, so 2.5x the springs was 1.33x the F4's
  stiffness per kg, and the generated-tyre approximation in setup_report
  cannot see it (it rated both the same). New gate, `check_tyres()`: every
  tyre spring per kg of tyre node <= the F4's (now 0.53x at most).
- **Round 10 (gearing, sound, steering):**
  - *Punchier low gears:* 4.15 / 3.15 / 2.54 / 2.12 / 1.79 / 1.535 / 1.32 /
    1.14 -- 1st to 5th top out at 95 / 125 / 155 / 186 / 220 km/h (were
    105 / 136 / 166 / 197 / 229); 8th unchanged (346). More wheel torque in
    2nd-5th and smaller rpm drops per shift; downshift points follow the
    ratios; the short set stays 9 % shorter.
  - *Engine sound:* same samples, re-voiced toward a 2018 V6 hybrid: less
    bass boom, more intake and exhaust, treble and upper mids up, the
    firing-order fundamental forward, more overrun.
  - *Steering:* at full lock the rack (slidenodes on the fx3r-fx3l rail)
    travelled 46.2 mm, past the 45.7 mm to the capped end of its rail;
    factor 0.090 / lock 170 deg keeps it 2 mm short with the same ratio
    (steering() checks it). No steering or front-corner beam comes near
    yielding in hard cornering (tie rods 8 %, worst front beam 25 %), and
    the steering-damper beams are light (25 N s/m), so neither a bent part
    nor damping explains an offset that stays. New readout, key **J**
    (`lua/controller/redbullSteerCheck.lua`): steering input and each front
    wheel's measured steer angle, to tell a steering offset from a pull.
- **Round 11 (in-game: steering and front wheels read straight but the car
  pulls, changing after each corner; front wheels judder in hard corners,
  shaking the front wing; match speed to the real car):**
  - *Front judder (undone in 11b: broke the front suspension at spawn):* tyre carcass 1.6x the F4's with deform / break forces
    to match -- 0.85x the F4's stiffness per kg of tyre node, inside the
    round-9c gate (round 9's 2.5x was 1.33x and shook the tyres apart).
    Wheel-carrier damping 600 -> 900 (1200 goes over the damped limit at
    the front axles). Stiffer rims (0.8x the F4's) put the axles at 1.73
    undamped, so they stay at 0.65x.
  - *Tyre-wing contact ruled out:* a dynamic clearance check (full lock +
    40 mm bump; 250-300 km/h with the wing drooping under its load and the
    car on its packers) finds no wing node within 100 mm of a front tyre.
    Static front-wing loads stay under 25 % of any beam's deform force
    (300 km/h + a 3 g kerb), so a wing only takes a set if the judder
    shakes it well past that.
  - *Pull:* the J readout adds rear wheel angles, chassis roll against the
    wheel plane, each front-wing tip's height change since spawn and the
    rear left-right wheel-speed difference: after a corner, whichever
    changes is the cause (rear toe / a roll that doesn't settle / a bent
    wing / a tyre radius difference).
  - *Speed:* fact check -- the RB14 was fastest through the 2018 Baku speed
    trap at 341.8 km/h (212 mph), low-downforce trim with DRS and a tow.
    Offline the Low Downforce car reaches 340 km/h (348 with DRS), Baseline
    323 (346); 0-100 / 0-200 2.4 / 4.5 s against ~2.6 / ~4.8 s for 2018
    cars. New always-on timer (`lua/controller/redbullPerf.lua`) posts
    0-100 / 0-200 / 0-300 and top speed in game, to calibrate against.
- **Round 11b (in-game: front suspension broke, wheels fell off at spawn):**
  round 11's physics changes undone -- the jbeam is round 10's again (tyre
  carcass 1.0x, carrier damping 600); the J readout and the timer stay.
  The model puts the front wheel-corner mode (axle + upright nodes) at
  1.78 damped with 600 and 1.83 with 900; round 10 was fine, round 11 was
  not. New gate: wheel-corner damped modes <= 1.78. The generated tyres
  stay a blind spot, so the 1.6x carcass is undone too rather than tested
  separately at spawn.
- **Round 12 (front-fix variants; setup sweeps removed):** the 54 sweep
  cars and `sweeps.py` are gone. Three new tuning variables (defaults = the
  round-10 car): `$tyre_carcass_F` (front tyre springs and their deform /
  break forces), `$carrier_damp_F` (front wheel-carrier damping) and
  `$upright_mass_F` (kg per front corner moved from the rim's hub nodes to
  the upright nodes fh3 / fh5). `tools/rb14/variants.py` writes five test
  cars, `fix_1` ... `fix_5`, safest first -- test sheet
  `plans/front-fixes.md`. Offline: stiffer tyres (1.3x, 1.6x) pass every
  check; any carrier damping above 600 goes over the wheel-corner limit
  (800: 1.81); moving mass off the rim makes the rim's own mode the limit
  (+2 kg: 1.67, +4 kg: 1.75), so those two variants are flagged as risky.
- **Build naming (round 12b):** builds are now always `dist/redbull.zip`,
  so a new install replaces the old one (timestamped zips piled up in the
  mods folder and all loaded -- the likely reason the removed sweep cars
  still showed in the game). `--test`: Baseline + the Front Fix cars only.
  The removed sweeps are recorded in `plans/sweeps-archive.md`.
- **Round 13 (test results: Front Fix 4 best, 3 blew up; steering still
  doesn't quite re-centre after hard turning):** Front Fix 4 is the new
  Baseline (tyre carcass 1.3x, 2 kg per front corner from the rim to the
  upright, as jbeam defaults). Gates recalibrated from the results:
  undamped target 1.67, wheel-corner damping limit 1.82. Firmer front
  dampers (Fix 3) blew up and no version of the model shows why (a 500 Hz
  filter attenuation model scored Fix 3 the same as Fix 5, which spawned),
  so they stay out of test cars. New variable `$steer_damper_F` (the
  steering-damper beams at the uprights). Five *Steering Fix* cars, all
  inside every check: more caster; slight toe-in (+0.12 deg, was -0.09);
  light steering damper (0.3x); stiffer front tyres (1.45x); caster +
  toe-in + 30 % more force feedback. Results in `plans/front-fixes.md`,
  new sheet `plans/steering-fixes.md`.
- **Round 13 replay (`f1 stearing.rpl`, Baseline = Front Fix 4, gridmap,
  34 s; `tools/rb14/replay_analysis.py`):** the steering-fix cars all had
  more wobble than Baseline. From the replay:
  - *Steering:* after each hard left turn the input and the front wheels
    are back at centre (front net +0.1 deg), but the car yaws right at
    6-8 deg/s for ~4 s; before any hard turn it tracks straight (-0.2
    deg/s). During that time the rear axle is not straight: net rear steer
    up to +2.35 deg after turn 1 (decays in 2.8 s), and the rear drive
    torque is lopsided (RR up to ~1.8x RL; even before the turns).
  - *Rear toe:* 3.7 deg toe-in per side at rest, 2.3-5.9 under power
    (offline model: 0.4) -- the rear axle steers with load and drive
    torque. Tyre temperatures are constant (thermals inactive) and the
    pressures equal left / right, so the tyres are not the cause.
  - *Performance:* full throttle, rear-wheel drive power 570-590 kW above
    160 km/h (engine ~600-620 kW); acceleration 0.84-0.90 g at 80-160 km/h
    (torque map trimming, traction-limited), 0.74 g at 160-200, 0.42 g at
    200-240. That leaves ~3-3.6 kN of resistance beyond the modelled drag at
    every speed (speed-independent: rolling / scrub, not aero) -- which
    caps the top speed near ~270 km/h instead of the modelled 323. Rear
    toe-in scrub is a likely part of it. Peaks: 3.3 g lateral, 3.4 g
    braking (brake pedal only ~50 %).
- **Round 14 (rear-axle variants):** Baseline unchanged (Front Fix 4). From
  the round-13 replay: rear toe 3.7 deg per side at rest (model 0.4), up to
  5.9 under power, rear axle steering the car after hard turns, ~3 kN of
  extra scrub / rolling resistance. The rear toe slider (`$toe_R`, which
  shortens the upper link rx3-rh4 and so moves camber too) now spans
  0.95-1.06; toe / camber settings are solved together to keep camber at
  -1.8 deg. New alternative part `redbull_wheeldata_R_gbx` (made by
  `alt_parts()`): rear drive-torque reaction on the wheel's own side
  (gearbox rx1 + engine e3) instead of the engine node across the car.
  Eight *Rear Fix* cars: toe fixed (~0.3 deg in game), toe half-fixed,
  gearbox reaction, freer diff, and their combinations; all inside every
  offline check (the drive-reaction change itself can't be checked
  offline). Test sheet `plans/rear-fixes.md`.
- **Round 15 (Rear Fix 4, freer diff, was best; replays A / B / C with it):**
  - *Analysis fixes:* the per-frame yaw rate read ~20x too high (frames
    sharing a timestamp); now the recorded yaw angle over 0.3 s. The first
    replay's post-turn yaw (6-8 deg/s) still stands. Top speed is the
    0.5 s mean (single frames spike).
  - *Straight line:* top speed 293 km/h (DRS open, 7th, 11,850 rpm, no
    longer accelerating); rear-wheel power ~590 kW; 0-100 3.1 s, 0-200
    6.6 s; acceleration 0.82-1.0 g to 160 km/h (torque map trimming 80-100 %,
    traction-limited), 0.86 g at 160-200, 0.54 at 200-240. Coast-down: air
    drag about as modelled (fit CdA ~1.1, some of it with DRS open) plus ~3 kN
    constant, mostly engine braking in gear. Braking 3.6-3.9 g at 200-300
    km/h = the brake torque limit (~30 kN); below 150 km/h full pedal locks
    the wheels (wheel speed 26-48 % of road speed). Steady 150 km/h hands
    off: 0.15-0.45 deg/s drift, wheels straight.
  - *Cornering:* 2.3 g at 80-120 km/h, 2.9 / 3.3 / 3.8 g (p95; peaks to
    4.5) at 160-200 / 200-240 / 240-300. Roll 0.1-0.2 deg per g.
  - *Deformation:* rear toe-in 2.6-5 deg per side on straights, more on
    throttle (B: 3.9 -> 5.1); front-wing tips down 21 mm at 200-240 km/h,
    31-34 mm at 240-300; front-wheel wobble 0.6-0.7 deg rms in fast
    corners (0.04-0.16 on straights), larger under heavy braking.
  - *Steering:* after hard turns the car still yaws 3-4 deg/s for 1-5 s
    (was 6-8) with the rear axle steered up to 1.5 deg -- better, not gone.
  - *DRS:* the replays carry no node positions, so the wing can't be seen.
    By design (drs_hydros) DRS lifts the whole upper wing's leading edge
    60 mm about its trailing edge; the RB14 wing mesh (main plane, flap and
    probably the centre pillar) follows those nodes -- the "whole wing lifts
    and the pillar comes off" seen in game. Needs a split mesh: fixed main
    plane + pillar, a moving flap.
- **Round 16 (Rear Fix 4 is Baseline; 14 test cars):** Baseline diff power
  lock 0.10, preload 20 Nm, coast lock 0.06. New tuning variables (defaults
  = Baseline): `$rear_toe_stiff` (rear hub toe torsion bar; 5x is the most
  the gates allow, the cars use 4x), `$drs_model` (1: the wing stays put and
  DRS acts as gearbox thrusters, -1.28 kN drag / -3.14 kN downforce at 300
  km/h x (v/300)^2, `electrics.values.drsThrust`), `$pu_power` (ICE torque
  scale; the torque table is ICE x scale + MGU-K, the ERS controller scales
  its ICE share to match), `$brake_map` (lua/controller/redbullBrakeMap.lua:
  brake x 0.5 + 0.5 (v/250 km/h)^2, capped at 1), `$tc_slip` (torque-map
  slip target); the brake force slider now goes to 1.5. Cars: one per fix
  (stiff rear hubs 4x; rear toe reset; DRS flap fix; traction 18 %; power
  +12 %; brakes 1.3x; brake modulation), the fixes combined worst-first
  (Test 08-13, Test 13 = all) and the performance changes alone (Test 14).
  All inside every offline check. Not addressed: front-wing droop and
  front-wheel wobble in fast corners (no solver headroom without more nose
  mass); a proper DRS (split wing mesh with a moving flap). Test sheet
  `plans/round16-tests.md`.
- **Round 17 (Test 05 is Baseline; drift sensors and seven drift-fix cars):**
  the one issue left: after a hard turn, wheel centred, the car keeps
  turning the other way for ~2.5-4.5 s. Replays B / C: the *inner* rear
  wheel loses ~3 deg of toe-in in the turn (the outer one barely moves),
  holds it ~1.5-2 s after centring, then snaps back -- the counter-yaw stops
  with it. Not the whole rear end (the toe between the wheels changes), not
  drive torque (equal left / right), and the offline model can't reproduce
  it (rear toe moves ~0.1-0.3 deg at 3.5 g; every beam under 20 % of its
  deform force). So: virtual sensors, `lua/controller/redbullSensors.lua`,
  always on, recorded in replays as `sn_*` electrics -- per rear wheel the
  toe / camber against the gearbox, both axle nodes in the gearbox frame,
  the driveshaft length, spring length, axle-to-upright distances and the
  six link lengths; the gearbox-vs-tub yaw; front toe, rack and tie rods;
  wheel loads where the game gives them. `replay_analysis.py` lists, per
  hard turn, the inner wheel's sensors still off while the car drifts.
  New variables `$rear_link_stiff` (1.5x fails the gates), `$rear_droop`,
  `$halfshaft_play`; Baseline `$pu_power` 1.12. Drift Fix 1-6: stiff rear
  hubs 5x, rear links 1.2x, driveshaft play 3x, droop room 2x, gearbox
  torque reaction, rear toe reset; 7 = all (hubs 4x). Sheet
  `plans/drift-fixes.md`.
- **Round 18 (hub-fix cars):** replayTurns (Baseline, sensors) traced the
  drift to the rear hub: rear toe follows the axle height at ~0.17 deg/mm
  (offline model 0.007), the axle nodes shift 2-4 mm on the upright as the
  wheel compresses (toe vs hub_in_rh4 r = 0.97), and after a turn the inner
  wheel's toe lags its height ~1-1.5 s, 0.6-0.8 deg of net rear steer. Not
  drive torque, driveshaft stops, droop stop, upright links, rear-structure
  yaw or a left / right height difference. New tuning variables (Baseline
  off): `$rear_hub_beam` (the 8 axle-to-upright beams), `$rear_brace` (new
  1.5 kg nodes rh6 / rh7 ahead of / behind the axle on each upright, rigid to
  rh1 / rh3 / rh4 at 3 MN/m, braced to both axle nodes at x 6 MN/m; the
  nodes are in Baseline too, +3 kg per rear corner from the ballast),
  `$rear_toe_brace` (torsion bar: outer axle node about the upright's
  rh1 -> rh3 edge, x 100 kNm/rad; about the 77 mm rw1 -> rh1 axis it went
  over the solver limit at 100 kNm/rad), and `$rear_corner_mass` (kg per rear
  corner moved from the engine ballast to the axle / upright / brace nodes,
  which the stiffer steps need: the axle and upright nodes are the limiting
  modes; moving it from the rim's hub nodes made those the limit instead).
  Hub Fix 1-4 axle beams 1.25 / 1.5 / 2 / 2.5x, 5-8 bracing 0.5 / 1 / 1.5 / 2,
  9-11 toe brace 200 / 400 / 600k, 12 corner mass only (control), 13-15
  combined medium / strong / max, 16 strong + more toe-in, 17 / 18 static
  rear toe +-0.6 deg. 4, 8, 11 and 15 are just over the stiffness target
  (1.68-1.72). Sheet `plans/hub-fixes.md`.
- **Round 19 (Hub Fix 15 is Baseline):** `$rear_hub_beam` 2, `$rear_brace`
  1.5, `$rear_toe_brace` 6, `$rear_corner_mass` 12 by default. The ballast is
  solved without the corner mass (which then comes out of the engine
  ballast), exactly as the test car had it: 733 kg dry, 45.9 % front (the
  mass moved rearward from the engine to the rear corners). Its stiffness
  1.72 was over the old 1.67 target; it was the best car in the game, so the
  target is now 1.72. Hub Fix test cars retired.
- **Reference check (after round 18):** `check_mod.py` only checked beam-
  style node columns in the default car. It now checks every reference, in
  all 29 cars (default, 22 configurations, 6 optional parts), and runs the
  Lua controllers on each car's nodes. Found (all inherited from the F4,
  which shows the same): front spindles fed from devices no part defines
  (now root devices, input "dummy"; the replays show the game built them
  anyway), the springs reading an undefined `$rideheight_F / _R` (now 1;
  precompressionRange overrides it), and the fuel cell naming a beam
  "fuelTank" that didn't exist (now ft1-rt4l; the tank's beams are
  unbreakable as in the F4, so no behaviour change). Accepted as dead F4
  leftovers: beams to the missing nc7 / fw2 / rh5 nodes, the empty flywheel
  slot, the mainEngine_piping deform group. The sensors controller now logs
  which node is missing instead of silently dropping a wheel.
- **Rear tyre clearance:** the rear floor / diffuser edge nodes sat 20-50 mm
  inside the 405 mm rear tyres' inner face; moved ~8 cm inboard (aero
  factors re-solved for the smaller floor).
- **Front wing endplates:** their rear jbeam nodes (collision surfaces)
  sat 15 cm behind the visible RB14 endplate, inside the 305 mm front tyres'
  steering sweep, so turning the wheels bent the wing. Moved to the visible
  endplate's rear edge; the tyre now clears them by 51 mm at full lock.
- **Suspension** (baseline, per wheel): heave 166 / 168 N/mm (5.6 / 5.0 Hz),
  roll 310 / 227 N/mm (57 % front roll stiffness). Corner springs carry the
  load; on top of them a **heave (third) spring** per axle -- a torsionbar
  about a lengthwise axis with the two hubs as its arms, so it resists both
  wheels rising together (aero load) but not roll -- and an anti-roll bar
  per axle (the F4's rear bar was wired to the front bar's variable; now its
  own). Heave and ARB variables read as added wheel rate in N/m. Packers
  (progressive bump stops) after 25 / 32 mm of wheel travel; the car rides
  them near 300 km/h. Spring preload is solved so the car sits exactly at
  its modelled ride height and rake with 60 L of fuel (72 mm front / 122 mm
  rear of the plank); "Spring Height" moves it by that many metres.
- **Alignment:** camber -3.1 / -1.8 deg, toe -0.12 (out) / +0.25 (in) deg,
  with new toe variables (the F4's fixed tie-rod setting gave 1.3 deg toe-in
  on the RB14 geometry).
- **Tyres:** 305 / 405 wide, 0.335 m radius, 21 / 19.5 psi, grip with strong
  load sensitivity (mu ~1.9 at low load falling to ~1.2-1.3 at 300 km/h
  loads). Wets kept.
- **Power unit:** 1.6 L V6 hybrid: ICE 559 kW (749 hp) at 11,000 rpm, rev
  limit 12,500, idle 4,000, light inertia, dry sump safe to 6.5 g (the F4's
  2.5 g limit would have starved it in fast corners). The jbeam torque curve
  is ICE + MGU-K; the **ERS** controller (`lua/controller/redbullERS.lua`)
  caps the throttle to the ICE share unless the 4 MJ store is deploying
  (+120 kW, 910 hp total), harvests under braking (MGU-K) and at high load
  (MGU-H). Modes: harvest / balanced (keeps a 25 % reserve) / overtake;
  key **O** cycles.
- **Gearbox and diff:** 8-speed seamless sequential (105 ... 346 km/h at the
  limiter on the 4.0 final drive), 30 ms shifts, short gear set for highdf;
  limited-slip diff with preload / power / coast locking and final drive
  as tuning variables.
- **Brakes:** carbon (278 / 266 mm), 5,000 Nm per wheel before the bias
  split (~10 kNm total), bias 57 % front (50-64 %, T / G keys). The bias
  controller takes its torques from the jbeam now instead of the F4's
  hard-coded values.
- **Aero:** wings and floor rescaled from the F4 for the numbers above;
  front wing ~30 %, rear wing ~30 %, floor ~40 % of downforce.
- **DRS** (key **U**): a hydro per side lifts the rear wing's leading edge
  so the upper wing turns flat about its trailing edge (-14 % downforce,
  -22 % drag at baseline); opens above 72 km/h, closes when you brake.
- **Ride-height floor (experimental, off by default):** Parts > Floor
  Aerodynamics > "Ride-Height Sensitive Floor". A controller measures the
  floor's height above the wheel plane and adds or removes downforce with
  thrusters: +1.2 % per mm lower, stalling below ~18 mm at the front.

**In-game checklist** (jbeam debug + the G-meter/telemetry apps):
1. The car settles at its modelled height (plank ~7 cm front, ~12 cm rear);
   nothing twitches at rest; DRS flap and ERS modes respond (on-screen
   messages).
2. Straight line: 0-100 ~2.7 s, 0-200 ~5 s, top speed per the table; no
   bottoming or porpoising at top speed.
3. Corners: < 2 g slow, 4-5 g fast; balance near neutral with mild
   understeer on baseline.
4. Braking from 300 km/h: ~5 g, no front lock at 57 % bias.
5. Then try the experimental floor on baseline and report how it feels.

## Testing loop

Every milestone ends the same way: `check_mod.py` passes → preview renders
committed → `build_mod.py` → you install the zip (removing the previous
build), test in BeamNG with the jbeam debug view, and report back with notes
or screenshots. Fixes go into the scripts/data, never hand-edits to generated
`.dae`/`.dds` files.

## Risks and open questions

- **Licence of the F4 jbeam.** The original files carry the note "Made by
  LucasBE - Do not reuse or modify without permission. Feel free to take
  inspiration from my Jbeam files." This mod modifies them, so it needs the
  author's permission before being shared or published; fine for private use.
- **Licence of `rb14.glb`.** Texture names (`toro_rosso_steering_wheel`,
  `generic_main_d`) suggest it was extracted from a game. Fine for personal
  use; check before publishing to the BeamNG repository.
- **Split quality.** If body panels are not separate loose pieces in the
  source, splitting needs cutting by region, which is slower and may need
  manual fixes in Blender GUI on your side.
- **Mechanical detail.** The RB14 model may have no engine, pedals or
  suspension internals; we keep F4 parts where hidden, otherwise go without.
- **Physics re-fit.** Stretching a F4 frame to F1 size (+1 m length, +0.5 m
  width) may leave suspension geometry odd; Milestone 4 may need parts of the
  suspension jbeam rebuilt rather than scaled (the rear becomes pullrod
  anyway).
- **Ground-effect floor.** Ride-height-sensitive downforce needs a custom Lua
  controller; getting it stable (no oscillation/porpoising from the
  aero-suspension feedback loop) may take several iterations.
- **Tuning needs the game.** Every handling change is verified by you driving
  and reading telemetry; there is no way to test driving dynamics in the
  sandbox.
- **Collada.** Blender 4.x (sandbox) and 3.4 (dev image) both export `.dae`;
  Blender 5 dropped it, so don't upgrade past 4.x for this pipeline.
- **Repo size.** Generated `.dds`/`.dae` add hundreds of MB over iterations;
  consider moving binaries to Git LFS before Milestone 1 lands.
