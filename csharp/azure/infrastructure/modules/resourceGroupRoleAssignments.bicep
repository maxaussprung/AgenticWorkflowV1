@description('The role assignments needed for the App Configuration resource.')
param roleAssignments array

// theory: https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/scenarios-rbac
// parameters: https://learn.microsoft.com/en-us/azure/templates/microsoft.authorization/roleassignments
resource resourceGroupRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in roleAssignments: {
    name: guid(role.principalId, role.roleId, resourceGroup().id)
    scope: resourceGroup()
    properties: {
      principalId: role.principalId
      principalType: role.principalType
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role.roleId)
    }
  }
]