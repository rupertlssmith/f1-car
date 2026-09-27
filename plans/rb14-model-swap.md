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
| `tools/check_mod.py` | Consistency checks: references, meshes, groups, materials, textures, configs, controllers, actions and key bindings; `--fit` measures how far each flexbody's vertices are from its nodes |
| `tools/rb14/f1_setup.py` | Milestone 4: turns the re-fitted F4 physics into the 2018 F1 setup (mass, tyres, suspension, alignment, power unit, gearbox, diff, brakes, aero, ERS/DRS, ride-height floor, the four configs). Sets absolute values, calibrating against `setup_report.py`, so it is safe to re-run |
| `tools/rb14/setup_report.py` | Offline setup sheet read from the jbeam the way the game merges it: mass and balance, a linear spring-network model of each axle (wheel/heave/roll rates, ride frequency, static sag), flat-plate aero by part (and with DRS open), torque/power, gearing, a straight-line launch sim, tyre-limited lateral and braking g. `--config <name>` for a `.pc` |
| `tools/rb14/jbeam_edit.py` | Format-preserving (CRLF, comments) jbeam text edits used by `f1_setup.py` |
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
  doesn't exist and a torque arm 2 cm from the axle line; its rear brake arm
  was 7 cm from the axle. Now: coupling at the differential, arms on the
  gearbox 40-48 cm away (drive ~10-12 kN instead of hundreds), rear brake
  arm on the upper upright (13 cm, 16.5 kN). Suspension and diff-mount beam
  deform/break thresholds are 3x the F4's (loads are 3.4-4.7x).
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
