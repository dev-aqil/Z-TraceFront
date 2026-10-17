param(
    [string]$Key = "$env:USERPROFILE\.ssh\linuxone-teammate",
    [string]$Server = "linux1@148.100.77.171",
    [int]$BackendPort = 8000,
    [int]$MlPort = 8100
)
# Keep this terminal open while presenting. A failed local port bind fails the command.
ssh -i $Key -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L "${BackendPort}:127.0.0.1:8000" -L "${MlPort}:127.0.0.1:8100" $Server
