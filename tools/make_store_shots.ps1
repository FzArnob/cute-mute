<#
    Build the Microsoft Store screenshots (1920x1080 PNG).

        # start CuteMute so its settings window is open, then:
        powershell -File tools\make_store_shots.ps1

    Shot 1 is a real capture of the settings window, composited onto the brand
    background with the headline beside it.
    Shot 2 is the badge sitting above a stand-in window, drawn entirely from the
    generated brand assets -- no real desktop content, and nothing that claims a
    UI which does not exist.

    Output: packaging/store/. See packaging/store/LISTING.md.
#>
Add-Type -AssemblyName System.Drawing, System.Windows.Forms

$capture = @'
using System;
using System.Runtime.InteropServices;
public class CM {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RC r);
  // PW_RENDERFULLCONTENT: read the window's own pixels, whatever is in front of
  // it. CopyFromScreen would capture whatever happens to be on top -- which, on
  // a machine with a fullscreen game running, is the game.
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  public struct RC { public int L, T, Rt, B; }
}
'@
Add-Type -TypeDefinition $capture

$repo = Split-Path -Parent $PSScriptRoot
$outDir = "$repo\packaging\store"
New-Item -ItemType Directory -Force $outDir | Out-Null

# --- capture the live settings window ------------------------------------- #
$proc = Get-Process CuteMute -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) {
    Write-Host "Start CuteMute first, with its settings window open." -ForegroundColor Red
    Write-Host "  .\dist\CuteMute\CuteMute.exe    (or the installed copy)"
    exit 1
}
$rc = New-Object CM+RC
[CM]::GetWindowRect($proc.MainWindowHandle, [ref]$rc) | Out-Null
$ww = $rc.Rt - $rc.L; $wh = $rc.B - $rc.T
if ($ww -lt 200 -or $wh -lt 200) {
    Write-Host "the CuteMute window is $ww x $wh -- is it minimised?" -ForegroundColor Red
    exit 1
}
$shot = New-Object System.Drawing.Bitmap($ww, $wh)
$sg = [System.Drawing.Graphics]::FromImage($shot)
$hdc = $sg.GetHdc()
$ok = [CM]::PrintWindow($proc.MainWindowHandle, $hdc, 2)
$sg.ReleaseHdc($hdc)
$sg.Dispose()
if (-not $ok) {
    Write-Host "PrintWindow failed on the CuteMute window" -ForegroundColor Red
    exit 1
}

# Refuse anything that is not CuteMute's own UI. Every pixel it draws comes from
# theme.py, which is uniformly dark; if a capture comes back bright we grabbed
# something else, and that something else must not reach a Store listing.
$dark = 0; $sampled = 0
for ($sy = 4; $sy -lt $wh; $sy += 17) {
    for ($sx = 4; $sx -lt $ww; $sx += 17) {
        $px = $shot.GetPixel($sx, $sy)
        $sampled++
        if ($px.R -lt 90 -and $px.G -lt 90 -and $px.B -lt 110) { $dark++ }
    }
}
$ratio = $dark / [double]$sampled
Write-Host ("captured {0}x{1}, {2:P0} of sampled pixels are dark" -f $ww, $wh, $ratio)
if ($ratio -lt 0.70) {
    Write-Host "" 
    Write-Host "That capture does not look like CuteMute." -ForegroundColor Red
    Write-Host "CuteMute's window is uniformly dark; this one is not, so it is" -ForegroundColor Red
    Write-Host "almost certainly another window. Refusing to write it." -ForegroundColor Red
    $shot.Dispose()
    exit 1
}

$W = 1920; $H = 1080

# cutemute/theme.py
$cBg      = [System.Drawing.Color]::FromArgb(0x0E, 0x0E, 0x10)
$cBgLift  = [System.Drawing.Color]::FromArgb(0x1A, 0x1A, 0x22)
$cTitle   = [System.Drawing.Color]::FromArgb(0xE9, 0xE9, 0xEC)
$cText    = [System.Drawing.Color]::FromArgb(0xF3, 0xF3, 0xF5)
$cDim     = [System.Drawing.Color]::FromArgb(0x8B, 0x8B, 0x94)
$cFaint   = [System.Drawing.Color]::FromArgb(0x5A, 0x5A, 0x63)
$cRed     = [System.Drawing.Color]::FromArgb(0xE5, 0x48, 0x4D)
$cBorder  = [System.Drawing.Color]::FromArgb(0x3A, 0x3A, 0x42)

