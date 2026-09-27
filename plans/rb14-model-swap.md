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

1. Mass (~733 kg with driver) and weight distribution.
2. Engine: ~950 hp 1.6 L V6 turbo hybrid torque curve, rev limit ~12,000 rpm.
3. Gearbox: 8-speed sequential, ratios; differential.
4. Aero: downforce and drag at the four wing settings; DRS.
5. Brakes: carbon discs, bias range.
6. Tyres: 2018 13" slicks (front 305/670, rear 405/670), grip.
7. Test laps and iterate on your feedback.

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
  suspension jbeam rebuilt rather than scaled.
- **Collada.** Blender 4.x (sandbox) and 3.4 (dev image) both export `.dae`;
  Blender 5 dropped it, so don't upgrade past 4.x for this pipeline.
- **Repo size.** Generated `.dds`/`.dae` add hundreds of MB over iterations;
  consider moving binaries to Git LFS before Milestone 1 lands.
