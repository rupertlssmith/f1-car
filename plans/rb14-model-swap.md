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

All scripted and repeatable from the source `.glb`, so the model can be
re-processed after any fix instead of hand-edited:

| Script | Does |
|---|---|
| `tools/rb14/inspect.py` | Report meshes, loose parts, bounds and materials of the `.glb` |
| `tools/rb14/parts.json` | Declarative split map: which loose pieces of which source mesh become which BeamNG part (by material + position/bounding box rules) |
| `tools/rb14/prepare_model.py` | Blender (headless): import `.glb`, fix axes, split per `parts.json`, name parts, set origins, export `.dae` |
| `tools/rb14/textures.py` | Convert PNG → DDS with BeamNG naming (`_b.color`, `_n.normal`, …), write `main.materials.json` entries |
| `tools/rb14/fit_jbeam.py` | Measure key points on the RB14 mesh and remap jbeam node coordinates to them |
| `tools/rb14/render.py` | Blender preview renders (views of the car, optionally with jbeam nodes drawn as dots and beams as lines) for review |
| `tools/check_mod.py` | Consistency checks: every file reference resolves, every flexbody/prop mesh exists in a `.dae`, every material used by a mesh is defined, flexbody vertices lie near their node groups |

Previews go to `plans/previews/` (committed, small PNGs) so progress can be
reviewed without the game.

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

## Testing loop

Every milestone ends the same way: `check_mod.py` passes → preview renders
committed → `build_mod.py` → you install the zip (removing the previous
build), test in BeamNG with the jbeam debug view, and report back with notes
or screenshots. Fixes go into the scripts/data, never hand-edits to generated
`.dae`/`.dds` files.

## Risks and open questions

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
