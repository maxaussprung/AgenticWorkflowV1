using 'kafka-consumers.bicep'

param espAddressDomainKeyVaultName = 'sa-{project-name}-dev-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Dev'
param userAssignedManagedIdentityPrincipalId = '{AZURE-AD-OBJECT-ID}'
param appConfigurationName = '{project-name}-app-configuration-dev-{suffix}'
