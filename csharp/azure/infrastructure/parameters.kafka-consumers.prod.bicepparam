using 'kafka-consumers.bicep'

param espAddressDomainKeyVaultName = 'sa-{project-name}-prod-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Prod'
param userAssignedManagedIdentityPrincipalId = ''
param appConfigurationName = ''
