//  https://learn.microsoft.com/en-us/azure/templates/microsoft.insights/components
@description('The name of the application')
param projectName string

@description('The name of the Azure region that the resource will be created.')
param location string

@description('Resource Id of the log analytics workspace which the data will be ingested to.')
param logAnalyticsWorkspaceId string

@description('A value generated to provide uniqueness to Azure resource names.')
param uniqueTag string

resource apiApplicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${projectName}-api-application-insights-${uniqueTag}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'     
    WorkspaceResourceId: logAnalyticsWorkspaceId
  }
}

output connectionString string = apiApplicationInsights.properties.ConnectionString