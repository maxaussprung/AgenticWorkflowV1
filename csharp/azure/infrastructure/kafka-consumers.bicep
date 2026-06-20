targetScope = 'subscription'

@description('The name of the Key Vault resource, regarding the Address domain, that provides secrets for the Event Streaming Platform.')
param espAddressDomainKeyVaultName string

@description('The id of the subscription where the resource group of the event streaming platform is')
param espSubscriptionId string

@description('The name of the resource group of the event streaming platform')
param espResourceGroupName string

@description('The object (principal) ID of the managed identity.')
param userAssignedManagedIdentityPrincipalId string

@description('The name of the app configuration service.')
param appConfigurationName string

var location = deployment().location
var keyVaultReaderRoleId = '21090545-7ca7-4776-b22c-e363652d74d2'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var devTeamObjectId = '{AZURE-AD-GROUP-OBJECT-ID}'  // TODO: replace with your dev team AAD group object ID

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-{project-name}'
  location: location
}

var keyVaultRoleAssignments = [
    {
      roleId: keyVaultReaderRoleId
      principalId: devTeamObjectId
      principalType: 'Group'
    }
    {
      roleId: keyVaultReaderRoleId
      principalId: userAssignedManagedIdentityPrincipalId
      principalType: 'ServicePrincipal'
    }
    {
      roleId: keyVaultSecretsUserRoleId
      principalId: devTeamObjectId
      principalType: 'Group'
    }
    {
      roleId: keyVaultSecretsUserRoleId
      principalId: userAssignedManagedIdentityPrincipalId
      principalType: 'ServicePrincipal'
    }
]

module espAddressDomainKeyVaultRoleAssignmentsModule 'modules/keyVaultRoleAssignments.bicep' = {
  name: 'espAddressDomainKeyVaultRoleAssignmentsDeploy'
  scope: resourceGroup(espSubscriptionId , espResourceGroupName)
  params: {
    keyVaultName: espAddressDomainKeyVaultName
    roleAssignments: keyVaultRoleAssignments
  }
}
