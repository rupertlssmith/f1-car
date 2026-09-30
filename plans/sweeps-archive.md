# Setup sweeps (archived)

Parameter sweeps built in rounds 6-11 and removed from the build in round 12
(the user never got to test them; the front-wheel and steering issues came
first). Each sweep was a set of test cars that changed **one** tuning setting
from Baseline in five steps (step 3 = the Baseline value), so the best-feeling
step could be picked by driving them back to back on one track -- and, if the
best was 1/5 or 5/5, the sweep widened past it.

Steps are relative to Baseline, so they follow any later Baseline change. The
values below are what Baseline gave at the time (round 11).

**To bring them back:** `git show 12b2d4c:tools/rb14/sweeps.py > tools/rb14/sweeps.py`,
run it after `tools/rb14/f1_setup.py`, and rebuild. It writes
`vehicles/redbull/sweep_<key>_<n>.pc` (+ info / thumbnail, *Sweep NN · ...* in the
game's list) and a test sheet; the full sheet with offline estimates is
`git show 12b2d4c:plans/sweeps.md`. Its checks predate the round-11 wheel-corner
and tyre gates in `f1_setup.check_stability()`; add those before relying on it.

| # | Sweep | Tuning menu | Steps (1 ... 5) | Tested? |
|---|---|---|---|---|
| 01 | Front Wing | Aerodynamics > Front Wing Angle | -5° / -4° / -3° *(baseline)* / -2° / -1° | not yet |
| 02 | Roll Balance | Suspension > Anti-Roll Bar (front and rear) | more front / front+ / baseline *(baseline)* / rear+ / more rear | not yet |
| 03 | Diff Power Lock | Differentials > Power Lock Rate | 0.00 / 0.10 / 0.20 *(baseline)* / 0.30 / 0.40 | not yet |
| 04 | Diff Coast Lock | Differentials > Coast Lock Rate | 0.00 / 0.06 / 0.12 *(baseline)* / 0.18 / 0.24 | not yet |
| 05 | Heave Springs | Suspension > Heave Spring (front and rear) | x0.0 / x0.5 / x1.0 *(baseline)* / x1.5 / x2.0 | not yet |
| 06 | Ride Height | Suspension > Spring Height (front and rear) | -6 mm / -3 mm / +0 mm *(baseline)* / +3 mm / +6 mm | not yet |
| 07 | Rake | Suspension > Spring Height (rear only) | rear -8 mm / rear -4 mm / rear +0 mm *(baseline)* / rear +4 mm / rear +8 mm | not yet |
| 08 | Tyre Pressures | Wheels > Tire Pressure (front and rear) | 17/15.5 psi / 19/17.5 psi / 21/19.5 psi *(baseline)* / 23/21.5 psi / 25/23.5 psi | not yet |
| 09 | Brake Bias | Brakes > Brake Bias | 54% front / 56% front / 58% front *(baseline)* / 60% front / 62% front | not yet |
| 10 | Wing x Roll | Front Wing Angle and Anti-Roll Bars | 3 x 3 grid: front wing -5° / -3° / -1° each with roll front+ / baseline / rear+ (9 cars; centre = baseline) | not yet |

Sweep 10 crosses the two balance levers that interact most. "front+" / "rear+"
move 40,000 / 20,000 N/m of anti-roll bar between the axles (sweep 02's steps
2 and 4).

Why these ten (round 6): front wing and roll balance set the car's balance;
the diff's power / coast locking set traction and turn-in; heave springs, ride
height and rake trade aero platform against bumps and kerbs; tyre pressures
and brake bias are the quickest things a driver tunes. Other candidates
discussed then and not built: dampers, packers, final drive, camber / toe,
DRS size, ERS modes.
