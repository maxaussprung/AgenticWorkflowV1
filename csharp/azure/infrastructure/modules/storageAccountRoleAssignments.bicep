@description('The role assignments needed for the App Configuration resource.')
param roleAssignments array

@description('The name of the Storage Account resource.')
param storageAccountName string

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.authorization/roleassignments
resource storageAccountRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    scope: storageAccount
    name: guid(role.principalId, role.roleId, storageAccount.id)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role.roleId)
      principalId: role.principalId
      principalType: role.principalType
    }
  }
]
