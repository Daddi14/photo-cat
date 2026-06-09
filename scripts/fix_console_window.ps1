# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
param(
    [int]$Columns = 112,
    [int]$Lines = 52
)

$ErrorActionPreference = "SilentlyContinue"

try {
    [Console]::SetWindowSize([Math]::Min($Columns, [Console]::LargestWindowWidth), [Math]::Min($Lines, [Console]::LargestWindowHeight))
    [Console]::SetBufferSize([Math]::Max($Columns, [Console]::BufferWidth), [Math]::Max(300, [Console]::BufferHeight))
}
catch {
}

try {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class ConsoleWindowTools {
    [DllImport("kernel32.dll")]
    public static extern IntPtr GetConsoleWindow();

    [DllImport("user32.dll")]
    public static extern int GetWindowLong(IntPtr hWnd, int nIndex);

    [DllImport("user32.dll")]
    public static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

    [DllImport("user32.dll")]
    public static extern bool DrawMenuBar(IntPtr hWnd);
}
"@ | Out-Null

    $GWL_STYLE = -16
    $WS_SIZEBOX = 0x00040000
    $WS_MAXIMIZEBOX = 0x00010000
    $hwnd = [ConsoleWindowTools]::GetConsoleWindow()

    if ($hwnd -ne [IntPtr]::Zero) {
        $style = [ConsoleWindowTools]::GetWindowLong($hwnd, $GWL_STYLE)
        $style = $style -band (-bnot $WS_SIZEBOX)
        $style = $style -band (-bnot $WS_MAXIMIZEBOX)
        [ConsoleWindowTools]::SetWindowLong($hwnd, $GWL_STYLE, $style) | Out-Null
        [ConsoleWindowTools]::DrawMenuBar($hwnd) | Out-Null
    }
}
catch {
}
