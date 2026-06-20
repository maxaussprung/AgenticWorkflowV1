@description('The name of the Azure Redis cache resource.')
param redisName string

@description('The secrets and their corresponding values that will be populated when Azure Key Vault resource is created.')
param accessPolicies array

resource redisCache 'Microsoft.Cache/redis@2024-03-01' existing = {
  name: redisName
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.cache/redis/accesspolicies
resource redisCacheAccessPolicies 'Microsoft.Cache/redis/accessPolicyAssignments@2024-03-01' = [
  for accessPolicy in accessPolicies: {
    parent: redisCache
    name: '${accessPolicy.name} | ${accessPolicy.objectIdAlias}'
    properties: {
      accessPolicyName: accessPolicy.name
      objectId: accessPolicy.objectId
      objectIdAlias: accessPolicy.objectIdAlias
    }
  }
]