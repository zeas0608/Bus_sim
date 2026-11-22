# P0-2 F310 Input Diagnostics — Local verification guide

Status: **code committed, UE5.5.4 build/PIE/F310 device tests NOT YET RUN**.
This feature adds **input capture and on-screen display only**. It does not drive a bus.

## Expected inputs

| F310 control (rear switch set to X) | UE key | Normalized output |
|---|---|---|
| RT | Gamepad Right Trigger Axis | Throttle [0, 1] |
| LT | Gamepad Left Trigger Axis | Clutch [0, 1], 1 = pedal depressed / disengaged |
| Left stick horizontal | Gamepad Left X | Steering [-1, 1] |
| Right stick horizontal / vertical | Gamepad Right X / Right Y | RightStickX/Y [-1, 1] |
| A | Gamepad Face Button Bottom | BrakeHeld true / false |
| LB | Gamepad Left Shoulder | GearDownHeld true / false |
| RB | Gamepad Right Shoulder | GearUpHeld true / false |

Stick deadzone: 0.10 per axis. Trigger deadzone: 0.03. Each remaining
range is normalized to its full extent. Parameters are constants in
`BusInputPlayerController.h` for P0-2; data-driven calibration is later work.

## 1. Update your local working copy

The P0-2 branch was created from `p0/ue55-cpp-foundation`, **not** from main.
In GitHub Desktop: `Fetch origin` → `Current Branch` →
`p0/f310-input-diagnostics` → `Pull origin` (if shown).

If changes exist in your working tree, commit or stash them before changing branches.

## 2. Build with UE closed

- Connect F310 by USB and put the rear switch in **X** (XInput).
- Completely close UE5 Editor before compiling; Live Coding blocks external builds.
- Open `C:\UnrealProjects\Bus_sim\KotodenBusSimulator.sln` in **Visual Studio 2022**.
- Choose `Development Editor` / `Win64`.
- Build the **KotodenBusSimulator** C++ project.
- If Visual Studio reports MSB3073/exit code 6, read the *first actual UnrealBuildTool error* in Build Output.

If new C++ files are not recognized, regenerate Visual Studio project files
with the same procedure used for P0-1, then reopen the solution.

## 3. Test in Unreal Editor

- Launch `KotodenBusSimulator.uproject`.
- Use the existing `Entry` level. No map, blueprint or input asset creation is needed;
  `DefaultEngine.ini` selects `BusInputGameMode` at runtime.
- Press the **Play** triangle, click inside the game viewport, and manipulate the F310.
- Cyan text should show `P0-2 F310 / XInput input test`, numeric axes, and button states.
- RT and LT should each vary independently from approximately 0 to 1.
- Left/right thumbsticks should vary smoothly between -1 and +1.
- A, LB, RB should change to ON only while held.
- Releasing an axis should return it to 0; releasing a button to off.

**If there is no cyan message**: In Play mode check
World Settings → GameMode Override (set to None / BusInputGameMode),
Project Settings → Maps & Modes, and Output Log for `F310:`.
The `Entry` map is dark and might show `BAD SIZE`; this is unrelated to
the input diagnostics.

**If values stay at zero**: click inside PIE, check F310 X switch,
reconnect USB, try Windows `Win + R` → `joy.cpl` → Properties to confirm
Windows is receiving analog input. A zero reading alone does not prove disconnection.

## 4. Verification report to record

- UE version: __________
- Build: PASS / FAIL (paste first compiler error if FAIL)
- PIE debug overlay: PASS / FAIL
- RT independent of LT: PASS / FAIL
- Left X / Right X / Right Y: PASS / FAIL
- A / LB / RB hold/release: PASS / FAIL
- Notes (axis inversion, jitter, missing inputs): __________

Do not report P0-2 complete until these tests pass on the actual Windows PC.
