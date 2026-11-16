"""Create an internal API key for obliq-in-app / canary / load tests.

Usage:
    python -m scripts.create_internal_key --org-id <uuid> --name "obliq-in-app"
"""

import argparse
import asyncio
import sys
from uuid import UUID

from obliq_api.auth.keys import generate_api_key
from obliq_api.db.session import AsyncSessionLocal
from obliq_api.models.api_key import ApiKey
from obliq_api.models.organisation import Organisation


async def main(org_id: UUID, name: str) -> None:
    async with AsyncSessionLocal() as session:
        org = await session.get(Organisation, org_id)
        if org is None:
            print(f"Organisation {org_id} not found", file=sys.stderr)
            sys.exit(1)

        full_key, prefix, key_hash = generate_api_key(internal=True)
        api_key = ApiKey(
            organisation_id=org_id,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            is_internal=True,
            status="active",
        )
        session.add(api_key)
        await session.commit()

        print("Internal API key created (store this securely – it will not be shown again):")
        print(full_key)
        print(f"Prefix: {prefix}")
        print(f"ID:     {api_key.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", type=UUID, required=True)
    parser.add_argument("--name", default="internal")
    args = parser.parse_args()
    asyncio.run(main(args.org_id, args.name))
