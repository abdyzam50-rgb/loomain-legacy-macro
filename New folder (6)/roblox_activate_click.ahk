; AutoHotkey v2 script to activate a specific Roblox window,
; move the mouse with a human-like offset, click (with random down/up positions), and exit.

; Activate the specified Roblox window
WinActivate("ahk_class WINDOWSCLIENT")
Sleep 200

; Get the current mouse position
MouseGetPos &x, &y

; Add a small random offset to simulate human hand movement
offsetX := Random(-3, 3)
offsetY := Random(-3, 3)
x := x + offsetX
y := y + offsetY

; Move the mouse to the (possibly offset) position with a smooth movement (20 ms)
MouseMove(x, y, 20)

; Generate random offsets for down and up actions
downX := Random(0, 3)
downY := Random(0, 3)
upX := Random(0, 3)
upY := Random(0, 3)

; Simulate a human-like mouse click (down, delay, up) with random pixel offsets
MouseClick "left", x + downX, y + downY, 1, 0, "D"
Sleep Random(50, 160)
MouseClick "left", x + upX, y + upY, 1, 0, "U"

; Exit the script
ExitApp