@description('The name of the Azure region that the resource will be created.')
param location string

@description('The name of the App Configuration resource.')
param name string

// https://learn.microsoft.com/en-us/azure/templates/microsoft.appconfiguration/configurationstores
resource appConfiguration 'Microsoft.AppConfiguration/configurationStores@2023-03-01' = {
  name: name
  location: location
  sku: {
    name: 'Free'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    createMode: 'Default'
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
  }
}

output endpoint string = 'https://${appConfiguration.name}.azconfig.io'
