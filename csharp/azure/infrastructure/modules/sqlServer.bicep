@description('The name of the SQL Server instance.')
param name string

@description('The name of the Azure region that the resource will be created.')
param location string

@description('SID (object ID) of the server administrator.')
param administratorId string

@description('Login name of the server administrator.')
param administratorName string

@description('Principal Type of the sever administrator.')
param administratorPrincipalType string

@description('A unique identifier of the Azure Active Directory instance.')
param tenantId string

// https://learn.microsoft.com/en-us/azure/templates/microsoft.sql/servers
resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: name
  location: location
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: administratorName
      principalType: administratorPrincipalType
      sid: administratorId
      tenantId: tenantId
    }
    minimalTlsVersion: '1.2'
  }
}

resource allowAccessToAzureServices 'Microsoft.Sql/servers/firewallRules@2020-11-01-preview' = {
    name: 'allow-access-to-azure-services'
    parent: sqlServer
    properties: {
        startIpAddress: '0.0.0.0'
        endIpAddress: '255.255.255.255'
    }
}