# DeCrypt.ps1 R:\Test chrissy_Chaturbate_

param (
  [string]$path,
  [string]$prefix,
  [switch]$delete
)

$sevenZip = "P:/7zip/7z.exe"
$include = @("*.mp4")
$files = (Get-ChildItem -Path "$($path)/*" -Include $include)
Push-Location $path
foreach ($file in $files) {
  $origName = "$($prefix)$(($file).BaseName).mkv"
  $passwd = (-join ([security.cryptography.sha256managed]::new().ComputeHash([Text.Encoding]::Utf8.GetBytes("$($origName)")).ForEach{$_.ToString("X2")}).ToLower())
  
  $cmdArgs = @("x", "-y", "-p$passwd", $file.FullName)
  & $sevenZip $cmdArgs 2>&1 | Out-Null
  
  if ($LASTEXITCODE -eq 0) {
    Write-Host "$($file.Name): success"
    if ($delete) {
      $outFile = Join-Path -Path $file.DirectoryName -ChildPath $origName
      if (Test-Path $outFile) {
        $inSize = $file.Length
        $outSize = (Get-Item $outFile).Length
        
        $minSize = $inSize * 0.9
        $maxSize = $inSize * 1.1
        
        if ($outSize -ge $minSize -and $outSize -le $maxSize) {
          Remove-Item -Path $file.FullName -Force
        }
      }
    }
  } else {
    Write-Host "$($file.Name): fail"
  }
}
Pop-Location
