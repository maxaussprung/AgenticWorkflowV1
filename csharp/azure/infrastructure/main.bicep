targetScope = 'subscription'

@description('The Object ID of the dev team AAD group.')
param devTeamObjectId string = '{AZURE-AD-GROUP-OBJECT-ID}'

@description('The Object ID of the LZ developers AAD group.')
param devTeamLzObjectId string = '{AZURE-AD-LZ-GROUP-OBJECT-ID}'

@description('The name of the stage currently used.')
param stage string

@description('The URL of the back-end API in Kubernetes.')
param serverUrl string

@description('The object (principal) id of the service connection running the pipeline.')
param serviceConnectionObjectId string

@description('The name of the service connection running the pipeline.')
param serviceConnectionName string

@description('The url to the address endpoint')
param addressUrl string

@description('The Application (client) ID of the app registration that represents the {PROJECT-NAME} API in Azure Active Directory.')
param azureAdClientId string

@description('The nodes of the Typesense cluster.')
param typesenseNodes array

@secure()
@description('The Application (client) secret of the app registration that represents the {PROJECT-NAME} API in Azure Active Directory.')
param azureAdClientSecret string

@description('The Application (client) id of the app registration that represents the swagger client in Azure Active Directory.')
param swaggerClientId string

@description('The OAuth redirect URL of the swagger client.')
param swaggerRedirectUrl string

@description('The scope to request in order to access the {PROJECT-NAME} API.')
param projectApiScope string

@description('The name of the Key Vault resource that provides secrets for the Event Streaming Platform.')
param espKeyVaultName string

@description('The id of the subscription where the resource group of the event streaming platform is')
param espSubscriptionId string

@description('The name of the resource group of the event streaming platform')
param espResourceGroupName string

@description('A unique identifier of the Azure Active Directory instance.')
var tenantId = '{AZURE-AD-TENANT-ID}'  // TODO: your Azure AD tenant ID

var projectName = '{project-name}'  // TODO: replace with your project name
var uniqueTag = substring(uniqueString(rg.id), 0, 4)
var location = deployment().location
var appConfigurationDataReaderRoleId = '516239f1-63e1-4d78-a4de-a74fb236a071'
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var keyVaultReaderRoleId = '21090545-7ca7-4776-b22c-e363652d74d2'
var contributorRoleId = 'b24988ac-6180-42a0-ab88-20f7382dd24c'
var sqlServerName = '${projectName}-sql-server-${stage}-${uniqueTag}'
var sqlServerDatabaseName = '${projectName}-db-${stage}-${uniqueTag}'
var redisName = '${projectName}-redis-${stage}-${uniqueTag}'
var keyVaultName = '${projectName}-key-vault-${stage}-${uniqueTag}'
var appConfigurationName = '${projectName}-app-configuration-${stage}-${uniqueTag}'
var userAssignedManagedIdentityName = '${projectName}-managed-identity-${stage}-${uniqueTag}'
var projectDbLogAnalyticsWorkspaceName = '${projectName}-db-law-${stage}-${uniqueTag}'
var typesenseApiKey = uniqueString('${rg.id}-${location}')
// Storage account names must be between 3 and 24 characters in length and may contain numbers and lowercase letters only.
// https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview#storage-account-name
var storageAccountName = '${projectName}sa${uniqueTag}'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${projectName}'
  location: location
}

module resourceGroupRoleAssignments 'modules/resourceGroupRoleAssignments.bicep' = {
  name: 'resourceGroupRolesAssignmentsDeploy'
  scope: rg
  params: {
    roleAssignments: [
      {
        roleId: contributorRoleId
        principalId: devTeamObjectId
        principalType: 'Group'
      }
      {
        roleId: contributorRoleId
        principalId: devTeamLzObjectId
        principalType: 'Group'
      }
    ]
  }
}

module userAssignedManagedIdentityModule 'modules/userAssignedManagedIdentity.bicep' = {
  name: 'userAssignedManagedIdentityDeploy'
  scope: rg
  params: {
    name: userAssignedManagedIdentityName
    location: location
  }
}

