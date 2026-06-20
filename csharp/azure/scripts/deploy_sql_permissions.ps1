<#
        .SYNOPSIS
        Allowes the automation of role assignements within an SQL server, via an Azure DevOps pipeline unsing a Azure RM service connection.

        .DESCRIPTION
        This script solves a small but important issue in automating the deployment of SQL server roles.
        The current Azure recommended workflow for granting SQL server roles is the T-SQL command "CREATE USER [Azure_AD_Object] FROM EXTERNAL PROVIDER".
        To be able to execute this command while logged in as a Service Principal, the SQL servers system managed identity has to be granted the "Directory Readers" permission first, See link below for more details.
        As granting the "Directory Readers" role can currently not be automated in a reasonable way, this script allows one to circumvent this requirement.
        The script can manage SQL server roles by simply using a Service Principal / Service Connection with the "Directory Readers" role, which allowes for fully automated end to end infrastructure deployments.

        .NOTES
        PREREQUISITES:
            - The Service Principal / Service Connection used needs to be "Azure Active Directory admin" on the SQL server.
            - The Service Principal / Service Connection used needs to have the "Directory Readers" role.
            - Ensure the build machine / build pool you are using is allowed to pass the SQL server firewall.
                - This can be accived by adding the SPN to the Az.AAD.SPN.Deploy.DirectoryRead group, if you need help as Azure Betrieb.
        WARNINGS:
            - Script is subject to changes over time, copy this script into the repository continaing the pipeline it is executed with, do NOT download it at build time !!!

        .PARAMETER SQLServerName
        Specifies the Azure SQL server name.

        .PARAMETER SQLDBNames
        Specifies one or multiple databases you want to grante permissions to.

        .PARAMETER Roles
        Specifies the database level roles you want to apply.
        Multiple roles can be applied.
        !!! IMPORTANT: All roles will be applied to all AzADGroups and AzServicePrincipals passed to the script.

        Fixed-database roles: 
            - db_datareader
            - db_datawriter
            - db_owner
            - db_securityadmin
            - db_accessadmin
            - db_backupoperator
            - db_ddladmin 
            - db_denydatawriter
            - db_denydatareader

        .PARAMETER AzADGroupNames
        Specifies the names of one or multiple Azure AD groups, groups specified have to Azure AD "Security" groups / "Security" enabled groups.

        .PARAMETER AzServicePrincipalNames
        Specifies the names of one or multiple Azure AD Service Principals.

        .PARAMETER RemoveUsers
        Specifies the names of one or multiple SQL users to be removed.

        .INPUTS
        None. You cannot pipe objects.

        .OUTPUTS
        Table of all currnetly configured database level permissions for each database.

        .EXAMPLE
          - task: AzureCLI@2
            displayName: Azure CLI
            inputs:
            azureSubscription: ${{parameters.ServiceConnectionName}}
            scriptType: pscore
            scriptLocation: scriptPath
            scriptPath: '$(System.DefaultWorkingDirectory)/sqlPermissions/psScript/Deploy-SQLPermissions.ps1'   
            arguments: '-SQLServerName ${{ parameters.SQLServerName }} -SQLDBNames ${{ parameters.SQLDBNames }} -Role ${{ parameters.Role }} -AzADGroupNames ${{ parameters.groupDisplayName }} -AzServicePrincipalNames ${{ parameters.AzServicePrincipalNames }}'

        .EXAMPLE
        PS> Deploy-SQLPermissions.ps1 -SQLServerName sqlServer1 -SQLDBNames SampleDB,SampleDB1,SampleDB2 -Roles db_datareader,db_datawriter -AzADGroupNames "Systemteam_Admins","IT_Azure_Betrieb_Users" -AzServicePrincipalNames "all.operations.iac.deployment"

        .EXAMPLE
        PS> Deploy-SQLPermissions.ps1 -SQLServerName sqlServer1 -SQLDBNames SampleDB,SampleDB1,SampleDB2 -RemoveUsers IT_Azure_Betrieb_Users


        .LINK
        https://docs.microsoft.com/en-us/azure/azure-sql/database/authentication-aad-service-principal?view=azuresql#enable-service-principals-to-create-azure-ad-users (Common workflow, can not be fully automated: Enable service principals to create Azure AD users.)
        https://docs.microsoft.com/en-us/sql/relational-databases/security/authentication-access/database-level-roles?view=sql-server-ver16#fixed-database-roles (Fixed-database roles)

    #>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]    
    [string]
    $SQLServerName,
    [Parameter(Mandatory = $true)]
    [string[]]
    $SQLDBNames,
    [ValidateSet(
        "db_datareader",
        "db_datawriter",
        "db_owner",
        "db_securityadmin",
        "db_accessadmin",
        "db_backupoperator",
        "db_ddladmin",
        "db_denydatawriter",
        "db_denydatareader"
    )]
    [string[]]
    $Roles,
    [string[]]
    $AzADGroupNames, 
    [string[]]
    $AzServicePrincipalNames,
    [string[]]
    $RemoveUsers
)

