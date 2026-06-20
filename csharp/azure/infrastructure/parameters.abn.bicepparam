using 'main.bicep'

param stage = 'abn'
param serverUrl = 'https://{project-name}-api.abn.{cluster-domain}'
param serviceConnectionObjectId = '{SERVICE-CONNECTION-OBJECT-ID-ABN}'
param serviceConnectionName = 'serviceConnection-{client-name}-{AZURE-DEVOPS-PROJECT}-{service-connection}-abn'
param addressUrl = 'https://{external-service-api}.abn.{cluster-domain}/'
param azureAdClientId = '{AZURE-AD-CLIENT-ID-ABN}'
param azureAdClientSecret = ''
param swaggerClientId = ''
param swaggerRedirectUrl = 'https://{project-name}-api.abn.{cluster-domain}/docs/oauth2-redirect.html'
param projectApiScope = 'api://{project-name}/abn/read'
param espKeyVaultName = 'sa-{project-name}-abn-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Abn'

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
