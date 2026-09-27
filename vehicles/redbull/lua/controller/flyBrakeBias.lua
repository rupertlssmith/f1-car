-- Brake bias controller by Zeit and LucasBE
-- Do not reuse or modify without permission

local M = {}
M.type = "auxiliary"

local timer = 1 -- timer duration in seconds

local startBias = 0
local lastBrakeBiasNeeded = 0
local biasChanged = 0
electrics.values.biasChange = 0
electrics.values.biasDifferent = 0

--brake torque for front and rear brakes (per wheel, before the bias split) and
--the bias range. Passed in from the jbeam controller row so they match the
--brakes' own brakeStrength/brakeBias expressions (RB14: see redbull.jbeam).
local brakeTorqueFront = 5000
local brakeTorqueRear = 5000
local minBias = 0.50
local maxBias = 0.64

-- clamp bias to max and min values
local function clampBias(value)
    if value > maxBias then
        return maxBias
    elseif value < minBias then
        return minBias
    end

    return value
end

local function updateGFX(dt)
    local biasNeeded = clampBias(startBias + electrics.values.biasChange)
    electrics.values.biasChange = biasNeeded - startBias
    
    -- screen bias change timer
    if electrics.values.biasDifferent > 0 then
      electrics.values.biasDifferent = electrics.values.biasDifferent - dt
      --print(electrics.values.biasDifferent) --debug
    end

    -- check if bias changed, return if not
    if lastBrakeBiasNeeded == biasNeeded then return end
    lastBrakeBiasNeeded = biasNeeded

      biasChanged = 1
      electrics.values.biasDifferent = timer

    -- gui message
    guihooks.message({txt = string.format("Brake Bias : %.1f%%",biasNeeded*100), context = {}}, 1, "nil", "settings")
    --print(biasNeeded) --debug
    --print(electrics.values.biasChange) --debug

    -- apply
    for _, wd in pairs(wheels.wheels) do
        if wd.name:sub(0,1) == "F" then
            wd.brakeTorque = brakeTorqueFront*biasNeeded
        elseif wd.name:sub(0,1) == "R" then
            wd.brakeTorque = brakeTorqueRear*(1-biasNeeded)
        end
    end
    
    --send current formatted bias to electrics for use elsewhere
    electrics.values.biasInfo = string.format("%.1f%%",biasNeeded*100)
end

local function init(jbeamData)
    startBias = jbeamData.startBias or 0.57 -- set in jbeam using usual controller formatting
    brakeTorqueFront = jbeamData.torqueFront or brakeTorqueFront
    brakeTorqueRear = jbeamData.torqueRear or brakeTorqueRear
    minBias = jbeamData.minBias or minBias
    maxBias = jbeamData.maxBias or maxBias
    electrics.values.biasChange = 0
end

M.init = init
M.updateGFX = updateGFX

return M