# Backend Source

This folder holds the target application's backend source code.

For agent guidance on working with the backend code, see [AGENTS.md](AGENTS.md).

## Structure

Place your backend project files here. Recommended structure:

- `{ClientName}.{ProjectName}.Api/` — ASP.NET Core API project
- `{ClientName}.{ProjectName}.Domain/` — Domain models and business logic
- `{ClientName}.{ProjectName}.Infrastructure/` — Data access, external service clients
- `{ClientName}.{ProjectName}.Application/` — Application services and use cases
- `{ClientName}.{ProjectName}.Contracts/` — Shared DTOs and API contracts
- `{ClientName}.{ProjectName}.SharedKernel/` — Cross-cutting utilities and base types
- `{ClientName}.{ProjectName}.ConsumersWorker/` — Background worker / message consumers (optional)
