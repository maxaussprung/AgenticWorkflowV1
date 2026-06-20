@description('The role assignments needed for the App Configuration resource.')
param roleAssignments array

@description('The name of the App Configuration resource.')
param appConfigurationName string

resource appConfiguration 'Microsoft.AppConfiguration/configurationStores@2023-03-01' existing = {
  name: appConfigurationName
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.authorization/roleassignments
resource appConfigurationRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    scope: appConfiguration
    name: guid(role.principalId, role.roleId, appConfiguration.id)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role.roleId)
      principalId: role.principalId
      principalType: role.principalType
    }
  }
]
