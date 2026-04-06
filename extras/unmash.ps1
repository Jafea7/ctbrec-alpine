# DeCrypt.ps1 R:\Test chrissy_Chaturbate_

param (
  [string]$path,
  [string]$prefix
)

$sevenZip = "P:/7zip/7z.exe"
$include = @("*.mp4")
$files = (Get-ChildItem -Path "$($path)/*" -Include $include)
Push-Location $path
foreach ($file in $files) {
  $origName = "$($prefix)$(($file).BaseName).mkv"
  $passwd = (-join ([security.cryptography.sha256managed]::new().ComputeHash([Text.Encoding]::Utf8.GetBytes("$($origName)")).ForEach{$_.ToString("X2")}).ToLower())
  $cmdArgs = "x -p`"$($passwd)`" $($file)"
  Start-Process $sevenZip -Argument $cmdArgs -NoNewWindow -Wait
}
Pop-Location
