@description('The name of the Azure region that the resource will be created.')
param location string

@description('The name of the Azure Redis cache.')
param name string

// https://learn.microsoft.com/en-us/azure/templates/microsoft.cache/redis
resource redisCache 'Microsoft.Cache/redis@2024-03-01' = {
  name: name
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    disableAccessKeyAuthentication: true
    redisConfiguration: {
      'aad-enabled': 'true'
      'preferred-data-persistence-auth-method': 'ManagedIdentity'
    }
  }
}

output hostName string = redisCache.properties.hostName