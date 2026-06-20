# assets/

This folder holds **static assets** for the requirements site — logos, favicons, and UI screenshots.

## Structure

```
assets/
├── screens/     # UI screenshots referenced in requirements (screen traceability)
│   ├── {source-id}/    # Grouped by source document
│   └── ...
└── {logo/favicon files}
```

## Usage

- Add project logo and favicon files here (replace the placeholder files).
- UI screenshots go in `screens/{source-id}/` and are referenced via `screens:` frontmatter in requirements.
