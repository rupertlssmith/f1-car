-- RB14 drag reduction system for the redbull mod.
--
-- Action "drsToggle" requests DRS; it opens above minSpeed and closes as soon
-- as the brake is touched (like the real system, it then has to be requested
-- again). electrics.values.drs (0/1) drives the rear wing hydros
-- (redbull_wing_R.jbeam), which rotate the upper wing flat about its trailing
-- edge and so cut its downforce and drag.

local M = {}
M.type = "auxiliary"

local minSpeed = 20      -- m/s
local lastState = 0

local function updateGFX(dt)
  local request = electrics.values.drsRequest or 0
  local brake = electrics.values.brake or 0
  local speed = electrics.values.wheelspeed or 0

  if request > 0 and brake > 0.05 then
    request = 0
    electrics.values.drsRequest = 0
  end
  local state = (request > 0 and speed > minSpeed) and 1 or 0
  electrics.values.drs = state

  if state ~= lastState then
    lastState = state
    guihooks.message({txt = state == 1 and "DRS open" or "DRS closed", context = {}}, 1.5, "redbullDRS", "flag")
  end
end

local function reset()
  electrics.values.drsRequest = 0
  electrics.values.drs = 0
  lastState = 0
end

local function init(jbeamData)
  minSpeed = jbeamData.minSpeed or minSpeed
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
