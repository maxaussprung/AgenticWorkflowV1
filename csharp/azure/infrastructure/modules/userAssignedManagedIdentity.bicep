// https://learn.microsoft.com/en-us/azure/templates/microsoft.managedidentity/userassignedidentities

@description('The name of the Azure region that the resource will be created.')
param location string

@description('The name of the user-assigned managed identity.')
param name string

resource userAssignedManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
}

output principalId string = userAssignedManagedIdentity.properties.principalId
output clientId string = userAssignedManagedIdentity.properties.clientId
output name string = userAssignedManagedIdentity.name