module sqlServerModule 'modules/sqlServer.bicep' = {
  name: 'sqlServerDeploy'
  scope: rg
  params: {
    name: sqlServerName
    administratorId: serviceConnectionObjectId
    administratorName: serviceConnectionName
    administratorPrincipalType: 'Application'
    location: location
    tenantId: tenantId
  }
}

module sqlServerDatabaseModule 'modules/sqlServerDatabase.bicep' = {
  name: 'sqlServerDatabaseDeploy'
  scope: rg
  dependsOn: [
    sqlServerModule
  ]
  params: {
    name: sqlServerDatabaseName
    sqlServerName: sqlServerName
    location: location
  }
}

module redisModule 'modules/redis.bicep' = {
  name: 'redisDeploy'
  scope: rg
  params: {
    name: redisName
    location: location
  }
}

/*
  TODO: Check again for 'objectId' and 'objectIdAlias' to take group Ids
*/
module redisAccessPoliciesModule 'modules/redisAccessPolicies.bicep' = {
  name: 'redisAccessPoliciesDeploy'
  scope: rg
  dependsOn: [
    redisModule
  ]
  params: {
    redisName: redisName
    accessPolicies: [
      {
        name: 'Data Owner'
        objectId: '{AZURE-AD-OBJECT-ID}'  // TODO: replace with your Redis data owner object ID
        objectIdAlias: 'SFPPYWX'
      }
      {
        name: 'Data Contributor'
        objectId: userAssignedManagedIdentityModule.outputs.principalId
        objectIdAlias: userAssignedManagedIdentityModule.outputs.name
      }
    ]
  }
}

module logAnalyticsWorkspaceModule 'modules/logAnalyticsWorkspace.bicep' = {
  name: 'logAnalyticsWorkspaceDeploy'
  scope: rg
  params: {
    name: projectDbLogAnalyticsWorkspaceName
    location: location
  }
}

module applicationInsightsModule 'modules/applicationInsights.bicep' = {
  name: 'applicationInsightsDeploy'
  scope: rg
  params: {
    projectName: projectName
    location: location
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceModule.outputs.logAnalyticsWorkspaceId
    uniqueTag: uniqueTag
  }
}

module keyVaultModule 'modules/keyVault.bicep' = {
  name: 'keyVaultDeploy'
  scope: rg
  params: {
    name: keyVaultName
    location: location
    tenantId: tenantId
  }
}

var keyVaultRoleAssignments = [
    {
      roleId: keyVaultReaderRoleId
      principalId: devTeamObjectId
      principalType: 'Group'
    }
    {
      roleId: keyVaultReaderRoleId
      principalId: devTeamLzObjectId
      principalType: 'Group'
    }
    {
      roleId: keyVaultReaderRoleId
      principalId: userAssignedManagedIdentityModule.outputs.principalId
      principalType: 'ServicePrincipal'
    }
    {
      roleId: keyVaultSecretsUserRoleId
      principalId: devTeamObjectId
      principalType: 'Group'
    }
    {
      roleId: keyVaultSecretsUserRoleId
      principalId: devTeamLzObjectId
      principalType: 'Group'
    }
    {
      roleId: keyVaultSecretsUserRoleId
      principalId: userAssignedManagedIdentityModule.outputs.principalId
      principalType: 'ServicePrincipal'
    }
]

module keyVaultRoleAssignmentsModule 'modules/keyVaultRoleAssignments.bicep' = {
  name: 'keyVaultRoleAssignmentsDeploy'
  scope: rg
  dependsOn: [
    keyVaultModule
  ]
  params: {
    keyVaultName: keyVaultName
    roleAssignments: keyVaultRoleAssignments
  }
}

module espKeyVaultRoleAssignmentsModule 'modules/keyVaultRoleAssignments.bicep' = {
  name: 'espkeyVaultRoleAssignmentsDeploy'
  scope: resourceGroup(espSubscriptionId , espResourceGroupName)
  params: {
    keyVaultName: espKeyVaultName
    roleAssignments: keyVaultRoleAssignments
  }
}

