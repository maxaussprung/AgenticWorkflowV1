# Introduction

TODO: Give a short introduction of your project. Let this section explain the objectives or the motivation behind this project.

# Getting Started

TODO: Guide users through getting your code up and running on their own system. In this section you can talk about:

1. Installation process
2. Software dependencies
3. Latest releases
4. API references

# Manage and Deploying Database Changes

The project is using [Entity Framework Core Migrations](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/?tabs=dotnet-core-cli)
in order to manage the evolvement of the database schema changes. The underlying provider that is being used is SQL Server.

## 1. Local Development

When a developer is running the project locally you do not need to worry about migrations since they are [applied automatically at runtime](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/applying?tabs=dotnet-core-cli#apply-migrations-at-runtime)
when the project runs in the development environment.

## 2. Making Database Changes

When we need to make changes on the database schema or data we will have to create a new migration. You can find the existing migrations
under the `{ClientName}.{ProjectName}.Infrastructure\Migrations` folder. In order to create a new migration you will need to make the following steps
in the **powershell** terminal:

- Navigate to the project directory `cd $env:USERPROFILE\source\repos\{ClientName}.{ProjectName}`
- Run `dotnet ef migrations add {MigrationName} --output-dir Migrations\DirectivesDb --project src\backend\{ClientName}.{ProjectName}.Infrastructure --context DirectivesDbContext --namespace Migrations.DirectivesDb --startup-project src\backend\{ClientName}.{ProjectName}.Infrastructure`
- Run `dotnet ef database update {MigrationName} --project src\backend\{ClientName}.{ProjectName}.Infrastructure --context DirectivesDbContext --startup-project src\backend\{ClientName}.{ProjectName}.Infrastructure`

Feel free to add migration name that makes sense regarding the change that was made. The migration classes that are created by the CLI
should be commited on the repository.

## 3. Deploying Database Changes

The new version of the database can be deployed to all four stages (dev, test, abn, prod) of the application using the project's [pipeline](https://dev.azure.com/{AZURE-DEVOPS-ORG}/{AZURE-DEVOPS-PROJECT}/_build).
There is a dedicated step in each stage that applies the migrations from the corresponding folder. Please check the [`.yml files`](https://dev.azure.com/{AZURE-DEVOPS-ORG}/{AZURE-DEVOPS-PROJECT}/_git/{ClientName}.{ProjectName}?path=/azure/pipeline/job-deploy-database.yml)
for more details.

# Build and Test

1. Navigate to *{ClientName}.{ProjectName}\src*
2. Execute the following commands in two separate terminals:
   a. `dotnet run --project /src/{ClientName}.{ProjectName}.UI`
   b. `dotnet run --project /src/{ClientName}.{ProjectName}.API`
3. Go to *{ClientName}.{ProjectName}\test\{ClientName}.{ProjectName}.UITests*
4. Make sure there is a _test.runsettings_ file there containing a `BASE_URL` as per 2.a command output
5. Go to Test > Configure Run Settings > Select Solution Wide run settings File > Select _test.runsettings_ in Windows Explorer
   OR
6. Go to Terminal and type `dotnet run test --settings:dev.runsettings`
7. Under the Tests folder, Click & Execute the Test Case you prefer
   OR
8. add a new one
9. Happy Testing!

# Running Locally with docker-compose and UI System Tests

To run the project locally using docker-compose, follow these steps:

1. Create a Personal Access Token (PAT) for Azure DevOps (ADO)
   - Go to ADO User Settings → Personal Access Tokens → New Token
   - Set the required scope to at least: Packaging (Read & Write)
   - Copy the token once it's created — you won't be able to see it again!
2. Update nuget.config to allow downloading NuGet packages:
   - Edit file at _{ClientName}.{ProjectName}\nuget.config_
   - Add your credentials: Under `<packageSourceCredentials>` add

     ```xml
     <packageSourceCredentials>
        <{AZURE-DEVOPS-ORG}>
           <add key="Username" value="{your-email}" />
           <add key="ClearTextPassword" value="YOUR_PERSONAL_ACCESS_TOKEN" />
        </{AZURE-DEVOPS-ORG}>
     </packageSourceCredentials>
     ```

   - Replace `{your-email}` and `YOUR_PERSONAL_ACCESS_TOKEN` with the actual user and token.
3. Set Your PAT as an Environment Variable.
   - In PowerShell: `$env:PAT = "YOUR_PERSONAL_ACCESS_TOKEN"`
   - Or set it permanently in System Environment Variables if preferred.
4. Build and Run the Services.
   - From the project root: Execute `docker-compose up --build`
     This builds all images and starts the services.
5. Wait for Services to Become Available
6. Access the App.
   - Frontend UI: [{PROJECT-NAME}-UI](http://localhost:3000)
   - API Swagger: [Swagger](http://localhost:5000/docs/index.html)
