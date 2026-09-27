local M = {}

-- Made by LucasBE
-- Do not reuse or modify without permission. Feel free to use this as reference for your own code.

pitLimiterSpeed = 22.22 -- default is 80 km/h, use M/s

local topSpeedLimitPID = newPIDParallel(0.5, 0.8, 0, 0, 1, 50, 20, 0, 1)
local pitMsg = 1

local function onReset()
    electrics.values.pitLimiter = 0
  end


local function updateGFX(dt)

-- Main toggle idk
if electrics.values.pitLimiter == 1 then

	electrics.values.ledAlarm = 1

	if electrics.values.wheelspeed >= pitLimiterSpeed then

		local vehicleSpeed = electrics.values.wheelspeed or 0
		if vehicleSpeed >= pitLimiterSpeed then
		    local speedError = vehicleSpeed - pitLimiterSpeed
		    local throttleCoef = 1 - topSpeedLimitPID:get(-speedError, 0, dt)
		    electrics.values.throttle = electrics.values.throttle * throttleCoef
		end
		
		end
	else

		-- electrics.values.throttle = input.throttle
		electrics.values.ledAlarm = 0

	end
-- Pit Limiter GUI Message
if electrics.values.pitLimiter == 1 then 

	if pitMsg == 1 then
	gui.message("Pit Limiter enabled", 2, "nil", "flag")
	end
	pitMsg = 0

elseif electrics.values.pitLimiter == 0 then 

	if pitMsg == 0 then
	gui.message("Pit Limiter disabled", 2, "nil", "flag")
	end
	pitMsg = 1

end
end

-- public interface
M.onReset = onReset
M.updateGFX = updateGFX
return M