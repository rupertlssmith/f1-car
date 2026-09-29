-- Acceleration and top-speed timer for the redbull mod (always on).
--
-- A run starts when the car pulls away from a standstill (below 1 km/h);
-- messages give 0-100 / 0-200 / 0-300 km/h as they are reached, and the
-- top speed (km/h and mph) once you slow 10 km/h below it after passing
-- 250 km/h. Speed is electrics.values.airspeed (road speed, no wheelspin).
-- Electrics out: perfTopSpeed (km/h).

local M = {}
M.type = "auxiliary"

local marks = {100, 200, 300}
local t, running, nextMark, top = 0, false, 1, 0

local function say(txt)
  guihooks.message({txt = txt, context = {}}, 6, "redbullPerf", "timer")
end

local function updateGFX(dt)
  local kmh = (electrics.values.airspeed or 0) * 3.6
  if kmh < 1 then
    t, running, nextMark = 0, true, 1
    return
  end
  if running then
    t = t + dt
    if marks[nextMark] and kmh >= marks[nextMark] then
      say(string.format("0-%d km/h: %.2f s", marks[nextMark], t))
      nextMark = nextMark + 1
      if not marks[nextMark] then running = false end
    end
  end
  if kmh > top then top = kmh end
  if top > 250 and kmh < top - 10 then
    say(string.format("Top speed: %.0f km/h (%.0f mph)", top, top / 1.609344))
    electrics.values.perfTopSpeed = top
    top = 0
  end
end

local function reset()
  t, running, nextMark, top = 0, false, 1, 0
end

local function init(jbeamData)
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
