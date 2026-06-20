@description('The secrets and their corresponding values that will be populated when Azure Key Vault resource is created.')
param secrets array

@description('The name of the Key Vault resource.')
param keyVaultName string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.keyvault/vaults/secrets
resource keyVaultSecrets 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = [
  for secret in secrets: {
    parent: keyVault
    name: secret.name
    properties: {
      value: secret.value
      contentType: secret.?contentType ?? 'text/plain'
    }
  }
]
