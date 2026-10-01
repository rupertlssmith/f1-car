-- Low-speed brake modulation for the redbull mod (tuning variable
-- $brake_map, off by default).
--
-- An F1 car's brake force is sized for 300 km/h, where downforce gives the
-- tyres 2-3x the grip they have at low speed; a driver bleeds the pedal off
-- as the car slows. With a full pedal the RB14 locked its wheels below
-- ~150 km/h (round-15 replays). This scales the brake by
--   lowFactor + (1 - lowFactor) * min(1, (speed / fullSpeed)^2)
-- -- the grip that downforce adds -- so full pedal is full brake at
-- fullSpeed (km/h) and lowFactor of it at a standstill.
-- Electrics out: brakeMap (the factor applied).

local M = {}
M.type = "auxiliary"
M.defaultOrder = 1200     -- after vehicleController has written the brake

local enabled = false
local lowFactor = 0.5
local fullSpeed = 250 / 3.6

local function updateGFX(dt)
  if not enabled then
    electrics.values.brakeMap = 1
    return
  end
  local v = electrics.values.airspeed or electrics.values.wheelspeed or 0
  local k = lowFactor + (1 - lowFactor) * math.min(1, (v / fullSpeed) ^ 2)
  electrics.values.brakeMap = k
  if electrics.values.brake then
    electrics.values.brake = electrics.values.brake * k
  end
end

local function reset()
  electrics.values.brakeMap = 1
end

local function init(jbeamData)
  enabled = (tonumber(jbeamData.enabled) or 0) > 0.5
  lowFactor = tonumber(jbeamData.lowFactor) or lowFactor
  fullSpeed = (tonumber(jbeamData.fullSpeed) or 250) / 3.6
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
