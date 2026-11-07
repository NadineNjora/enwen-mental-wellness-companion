# Code-drawn ENWEN flower icons. No external images or fonts are required.
Add-Type -AssemblyName System.Drawing
$enwenIconDir = Join-Path $PSScriptRoot '..\frontend\icons'
New-Item -ItemType Directory -Path $enwenIconDir -Force | Out-Null
foreach ($enwenIconSize in @(180,192,512)) {
    $enwenBitmap = New-Object System.Drawing.Bitmap($enwenIconSize,$enwenIconSize)
    $enwenGraphics = [System.Drawing.Graphics]::FromImage($enwenBitmap)
    $enwenGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $enwenGraphics.ScaleTransform($enwenIconSize/512.0,$enwenIconSize/512.0)
    $enwenGraphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#fff8ee'))
    $enwenInk = New-Object System.Drawing.Pen([System.Drawing.ColorTranslator]::FromHtml('#241c36'),10)
    $enwenStem = New-Object System.Drawing.Pen([System.Drawing.ColorTranslator]::FromHtml('#6f8b4e'),16)
    $enwenPetal = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml('#ded0f5'))
    $enwenCentre = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml('#ddf780'))
    try {
        $enwenGraphics.DrawLine($enwenStem,256,260,256,405)
        $enwenGraphics.DrawArc($enwenStem,174,312,82,48,0,165)
        for ($enwenAngle=0; $enwenAngle -lt 360; $enwenAngle+=60) {
            $enwenState=$enwenGraphics.Save()
            $enwenGraphics.TranslateTransform(256,224)
            $enwenGraphics.RotateTransform($enwenAngle)
            $enwenGraphics.FillEllipse($enwenPetal,-44,-128,88,136)
            $enwenGraphics.DrawEllipse($enwenInk,-44,-128,88,136)
            $enwenGraphics.Restore($enwenState)
        }
        $enwenGraphics.FillEllipse($enwenCentre,210,178,92,92)
        $enwenGraphics.DrawEllipse($enwenInk,210,178,92,92)
        $enwenBitmap.Save((Join-Path $enwenIconDir "enwen-$enwenIconSize.png"),[System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $enwenInk.Dispose();$enwenStem.Dispose();$enwenPetal.Dispose();$enwenCentre.Dispose();$enwenGraphics.Dispose();$enwenBitmap.Dispose()
    }
}
Write-Output 'Generated public ENWEN icons at 180, 192 and 512 pixels.'