module keyVaultSecretsModule 'modules/keyVaultSecrets.bicep' = {
  name: 'keyVaultSecretsDeploy'
  scope: rg
  dependsOn: [
    keyVaultModule
  ]
  params: {
    keyVaultName: keyVaultName
    secrets: [
      {
        name: 'ConnectionStrings--ApplicationInsights'
        value: applicationInsightsModule.outputs.connectionString
      }
      {
        name: 'ConnectionStrings--{ProjectName}Db'
        value: sqlServerDatabaseModule.outputs.connectionString
      }
      {
        name: 'Typesense--ApiKey'
        value: typesenseApiKey
      }
    ]
  }
}

module appConfigurationModule 'modules/appConfiguration.bicep' = {
  name: 'appConfigurationDeploy'
  scope: rg
  params: {
    name: appConfigurationName
    location: location
  }
}

var staticAppConfigurationKeyValues = [
  {
    key: 'Redis:HostName'
    value: redisModule.outputs.hostName
    contentType: 'text/plain; charset=UTF-8'
  }
  {
    key: 'Swagger:ServerUrls:0'
    value: serverUrl
    contentType: 'text/plain; charset=UTF-8'
  }
  {
    key: 'ConnectionStrings:ApplicationInsights'
    value: '{"uri":"https://${keyVaultModule.outputs.name}.vault.azure.net/Secrets/ConnectionStrings--ApplicationInsights"}'
    contentType: 'application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8'
  }
  {
    key: 'ConnectionStrings:{ProjectName}Db'
    value: '{"uri":"https://${keyVaultModule.outputs.name}.vault.azure.net/Secrets/ConnectionStrings--{ProjectName}Db"}'
    contentType: 'application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8'
  }
  {
    key: 'AddressDomain:ApiUrl'
    value: addressUrl
  }
  {
    key: 'AzureAd:ClientId'
    value: azureAdClientId
  }
  {
    key: 'AzureAd:ClientSecret'
    value: azureAdClientSecret
  }
  {
    key: 'AzureAd:Audience'
    value: 'api://{project-name}/${stage}'
  }
  {
    key: 'Kafka:SaslUsername'
    value: '{"uri":"https://${espKeyVaultName}.vault.azure.net/Secrets/ApiKey"}'
    contentType: 'application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8'
  }
  {
    key: 'Kafka:SaslPassword'
    value: '{"uri":"https://${espKeyVaultName}.vault.azure.net/Secrets/ApiSecret"}'
    contentType: 'application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8'
  }
  {
    key: 'Kafka:BootstrapServers'
    value: '{"uri":"https://${espKeyVaultName}.vault.azure.net/Secrets/BootstrapServers"}'
    contentType: 'application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8'
  }
  {
    key: 'Kafka:SchemaRegistry:BasicAuthUserInfo'
    value: '{"uri":"https://${espKeyVaultName}.vault.azure.net/Secrets/SchemaRegistryBasicAuthUserInfo"}'
    contentType: 'application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8'
  }
  {
    key: 'Kafka:SchemaRegistry:Url'
    value: '{"uri":"https://${espKeyVaultName}.vault.azure.net/Secrets/SchemaRegistryUrl"}'
    contentType: 'application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8'
  }
  {
    key: 'Kafka:Producer:Id'
    value: '{project-name}.api.${stage}'
  }
  {
    key: 'Kafka:Consumer:GroupId'
    value: 'Logistics.{ProjectName}.${stage}'
  }
  {
    key: 'Swagger:ServerUrl'
    value: serverUrl
  }
  {
    key: 'Typesense:ApiKey'
    value: '{"uri":"https://${keyVaultModule.outputs.name}.vault.azure.net/Secrets/Typesense--ApiKey"}'
    contentType: 'text/plain; charset=UTF-8'
  }
  {
    key: 'GenerateMockData'
    value: stage != 'prod'
    contentType: 'text/plain; charset=UTF-8'
  }
  {
    key: 'Swagger:OAuth2RedirectUrl'
    value: swaggerRedirectUrl
    contentType: 'text/plain; charset=UTF-8'
  }
  {
    key: 'Swagger:OAuthClientId'
    value: swaggerClientId
    contentType: 'text/plain; charset=UTF-8'
  }
  {
    key: 'Swagger:Scopes:3:Name'
    value: projectApiScope
    contentType: 'text/plain; charset=UTF-8'
  }
  {
    key: 'StorageAccount:BlobEndpoint'
    value: storageAccountModule.outputs.blobEndpoint
    contentType: 'text/plain; charset=UTF-8'
  }
]