$ErrorActionPreference = "Stop"

function Grant-PermissionsToAzADGroup {
    param (
        [System.Data.SqlClient.SqlConnection]
        $Connection,
        [string]
        $AzADGroupName,
        [Parameter(Mandatory = $true)]
        [string[]]
        $Roles
    )

    # Retrieve AzADGroupId and convert it to SID
    
    $securityEnabled = az ad group list --filter "displayName eq '$AzADGroupName'" --query '[].securityEnabled' | ConvertFrom-Json

    if ($securityEnabled -like "True") {

        $principalAppId = az ad group list --filter "displayName eq '$AzADGroupName'" --query '[].id' | ConvertFrom-Json

        try {
            $principalSid = "0x" + -join ([guid]::Parse($principalAppId).ToByteArray() | ForEach-Object { [string]::Format("{0:X2}", $_) })
        }
        catch {
            throw "Could not retreive valide GUID for Azure AD Group `"$AzADGroupName`" !"
        }

        if ($null -ne "$principalSid") {
            foreach ($Role in $Roles) {
                $connection.Open()
                # Create user based on SID if not exists
                Write-Debug "Session Opened, Role: $Role, AzADGroupName: $AzADGroupName, principalSid: $principalSid "
                $query = @"
IF NOT EXISTS(SELECT name FROM sys.database_principals WHERE name = '$AzADGroupName')
BEGIN
CREATE USER [$AzADGroupName] WITH SID=$principalSid, TYPE=X
ALTER ROLE $Role ADD MEMBER [$AzADGroupName]
END
ELSE
BEGIN
ALTER ROLE $Role ADD MEMBER [$AzADGroupName]
END
"@
                $command = New-Object -Type System.Data.SqlClient.SqlCommand($query, $connection)
                $result = $command.ExecuteNonQuery()
                if ($result -like "-1") {
                    Write-Output "Query execution successful, granted access $Role to $AzADGroupName."
                }
                else {
                    throw Write-Output "Query execution failed, not able to granted access $Role to $AzADGroupName."
                }
                $connection.Close()
            }
        }
    }
    else {
        throw "Azure AD group '$AzADGroupName' is not 'securityEnabled', group can not be used to grant SQL server permissions."
    }


}

function Grant-PermissionsToAzServicePrincipal {
    param (
        [System.Data.SqlClient.SqlConnection]
        $Connection,
        [string]
        $AzServicePrincipalName,
        [Parameter(Mandatory = $true)]
        [string[]]
        $Roles
    )

    # Retrieve AzADGroupId and convert it to SID
    $principalAppId = az ad sp list --filter "displayName eq '$AzServicePrincipalName'" --query '[].appId' | ConvertFrom-Json

    try {
        $principalSid = "0x" + -join ([guid]::Parse($principalAppId).ToByteArray() | ForEach-Object { [string]::Format("{0:X2}", $_) })
    }
    catch {
        throw "Could not retreive valide GUID for Azure AD Service Principal `"$AzServicePrincipalName`" !"
    }

    if ($null -ne "$principalSid") {
        foreach ($Role in $Roles) {      
            $connection.Open()
            # Create user based on SID if not exists
            Write-Debug "Session Opened, Role: $Role, AzADGroupName: $AzServicePrincipalName, principalSid: $principalSid "
            $query = @"
IF NOT EXISTS(SELECT name FROM sys.database_principals WHERE name = '$AzServicePrincipalName')
BEGIN
CREATE USER [$AzServicePrincipalName] WITH SID=$principalSid, TYPE=E
ALTER ROLE $Role ADD MEMBER [$AzServicePrincipalName]
END
ELSE
BEGIN
ALTER ROLE $Role ADD MEMBER [$AzServicePrincipalName]
END
"@
        
            $command = New-Object -Type System.Data.SqlClient.SqlCommand($query, $connection)
            $result = $command.ExecuteNonQuery()
            if ($result -like "-1") {
                Write-Output "Query execution successful, granted  access $Role to $AzServicePrincipalName."
            }
            else {
                throw Write-Output "Query execution failed, not able to granted access $Role to $AzServicePrincipalName."
            }
            $connection.Close()
        }
    }
}

function Remove-User {
    param (
        [System.Data.SqlClient.SqlConnection]
        $connection,
        [PSCustomObject]
        $SQLUserName      
    )

    $connection.Open()
    Write-Host "Connection Opened!"
    # Create user based on SID if not exists

    if ($SQLUserName -notlike "") {
        Write-Debug "Session Opened, Removing user: $SQLUserName"
        $query = @"
IF EXISTS(SELECT name FROM sys.database_principals WHERE name = '$SQLUserName')
BEGIN
DROP USER [$SQLUserName]
END
"@
    
    }

    $command = New-Object -Type System.Data.SqlClient.SqlCommand($query, $connection)
    $result = $command.ExecuteNonQuery()
    if ($result -like "-1") {
        Write-Output "Query execution successful, $SQLUserName did not exist or was removed $SQLUserName."
    }
    else {
        throw Write-Output "Query execution failed, not able to remove $SQLUserName."
    }
    $connection.Close()
}

function Get-DBPermissions {
    param (
        [System.Data.SqlClient.SqlConnection]
        $connection
    )

    $connection.Open()

    $query = @"      
SELECT    roles.principal_id                            AS RolePrincipalID
    ,    roles.name                                    AS RolePrincipalName
    ,    database_role_members.member_principal_id    AS MemberPrincipalID
    ,    members.name                                AS MemberPrincipalName
FROM sys.database_role_members AS database_role_members  
JOIN sys.database_principals AS roles  
    ON database_role_members.role_principal_id = roles.principal_id  
JOIN sys.database_principals AS members  
    ON database_role_members.member_principal_id = members.principal_id;  
"@
    $command = New-Object -Type System.Data.SqlClient.SqlCommand($query, $connection)
    $reader = $command.ExecuteReader()

    $results = @()
    while ($reader.Read()) {
        $row = @{}
        for ($i = 0; $i -lt $reader.FieldCount; $i++) {
            $row[$reader.GetName($i)] = $reader.GetValue($i)
        }
        $results += new-object psobject -property $row            
    }

    $connection.Close();

    $results

}


foreach ($db in $SQLDBNames) {

    # Connect to the database
    $connectionString = "Server=tcp:$SQLServerName.database.windows.net,1433;Initial Catalog=$db;Encrypt=True;" 
    $connection = New-Object System.Data.SqlClient.SqlConnection($connectionString)  
    $connection.AccessToken = az account get-access-token --resource=https://database.windows.net/ --query accessToken | ConvertFrom-Json

    Write-Output "Starting execution on SQL server '$SQLServerName', database '$db'."

    if ($Roles.Count -gt 0) {

        foreach ($spn in $AzServicePrincipalNames) {
            Grant-PermissionsToAzServicePrincipal -connection $connection -AzServicePrincipalName $spn -Roles $Roles
        }

        foreach ($group in $AzADGroupNames) {
            Grant-PermissionsToAzADGroup -connection $connection -AzADGroupName $group -Roles $Roles
        }
    }

    foreach ($User in $RemoveUsers) {
        Remove-User -connection $connection -SQLUserName $User
    }


    Write-Output "Permissions on $db :"

    Get-DBPermissions -connection $connection

    Write-Output "-----------------------------------------------------------------------"
}