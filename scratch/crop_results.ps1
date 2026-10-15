Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile('docs/ui-reference/agent2/S2-06-results-overview.png')
$crops = @(
    @{ name='s2_06_header.png'; y=0; h=350 }
)
foreach ($c in $crops) {
    $rect = New-Object System.Drawing.Rectangle(0, $c.y, $img.Width, [Math]::Min($c.h, $img.Height - $c.y))
    $bmp = New-Object System.Drawing.Bitmap($rect.Width, $rect.Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($img, (New-Object System.Drawing.Rectangle(0, 0, $rect.Width, $rect.Height)), $rect, [System.Drawing.GraphicsUnit]::Pixel)
    $bmp.Save("scratch/$($c.name)", [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
}
$img.Dispose()
