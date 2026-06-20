@description('The keys and their corresponding values that will be populated when App Configuration resource is created.')
param keyValues array

@description('The name of the App Configuration resource.')
param appConfigurationName string

resource appConfiguration 'Microsoft.AppConfiguration/configurationStores@2023-03-01' existing = {
  name: appConfigurationName
}

// https://learn.microsoft.com/en-us/azure/templates/microsoft.appconfiguration/configurationstores/keyvalues
resource appConfigurationKeyValues 'Microsoft.AppConfiguration/configurationStores/keyValues@2023-03-01' = [
  for keyValue in keyValues: {
    name: keyValue.key
    parent: appConfiguration
    properties: {
      contentType: keyValue.?contentType ?? 'text/plain'
      tags: keyValue.?tags ?? {}
      value: keyValue.value
    }
  }
]
