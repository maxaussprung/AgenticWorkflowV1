@description('The name of the Azure region that the resource will be created.')
param location string

@description('A unique identifier of the Azure Active Directory instance.')
param tenantId string

@description('The name of the Key Vault resource.')
param name string

// https://learn.microsoft.com/en-us/azure/templates/microsoft.keyvault/vaults
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  properties: {
    accessPolicies: []
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enabledForTemplateDeployment: true
    enableRbacAuthorization: true
    enableSoftDelete: true // Can only be changed when key vault is created for the first time.
  }
}

output vaultUri string = keyVault.properties.vaultUri
output name string = keyVault.name
