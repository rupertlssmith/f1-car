# Wobble-fix test cars (round 20)

Silverstone replay (tools/rb14/handling_analysis.py): each front wheel shimmies at ~7 Hz on its
own track rod and hub, 2-4 deg RMS in fast corners (it grows with lateral g), not from the
driver, the rack or the bounce (5 Hz). Behind it: heavy understeer -- front tyres at 8-12 deg of
slip against 2.5-3.6 at the rear, yaw at 24-46 % of geometric, aero balance 41 % front against
46 % weight -- and a soft front corner: ~200 Nm/deg toe stiffness (FEM, chassis and rack held),
most of it the hub turning on its upright. Baseline is unchanged (Hub Fix 15, with halo).
Every car now records sn_FL_wobble / sn_FR_wobble (deg RMS above ~3 Hz, at frame rate).
In the game: *Wobble Fix N · ...*.

Test drive per car: a few fast corners (Silverstone's Copse / Maggotts / Stowe are ideal), then
`python3 tools/rb14/handling_analysis.py <replay>`: shimmy RMS by lateral g, yaw / geometric,
front / rear slip angles.

| # | Car | Change |
|---|---|---|
| 1 | Front toe brace | torsion bar holding each front axle against toe about its upright's steering axis (100 kNm/rad): front toe stiffness 201 -> 373 Nm/deg |
| 2 | Toe brace strong | toe brace 150 kNm/rad (395 Nm/deg; just over the stiffness target) |
| 3 | Shimmy damper | damping of each front axle's toe about its upright, 150 Nms/rad (about half critical) |
| 4 | Shimmy damper strong | shimmy damper 200 Nms/rad, uprights +2 kg (from the rims) to carry it; just over the stiffness target |
| 5 | Stiffer track rods | front track rods 1.5x stiffer |
| 6 | Damped track rods | front track rods 10x damping (1500 Ns/m) |
| 7 | Front wing +3 deg | front wing 0 deg (was -3): aero balance 41 -> 45 % front, +5 % downforce |
| 8 | Aero balance to weight | front wing 0 deg, rear wing 6 deg (was 8): aero balance 46 % front like the weight, drag -5 % |
| 9 | Roll balance rearward | front anti-roll bar 150 kN/m (was 260), rear 200 kN/m (was 110) |
| 10 | Front grip +6 % | front dry tyres 6 % more grip |
| 11 | Brace + track rods | 1 + track rods 1.5x stiffer, 10x damping (418 Nm/deg) |
| 12 | Damper + track rods | 3 + track rods 1.5x stiffer, 10x damping |
| 13 | Brace + balance | 1 + aero balance to weight + roll balance rearward |
| 14 | Damper + balance | 3 + aero balance to weight + roll balance rearward |
| 15 | All: brace | brace + track rods + aero balance + roll balance + front grip +6 % |
| 16 | All: damper | shimmy damper + track rods + aero balance + roll balance + front grip +6 % |

Offline checks: stiffness = highest omega*dt (target <= 1.72), damped = with
damping (<= 1.85), corner = wheel-corner modes with damping (<= 1.82; round 10
was 1.78 and fine, round 11 1.83 and broke), tyres = stiffness per kg vs the F4's (<= 1).

| Car | Tries | stiffness | damped | corner | tyres | spawns? | judder? |
|---|---|---|---|---|---|---|---|
| `wob_01` Front toe brace | torsion bar holding each front axle against toe about its upright's steering axis (100 kNm/rad): front toe stiffness 201 -> 373 Nm/deg | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_02` Toe brace strong | toe brace 150 kNm/rad (395 Nm/deg; just over the stiffness target) | 1.83 | 1.87 | 1.87 | 0.69 | | |
| `wob_03` Shimmy damper | damping of each front axle's toe about its upright, 150 Nms/rad (about half critical) | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_04` Shimmy damper strong | shimmy damper 200 Nms/rad, uprights +2 kg (from the rims) to carry it; just over the stiffness target | 1.75 | 1.84 | 1.84 | 0.69 | | |
| `wob_05` Stiffer track rods | front track rods 1.5x stiffer | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_06` Damped track rods | front track rods 10x damping (1500 Ns/m) | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_07` Front wing +3 deg | front wing 0 deg (was -3): aero balance 41 -> 45 % front, +5 % downforce | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_08` Aero balance to weight | front wing 0 deg, rear wing 6 deg (was 8): aero balance 46 % front like the weight, drag -5 % | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_09` Roll balance rearward | front anti-roll bar 150 kN/m (was 260), rear 200 kN/m (was 110) | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_10` Front grip +6 % | front dry tyres 6 % more grip | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_11` Brace + track rods | 1 + track rods 1.5x stiffer, 10x damping (418 Nm/deg) | 1.73 | 1.82 | 1.82 | 0.69 | | |
| `wob_12` Damper + track rods | 3 + track rods 1.5x stiffer, 10x damping | 1.72 | 1.83 | 1.83 | 0.69 | | |
| `wob_13` Brace + balance | 1 + aero balance to weight + roll balance rearward | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_14` Damper + balance | 3 + aero balance to weight + roll balance rearward | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `wob_15` All: brace | brace + track rods + aero balance + roll balance + front grip +6 % | 1.73 | 1.82 | 1.82 | 0.69 | | |
| `wob_16` All: damper | shimmy damper + track rods + aero balance + roll balance + front grip +6 % | 1.72 | 1.83 | 1.83 | 0.69 | | |