var typesenseNodesKeyValues = [
  for (node, i) in typesenseNodes: [
    {
      key: 'Typesense:Nodes:${i}:Host'
      value: node.host
      contentType: 'text/plain; charset=UTF-8'
    }
    {
      key: 'Typesense:Nodes:${i}:Port'
      value: string(node.port)
      contentType: 'text/plain; charset=UTF-8'
    }
    {
      key: 'Typesense:Nodes:${i}:Protocol'
      value: node.protocol
      contentType: 'text/plain; charset=UTF-8'
    }
  ]
]

module appConfigurationKeyValuesModule 'modules/appConfigurationKeyValues.bicep' = {
  name: 'appConfigurationKeyValuesDeploy'
  scope: rg
  dependsOn: [
    appConfigurationModule
    keyVaultSecretsModule
  ]
  params: {
    appConfigurationName: appConfigurationName
    keyValues: concat(staticAppConfigurationKeyValues, flatten(typesenseNodesKeyValues))
  }
}

module appConfigurationRoleAssignmentsModule 'modules/appConfigurationRoleAssignments.bicep' = {
  name: 'appConfigurationRoleAssignmentsDeploy'
  scope: rg
  dependsOn: [
    appConfigurationModule
  ]
  params: {
    appConfigurationName: appConfigurationName
    roleAssignments: [
      {
        roleId: appConfigurationDataReaderRoleId
        principalId: devTeamObjectId
        principalType: 'Group'
      }
      {
        roleId: appConfigurationDataReaderRoleId
        principalId: devTeamLzObjectId
        principalType: 'Group'
      }
      {
        roleId: appConfigurationDataReaderRoleId
        principalId: userAssignedManagedIdentityModule.outputs.principalId
        principalType: 'ServicePrincipal'
      }
    ]
  }
}

module storageAccountModule 'modules/storageAccount.bicep' = {
  name: 'storageAccountDeploy'
  scope: rg
  params: {
    name: storageAccountName
    location: location
  }
}

module storageAccountRoleAssignmentsModule 'modules/storageAccountRoleAssignments.bicep' = {
  name: 'storageAccountRoleAssignmentsDeploy'
  scope: rg
  dependsOn: [
    storageAccountModule
  ]
  params: {
    storageAccountName: storageAccountName
    roleAssignments: [
      {
        roleId: storageBlobDataContributorRoleId
        principalId: devTeamObjectId
        principalType: 'Group'
      }
      {
        roleId: storageBlobDataContributorRoleId
        principalId: devTeamLzObjectId
        principalType: 'Group'
      }
      {
        roleId: storageBlobDataContributorRoleId
        principalId: userAssignedManagedIdentityModule.outputs.principalId
        principalType: 'ServicePrincipal'
      }
    ]
  }
}

output keyVaultUri string = keyVaultModule.outputs.vaultUri
output keyVaultName string = keyVaultModule.outputs.name
output managedIdentityClientId string = userAssignedManagedIdentityModule.outputs.clientId
output appConfigurationEndpoint string = appConfigurationModule.outputs.endpoint
output managedIdentityName string = userAssignedManagedIdentityName
output sqlServerConnectionString string = sqlServerDatabaseModule.outputs.connectionString
output sqlServerName string = sqlServerName
output sqlServerDatabaseName string = sqlServerDatabaseName
