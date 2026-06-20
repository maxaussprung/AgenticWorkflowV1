@description('The name of the SQL Server database.')
param name string

@description('The name of the SQL Server instance.')
param sqlServerName string

@description('The name of the Azure region that the resource will be created.')
param location string

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' existing = {
  name: sqlServerName
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.sql/servers/databases
resource projectDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: name
  location: location
  sku: {
    //capacity: 2
    //family: 'Gen5'
    //name: 'HS_Gen5_2'
    //size: 'HS_Gen5'
    //tier: 'Hyperscale'
    name: 'S0'
    tier: 'Standard'
  }
  properties: {
    autoPauseDelay: -1
  }
}

output connectionString string = 'Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Initial Catalog=${projectDatabase.name};Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;Authentication="Active Directory Default";'