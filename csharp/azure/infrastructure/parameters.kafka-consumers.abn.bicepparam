using 'kafka-consumers.bicep'

param espAddressDomainKeyVaultName = 'sa-{project-name}-abn-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Abn'
param userAssignedManagedIdentityPrincipalId = ''
param appConfigurationName = '{project-name}-app-configuration-abn-{suffix}'
