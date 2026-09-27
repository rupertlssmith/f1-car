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

--sets brake torque for front and rear brakes. Set identical in jbeam using usual brakeStrength and brakeBias arguments as well.
local brakeTorqueFront = 1600
local brakeTorqueRear = 1400

-- clamp bias to max and min values
local function clampBias(value)
    if value > 0.65 then
        return 0.65
    elseif value < 0.45 then
        return 0.45
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
    startBias = jbeamData.startBias or 0.55 -- set in jbeam using usual controller formatting
    electrics.values.biasChange = 0
end

M.init = init
M.updateGFX = updateGFX

return M