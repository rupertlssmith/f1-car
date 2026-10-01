-- RB14 energy recovery system (MGU-K deployment) for the redbull mod.
--
-- The engine's torque curve in the jbeam is ICE + MGU-K. Whenever the energy
-- store is not deploying, this controller caps the throttle to the ICE's share
-- of that curve, so the car has ~750 hp on the engine alone and ~910 hp while
-- the MGU-K deploys (up to deployKW, 120 kW in 2018).
--
-- The store (storeMJ, 4 MJ) is drained by deployment and refilled by the
-- MGU-K under braking and lifting, and by the MGU-H at high load.
--
-- Modes (action "ersMode"): 0 harvest only, 1 balanced (deploys down to 25 %),
-- 2 overtake (deploys everything). Electrics out: ersSOC (0..100), ersDeploy
-- (0/1), ersMode.

local M = {}
M.type = "auxiliary"
M.defaultOrder = 1000     -- after vehicleController has written the throttle

local deployKW = 120
local maxTorque = 180
local storeJ = 4e6
local mguhKW = 40
local harvestKW = 120
local reserve = {0, 0.25, 0}
local modeNames = {[0] = "Harvest", [1] = "Balanced", [2] = "Overtake"}

local rpmTable, tqTable = {}, {}
local iceScale = 1            -- tuning variable $pu_power (the jbeam curve is ICE x scale + MGU-K)
local soc = 0
local lastMode = -1
local emptyWarned = false

local function iceTorque(rpm)
  local n = #rpmTable
  if n == 0 then return 0 end
  if rpm <= rpmTable[1] then return tqTable[1] end
  for i = 2, n do
    if rpm <= rpmTable[i] then
      local t = (rpm - rpmTable[i - 1]) / (rpmTable[i] - rpmTable[i - 1])
      return tqTable[i - 1] + t * (tqTable[i] - tqTable[i - 1])
    end
  end
  return tqTable[n]
end

local function ersTorque(av)
  if av < 1 then return maxTorque end
  return math.min(maxTorque, deployKW * 1000 / av)
end

local function updateGFX(dt)
  local mode = electrics.values.ersMode or 1
  if mode ~= lastMode then
    lastMode = mode
    guihooks.message({txt = string.format("ERS: %s (%.0f%%)", modeNames[mode] or "?", soc / storeJ * 100), context = {}}, 2, "redbullERS", "settings")
  end

  local throttle = electrics.values.throttle or 0
  local brake = electrics.values.brake or 0
  local rpm = electrics.values.rpm or 0
  local speed = electrics.values.wheelspeed or 0
  local av = rpm * math.pi / 30

  local ice = iceTorque(rpm) * iceScale
  local ers = ersTorque(av)
  local total = ice + ers
  local cap = total > 0 and ice / total or 1

  -- recovery: MGU-K under braking / lifting, MGU-H at high load
  local harvest = 0
  if speed > 5 then
    if brake > 0.05 then
      harvest = harvestKW * math.min(1, brake * 2) * math.min(1, speed / 20)
    elseif throttle < 0.05 then
      harvest = 30
    end
  end
  local mguh = (throttle > 0.8 and rpm > 9000) and mguhKW or 0
  harvest = harvest + mguh

  -- deployment: full MGU-K power above the mode's reserve; at the reserve
  -- only what the MGU-H is recovering right now (it feeds the MGU-K
  -- directly), so the store holds steady instead of toggling every frame
  local minSoc = (reserve[mode + 1] or 0) * storeJ
  local allowKW = 0
  if mode > 0 then
    allowKW = soc > minSoc and deployKW or mguh * 0.9 * 0.95
  end
  local deploying = false
  if throttle > cap then
    local limit = math.min(1, cap + allowKW * 1000 / math.max(total * av, 1))
    if throttle > limit then
      throttle = limit
      electrics.values.throttle = limit
    end
    local power = (throttle - cap) * total * av
    soc = soc - power / 0.95 * dt
    deploying = power > 1000
  end
  soc = math.max(0, math.min(storeJ, soc + harvest * 1000 * 0.9 * dt))

  if mode > 0 and soc <= minSoc + 1 and throttle >= cap and electrics.values.throttle < 1 then
    if not emptyWarned then
      guihooks.message({txt = mode == 2 and "ERS: store empty" or "ERS: reserve reached", context = {}}, 2, "redbullERS", "warning")
      emptyWarned = true
    end
  elseif soc > minSoc + 0.1 * storeJ then
    emptyWarned = false
  end

  electrics.values.ersSOC = soc / storeJ * 100
  electrics.values.ersDeploy = deploying and 1 or 0
end

local function reset()
  soc = storeJ
  lastMode = -1
  electrics.values.ersMode = electrics.values.ersMode or 1
  electrics.values.ersSOC = 100
  electrics.values.ersDeploy = 0
end

local function init(jbeamData)
  deployKW = jbeamData.deployKW or deployKW
  maxTorque = jbeamData.maxTorque or maxTorque
  storeJ = (jbeamData.storeMJ or storeJ / 1e6) * 1e6
  mguhKW = jbeamData.mguhKW or mguhKW
  harvestKW = jbeamData.harvestKW or harvestKW
  iceScale = tonumber(jbeamData.iceScale) or 1
  rpmTable, tqTable = {}, {}
  for _, row in ipairs(jbeamData.iceTorque or {}) do
    table.insert(rpmTable, row[1])
    table.insert(tqTable, row[2])
  end
  electrics.values.ersMode = 1
  reset()
end

M.init = init
M.reset = reset
M.updateGFX = updateGFX

return M