function New-Canvas {
    $bmp = New-Object System.Drawing.Bitmap($W, $H,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

    # Vertical wash for the ground.
    $rect = New-Object System.Drawing.Rectangle(0, 0, $W, $H)
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        $rect, $cBgLift, $cBg, 60.0)
    $g.FillRectangle($brush, $rect)
    $brush.Dispose()
    return @($bmp, $g)
}

function Add-Glow($g, $cx, $cy, $radius, $colour, $strength) {
    # Concentric translucent ellipses: a cheap radial falloff with no visible edge.
    for ($i = 48; $i -ge 1; $i--) {
        $f = $i / 48.0
        $a = [int]($strength * (1.0 - $f) * (1.0 - $f))
        if ($a -le 0) { continue }
        $r = $radius * $f
        $b = New-Object System.Drawing.SolidBrush(
            [System.Drawing.Color]::FromArgb($a, $colour.R, $colour.G, $colour.B))
        $g.FillEllipse($b, $cx - $r, $cy - $r, $r * 2, $r * 2)
        $b.Dispose()
    }
}

function Add-Shadow($g, $x, $y, $w, $h) {
    for ($i = 30; $i -ge 1; $i--) {
        $a = [int](70.0 / $i)
        $b = New-Object System.Drawing.SolidBrush(
            [System.Drawing.Color]::FromArgb($a, 0, 0, 0))
        $g.FillRectangle($b, $x - $i, $y - $i + 10, $w + 2 * $i, $h + 2 * $i)
        $b.Dispose()
    }
}

function Font($size, $style) {
    foreach ($name in @("Segoe UI Variable Display", "Segoe UI", "Arial")) {
        try { return New-Object System.Drawing.Font($name, $size, $style) } catch {}
    }
}

$bold = [System.Drawing.FontStyle]::Bold
$reg  = [System.Drawing.FontStyle]::Regular

# ---------------------------------------------------------------- shot 1 ---- #
$pair = New-Canvas
$bmp = $pair[0]; $g = $pair[1]

$winX = 1180; $winY = [int](($H - $shot.Height) / 2)
Add-Glow $g ($winX + $shot.Width / 2) ($winY + $shot.Height / 2) 620 $cRed 16
Add-Shadow $g $winX $winY $shot.Width $shot.Height
$g.DrawImage($shot, $winX, $winY, $shot.Width, $shot.Height)

$mark = [System.Drawing.Image]::FromFile("$repo\docs\assets\icon-512.png")
$g.DrawImage($mark, 150, 250, 132, 132)

$fTitle = Font 62 $bold
$fLede  = Font 25 $reg
$fItem  = Font 20 $reg
$bTitle = New-Object System.Drawing.SolidBrush($cTitle)
$bLede  = New-Object System.Drawing.SolidBrush($cDim)
$bItem  = New-Object System.Drawing.SolidBrush($cText)
$bFaint = New-Object System.Drawing.SolidBrush($cFaint)

$g.DrawString("CuteMute", $fTitle, $bTitle, 146, 404)
$g.DrawString("One key to mute your microphone", $fLede, $bLede, 152, 492)

$y = 580
foreach ($line in @(
    "Works while any app has focus",
    "A badge on top of everything while muted",
    "Mutes every microphone at once",
    "No installer, no dependencies, no telemetry"
)) {
    $dot = New-Object System.Drawing.SolidBrush($cRed)
    $g.FillEllipse($dot, 154, $y + 11, 9, 9)
    $dot.Dispose()
    $g.DrawString($line, $fItem, $bItem, 180, $y)
    $y += 52
}
$sep = [string][char]0x00B7
$g.DrawString("Free and open source  $sep  MIT licensed", $fItem, $bFaint, 150, $y + 26)

