using 'main.bicep'

param stage = 'prod'
param serverUrl = 'https://{project-name}-api.prod.{cluster-domain}'
param serviceConnectionObjectId = '{SERVICE-CONNECTION-OBJECT-ID-PROD}'
param serviceConnectionName = 'serviceConnection-{client-name}-{AZURE-DEVOPS-PROJECT}-{service-connection}-prod'
param addressUrl = 'https://{external-service-api}.prod.{cluster-domain}/'
param azureAdClientId = '{AZURE-AD-CLIENT-ID-PROD}'
param azureAdClientSecret = ''
param swaggerClientId = ''
param swaggerRedirectUrl = 'https://{project-name}-api.prod.{cluster-domain}/docs/oauth2-redirect.html'
param projectApiScope = 'api://{project-name}/prod/read'
param espKeyVaultName = 'sa-{project-name}-prod-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Prod'

param typesenseNodes = [
  {
   host: 'typesense-0.ts.typesense.svc.cluster.local'
   port: 8108
   protocol: 'https'
  }
  {
   host: 'typesense-1.ts.typesense.svc.cluster.local'
   port: 8108
   protocol: 'https'
  }
  {
   host: 'typesense-2.ts.typesense.svc.cluster.local'
   port: 8108
   protocol: 'https'
  }
]
