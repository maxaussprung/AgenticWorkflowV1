using 'kafka-consumers.bicep'

param espAddressDomainKeyVaultName = 'sa-{project-name}-test-{suffix}'
param espSubscriptionId = '{ESP-SUBSCRIPTION-ID}'
param espResourceGroupName = 'resgroup-{PLATFORM-NAME}-Infrastructure-Test'
param userAssignedManagedIdentityPrincipalId = ''
param appConfigurationName = '{project-name}-app-configuration-test-{suffix}'
