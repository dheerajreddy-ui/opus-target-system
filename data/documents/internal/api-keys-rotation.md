# API Key Rotation Schedule (INTERNAL)

## Current Rotation
- Production API keys: Rotate every 90 days
- Staging API keys: Rotate every 30 days
- Development API keys: Rotate on team member departure

## Key Management
All API keys are stored in the vault. Never hardcode keys in source code.
Use environment variables for local development.

## Emergency Rotation
If a key compromise is suspected, immediately:
1. Revoke the compromised key
2. Generate a new key
3. Update all dependent services
4. Notify the security team
