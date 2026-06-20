using 'main.bicep'

param stage = 'dev'
param serverUrl = 'https://{project-name}-api.dev.{cluster-domain}'
param serviceConnectionObjectId = '{SERVICE-CONNECTION-OBJECT-ID-DEV}'
param serviceConnectionName = 'serviceConnection-{client-name}-{AZURE-DEVOPS-PROJECT}-{service-connection}-dev'
param addressUrl = 'https://{external-service-api}.dev.{cluster-domain}/'
param azureAdClientId = '{AZURE-AD-CLIENT-ID-DEV}'
param azureAdClientSecret = ''
param swaggerClientId = '{SWAGGER-CLIENT-ID-DEV}'
param swaggerRedirectUrl = 'https://{project-name}-api.dev.{cluster-domain}/docs/oauth2-redirect.html'
param projectApiScope = 'api://{project-name}/dev/read'
param espKeyVaultName = 'sa-{project-name}-dev-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Dev'

param typesenseNodes = [
  {
   host: 'typesense-0.ts.typesense.svc.cluster.local'
   port: 8108
   protocol: 'https'
  }
]