$bmp.Save("$outDir\screenshot-1-settings.png",
          [System.Drawing.Imaging.ImageFormat]::Png)
$shot.Dispose(); $g.Dispose(); $bmp.Dispose()
Write-Host "wrote screenshot-1-settings.png"

# ---------------------------------------------------------------- shot 2 ---- #
# The badge doing its job: a stand-in window with the badge above it, at the
# size and corner the defaults use.
$pair = New-Canvas
$bmp = $pair[0]; $g = $pair[1]

$mx = 300; $my = 190; $mw = 1320; $mh = 700
Add-Glow $g ($mx + $mw / 2) ($my + $mh / 2) 780 $cRed 10
Add-Shadow $g $mx $my $mw $mh

$bWin = New-Object System.Drawing.SolidBrush(
    [System.Drawing.Color]::FromArgb(0x16, 0x17, 0x1D))
$g.FillRectangle($bWin, $mx, $my, $mw, $mh)
$bWin.Dispose()
$pen = New-Object System.Drawing.Pen($cBorder, 1)
$g.DrawRectangle($pen, $mx, $my, $mw, $mh)

# A title bar and two panes: enough to read as a window without pretending to
# be a specific application.
$bChrome = New-Object System.Drawing.SolidBrush(
    [System.Drawing.Color]::FromArgb(0x1C, 0x1D, 0x24))
$g.FillRectangle($bChrome, $mx, $my, $mw, 44)
$bChrome.Dispose()
$g.DrawLine($pen, $mx, $my + 44, $mx + $mw, $my + 44)
$g.DrawLine($pen, $mx + 330, $my + 44, $mx + 330, $my + $mh)
foreach ($i in 0..2) {
    $b = New-Object System.Drawing.SolidBrush(
        [System.Drawing.Color]::FromArgb(0x3A, 0x3C, 0x46))
    $g.FillEllipse($b, $mx + 18 + $i * 22, $my + 17, 11, 11)
    $b.Dispose()
}
$rowB = New-Object System.Drawing.SolidBrush(
    [System.Drawing.Color]::FromArgb(0x2C, 0x2E, 0x38))
foreach ($i in 0..7) {
    $g.FillRectangle($rowB, $mx + 30, $my + 84 + $i * 34, 250 - ($i % 3) * 60, 11)
}
foreach ($i in 0..11) {
    $g.FillRectangle($rowB, $mx + 372, $my + 84 + $i * 40, 880 - ($i % 4) * 150, 12)
}
$rowB.Dispose()

# The badge, over the window, in the bottom-right corner as the defaults place it.
$badge = [System.Drawing.Image]::FromFile("$repo\docs\assets\icon-512.png")
$bs = 84
$bx = $mx + $mw - $bs - 46; $by = $my + $mh - $bs - 46
Add-Glow $g ($bx + $bs / 2) ($by + $bs / 2) 165 $cRed 16
$g.DrawImage($badge, $bx, $by, $bs, $bs)

$fCap = Font 30 $bold
$fSub = Font 21 $reg
$bCap = New-Object System.Drawing.SolidBrush($cTitle)
$g.DrawString("You are muted, and you can see it", $fCap, $bCap, 300, 962)
$g.DrawString("It stays above every window until you unmute. Click-through, never steals focus. Shown enlarged; the default is 20 px.",
              $fSub, $bLede, 302, 1008)

$g.DrawString("CuteMute", (Font 26 $bold), $bCap, 302, 108)
$badgeSmall = $badge
$g.DrawImage($badgeSmall, 300, 44, 46, 46)

$bmp.Save("$outDir\screenshot-2-badge.png",
          [System.Drawing.Imaging.ImageFormat]::Png)
$badge.Dispose(); $pen.Dispose(); $g.Dispose(); $bmp.Dispose()
Write-Host "wrote screenshot-2-badge.png"

Get-ChildItem $outDir -Filter *.png | ForEach-Object {
    $img = [System.Drawing.Image]::FromFile($_.FullName)
    Write-Host ("  {0,-30} {1}x{2}  {3:N0} bytes" -f $_.Name, $img.Width, $img.Height, $_.Length)
    $img.Dispose()
}
