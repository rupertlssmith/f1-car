# Shimmy-fix test cars (round 21)

Baseline is round 20's Wobble Fix 2 (front toe brace 1.5). Its Silverstone lap still shimmies
(~8 Hz, 2 deg RMS above 3.5 g). Replay + FEM: each front tyre's load bounces at 7-8 Hz in hard
corners (rear too, but the rear toe stays put); cornering force bends the front wishbone legs,
the upright moves back and the track rod turns it toe-out -- 0.107 deg per kN of cornering
force, 0.239 per kN rearward (FEM) and ~4x that in the game near the corner's resonance. Every
wheel steers away from the corner as its load rises, inner and outer alike. A stiffer track rod
does not help (its stretch is ~1/4 of the toe motion; rigid makes the toe-out per kN worse).
In the game: *Shimmy Fix N · ...*.

Test drive per car: a few fast corners (Silverstone's Copse / Maggotts / Stowe are ideal), then
`python3 tools/rb14/handling_analysis.py <replay>`: shimmy RMS by lateral g, yaw / geometric,
front / rear slip angles. Cars 2, 7-9 and 11-13 steer slower (longer steering arm).

| # | Car | Change |
|---|---|---|
| 1 | Stiffer wishbones | front wishbone legs 2x stiffer, 2 kg per corner from the rim to the upper ball joint to carry it: toe-out per kN of cornering force 0.107 -> 0.037 deg |
| 2 | Longer steering arm | track rods' outer ends 20 mm forward (arm 78 -> 96 mm): toe stiffness 320 -> 454 Nm/deg, toe-out per kN rearward 0.24 -> 0.16 deg; ~18 % less steering lock, slower steering |
| 3 | Front roll damper | damping on the front anti-roll bar, 8000 Ns/m at the wheels in roll (the 7-8 Hz corner bounce) |
| 4 | Later front packers | front packers engage after 35 mm of wheel travel (was 25) |
| 5 | Aero balance to weight | front wing 0 deg, rear wing 6 deg (was -3 / 8): aero balance 46 % front like the weight, drag -5 % |
| 6 | Roll balance rearward | front anti-roll bar 150 kN/m (was 260), rear 200 kN/m (was 110) |
| 7 | Wishbones + arm | 1 + 2: 0.055 deg per kN cornering, 0.136 per kN rearward, 540 Nm/deg |
| 8 | Wishbones 2.5x + arm | wishbones 2.5x + 2: 0.043 / 0.131 deg per kN, 561 Nm/deg |
| 9 | Wishbones 3x + arm | wishbones 3x, 2.5 kg to the ball joints + 2: 0.035 / 0.128 deg per kN, 576 Nm/deg; just over the damping target |
| 10 | Roll damper + packers | 3 + 4 (the corner bounce) |
| 11 | Wishbones + arm + bounce | 7 + roll damper + later packers |
| 12 | Wishbones + arm + balance | 7 + aero balance to weight + roll balance rearward |
| 13 | All | wishbones 2.5x + arm + roll damper + later packers + aero balance + roll balance |

Offline checks: stiffness = highest omega*dt (target <= 1.83), damped = with
damping (<= 1.88), corner = wheel-corner modes with damping (<= 1.88; round 10
was 1.78 and fine, round 11 1.83 and broke), tyres = stiffness per kg vs the F4's (<= 1).

| Car | Tries | stiffness | damped | corner | tyres | spawns? | judder? |
|---|---|---|---|---|---|---|---|
| `shim_01` Stiffer wishbones | front wishbone legs 2x stiffer, 2 kg per corner from the rim to the upper ball joint to carry it: toe-out per kN of cornering force 0.107 -> 0.037 deg | 1.81 | 1.85 | 1.85 | 0.69 | | |
| `shim_02` Longer steering arm | track rods' outer ends 20 mm forward (arm 78 -> 96 mm): toe stiffness 320 -> 454 Nm/deg, toe-out per kN rearward 0.24 -> 0.16 deg; ~18 % less steering lock, slower steering | 1.72 | 1.82 | 1.82 | 0.69 | | |
| `shim_03` Front roll damper | damping on the front anti-roll bar, 8000 Ns/m at the wheels in roll (the 7-8 Hz corner bounce) | 1.83 | 1.87 | 1.87 | 0.69 | | |
| `shim_04` Later front packers | front packers engage after 35 mm of wheel travel (was 25) | 1.83 | 1.87 | 1.87 | 0.69 | | |
| `shim_05` Aero balance to weight | front wing 0 deg, rear wing 6 deg (was -3 / 8): aero balance 46 % front like the weight, drag -5 % | 1.83 | 1.87 | 1.87 | 0.69 | | |
| `shim_06` Roll balance rearward | front anti-roll bar 150 kN/m (was 260), rear 200 kN/m (was 110) | 1.83 | 1.87 | 1.87 | 0.69 | | |
| `shim_07` Wishbones + arm | 1 + 2: 0.055 deg per kN cornering, 0.136 per kN rearward, 540 Nm/deg | 1.76 | 1.83 | 1.83 | 0.69 | | |
| `shim_08` Wishbones 2.5x + arm | wishbones 2.5x + 2: 0.043 / 0.131 deg per kN, 561 Nm/deg | 1.77 | 1.84 | 1.84 | 0.69 | | |
| `shim_09` Wishbones 3x + arm | wishbones 3x, 2.5 kg to the ball joints + 2: 0.035 / 0.128 deg per kN, 576 Nm/deg; just over the damping target | 1.81 | 1.89 | 1.89 | 0.69 | | |
| `shim_10` Roll damper + packers | 3 + 4 (the corner bounce) | 1.83 | 1.87 | 1.87 | 0.69 | | |
| `shim_11` Wishbones + arm + bounce | 7 + roll damper + later packers | 1.76 | 1.83 | 1.83 | 0.69 | | |
| `shim_12` Wishbones + arm + balance | 7 + aero balance to weight + roll balance rearward | 1.76 | 1.83 | 1.83 | 0.69 | | |
| `shim_13` All | wishbones 2.5x + arm + roll damper + later packers + aero balance + roll balance | 1.77 | 1.84 | 1.84 | 0.69 | | |
