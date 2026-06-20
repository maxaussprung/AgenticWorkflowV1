// https://learn.microsoft.com/en-us/azure/templates/microsoft.operationalinsights/workspaces

@description('The name of the Azure region that the resource will be created.')
param location string

@description('The name of the Log Analytics Workspace resource.')
param name string

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: name
  location: location
}

output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id