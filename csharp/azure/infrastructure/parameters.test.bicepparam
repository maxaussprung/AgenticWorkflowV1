using 'main.bicep'

param stage = 'test'
param serverUrl = 'https://{project-name}-api.test.{cluster-domain}'
param serviceConnectionObjectId = '{SERVICE-CONNECTION-OBJECT-ID-TEST}'
param serviceConnectionName = 'serviceConnection-{client-name}-{AZURE-DEVOPS-PROJECT}-{service-connection}-test'
param addressUrl = 'https://{external-service-api}.test.{cluster-domain}/'
param azureAdClientId = '{AZURE-AD-CLIENT-ID-TEST}'
param azureAdClientSecret = ''
param swaggerClientId = ''
param swaggerRedirectUrl = 'https://{project-name}-api.test.{cluster-domain}/docs/oauth2-redirect.html'
param projectApiScope = 'api://{project-name}/test/read'
param espKeyVaultName = 'sa-{project-name}-test-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Test'

param typesenseNodes = [
  {
   host: 'typesense-0.ts.typesense.svc.cluster.local'
   port: 8108
   protocol: 'https'
  }
]
