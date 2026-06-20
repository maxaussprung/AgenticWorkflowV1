
param(
    [string]$SQLServerName,
    [string]$DatabaseName
)

Write-Host "Connecting to server: $SQLServerName"
Write-Host "Connecting to database: $DatabaseName"

$connectionString = "Server=tcp:$SQLServerName.database.windows.net,1433;Initial Catalog=$DatabaseName;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;"


# Get token for Azure SQL
$accessToken = az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv

$connection = New-Object System.Data.SqlClient.SqlConnection
$connection.ConnectionString = $connectionString
$connection.AccessToken = $accessToken
$connection.Open()

Write-Host "Connected successfully using access token."

$currentDb = $connection.Database
if ($currentDb -ne $DatabaseName) {
    Write-Error "Connected to wrong database: $currentDb instead of $DatabaseName"
    exit 1
}

# Delete orders command
$command = $connection.CreateCommand()

$command.CommandText = @"
-- TODO: Replace this with your project-specific cleanup query
-- Example: DELETE FROM dbo.{TableName} WHERE {Condition}
-- DELETE FROM dbo.Orders WHERE Type = 13 AND OwnerId NOT IN ('...','...')
"@

$rowsAffected = $command.ExecuteNonQuery()

Write-Host "$rowsAffected rows deleted."
# Cleanup

$connection.Close()
Write-Host "Connection closed."
