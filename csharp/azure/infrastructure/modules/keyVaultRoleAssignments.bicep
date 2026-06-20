@description('The role assignments needed for the Key Vault resource.')
param roleAssignments array

@description('The name of the Key Vault resource.')
param keyVaultName string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.authorization/roleassignments
resource keyVaultRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    scope: keyVault
    name: guid(role.principalId, role.roleId, keyVault.id)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role.roleId)
      principalId: role.principalId
      principalType: role.principalType
    }
  }
]