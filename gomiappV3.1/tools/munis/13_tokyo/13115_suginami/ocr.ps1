param([string[]]$Paths)
# Windows OCR (ja): writes "line x y w h text" TSV per word
$asm = [Reflection.Assembly]::LoadFile("C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Runtime.WindowsRuntime.dll")
$ext = $asm.GetType('System.WindowsRuntimeSystemExtensions')
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$asTask = ($ext.GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
$lang = New-Object Windows.Globalization.Language 'ja'
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
foreach ($p in $Paths) {
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
  $out = New-Object System.Text.StringBuilder
  $li = 0
  foreach ($line in $res.Lines) {
    foreach ($w in $line.Words) {
      $r = $w.BoundingRect
      [void]$out.AppendLine(("{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f $li, [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height, $w.Text))
    }
    $li++
  }
  [System.IO.File]::WriteAllText($p + '.tsv', $out.ToString(), [System.Text.Encoding]::UTF8)
  $stream.Dispose()
}
